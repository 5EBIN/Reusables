import { beforeEach, describe, expect, it, vi } from "vitest";

// The real helpers (tests/setup.ts replaces them for every other file) against a stand-in Supabase client.
vi.unmock("@/lib/supabase/server");
const sb = vi.hoisted(() => ({ claims: null as unknown, session: null as unknown, verifyOtp: vi.fn(), exchange: vi.fn(), jar: [] as { name: string; value: string }[], seen: [] as string[] }));
vi.mock("@supabase/ssr", () => ({
  parseCookieHeader: (h: string) => h.split("; ").filter(Boolean).map((c) => { const i = c.indexOf("="); return { name: c.slice(0, i), value: c.slice(i + 1) }; }),
  createServerClient: (_u: string, _k: string, o: { cookies: { getAll: () => { name: string }[] } }) => {
    sb.seen = o.cookies.getAll().map((c) => c.name);
    return { auth: { getClaims: async () => ({ data: sb.claims ? { claims: sb.claims } : null }), getSession: async () => ({ data: { session: sb.session } }), verifyOtp: sb.verifyOtp, exchangeCodeForSession: sb.exchange } };
  },
}));
vi.mock("next/headers", () => ({ cookies: async () => ({ getAll: () => sb.jar, set: vi.fn() }) }));

import { GET as callback } from "../app/auth/callback/route";
import { GET as confirm } from "../app/auth/confirm/route";
import { safeNext } from "../lib/supabase/next-path";
import { serverToken, sessionToken } from "../lib/supabase/server";

beforeEach(() => { sb.claims = null; sb.session = null; sb.verifyOtp.mockReset().mockResolvedValue({ error: null }); sb.exchange.mockReset().mockResolvedValue({ error: null }); sb.jar = []; });
const BS = String.fromCharCode(92);
const req = (p: string, cookie = "") => new Request(`http://localhost:3000${p}`, { headers: cookie ? { cookie } : {} });

describe("access token for the backend", () => {
  it("is the session's token, but only after the session's signature checked out (getClaims)", async () => {
    sb.claims = { sub: "u1" }; sb.session = { access_token: "a.b.c" };
    expect(await sessionToken(req("/x", "sb-p-auth-token=abc; sv_org=o1"))).toBe("a.b.c");
    expect(sb.seen).toEqual(["sb-p-auth-token", "sv_org"]);
  });
  it("is null for a session that does not verify, even when a token sits in the cookie", async () => {
    sb.claims = null; sb.session = { access_token: "forged" };
    expect(await sessionToken(req("/x", "sb-p-auth-token=abc"))).toBeNull();
  });
  it("is null with no cookies, and works from the Next.js cookie store too", async () => {
    expect(await sessionToken(req("/x"))).toBeNull();
    sb.claims = { sub: "u1" }; sb.session = { access_token: "srv.tok" }; sb.jar = [{ name: "sb-p-auth-token", value: "v" }];
    expect(await serverToken((await (await import("next/headers")).cookies()) as never)).toBe("srv.tok");
  });
});

describe("/auth/confirm (the link in Supabase's emails)", () => {
  it("verifies the token hash and lands on the page asked for", async () => {
    const r = await confirm(req("/auth/confirm?token_hash=h1&type=signup&next=%2Fsurveys"));
    expect(sb.verifyOtp).toHaveBeenCalledWith({ type: "signup", token_hash: "h1" });
    expect(r.headers.get("location")).toBe("http://localhost:3000/surveys");
  });
  it("sends a recovery link to the new-password step by default", async () => {
    const r = await confirm(req("/auth/confirm?token_hash=h1&type=recovery"));
    expect(r.headers.get("location")).toBe("http://localhost:3000/auth?reset=1");
  });
  it("refuses a bad, expired or unknown-type link, and never redirects off-site", async () => {
    sb.verifyOtp.mockResolvedValue({ error: { message: "expired" } });
    expect((await confirm(req("/auth/confirm?token_hash=h1&type=signup"))).headers.get("location")).toBe("http://localhost:3000/auth?error=confirm");
    expect((await confirm(req("/auth/confirm?token_hash=h1&type=admin"))).headers.get("location")).toBe("http://localhost:3000/auth?error=confirm");
    expect((await confirm(req("/auth/confirm?type=signup"))).headers.get("location")).toBe("http://localhost:3000/auth?error=confirm");
    sb.verifyOtp.mockResolvedValue({ error: null });
    for (const next of ["https://evil.example", "//evil.example", "/" + BS + "evil.example"])
      expect((await confirm(req(`/auth/confirm?token_hash=h&type=signup&next=${encodeURIComponent(next)}`))).headers.get("location")).toBe("http://localhost:3000/auth?welcome=1");
  });
  it("sends a confirmed sign-up to the page that signs it in, and accepts the PKCE form of the same link", async () => {
    expect((await confirm(req("/auth/confirm?token_hash=h1&type=signup"))).headers.get("location")).toBe("http://localhost:3000/auth?welcome=1");
    const r = await confirm(req("/auth/confirm?code=c1&next=%2Fauth%3Fwelcome%3D1"));
    expect(sb.exchange).toHaveBeenCalledWith("c1"); expect(r.headers.get("location")).toBe("http://localhost:3000/auth?welcome=1");
    sb.exchange.mockResolvedValue({ error: { message: "used" } });
    expect((await confirm(req("/auth/confirm?code=c1"))).headers.get("location")).toBe("http://localhost:3000/auth?error=confirm");
  });
});

describe("/auth/callback (code exchange)", () => {
  it("exchanges the code and redirects to a safe next", async () => {
    const r = await callback(req("/auth/callback?code=c1&next=%2Fteam"));
    expect(sb.exchange).toHaveBeenCalledWith("c1"); expect(r.headers.get("location")).toBe("http://localhost:3000/team");
  });
  it("fails closed without a code or when the exchange fails", async () => {
    expect((await callback(req("/auth/callback"))).headers.get("location")).toBe("http://localhost:3000/auth?error=callback");
    sb.exchange.mockResolvedValue({ error: { message: "bad" } });
    expect((await callback(req("/auth/callback?code=c1"))).headers.get("location")).toBe("http://localhost:3000/auth?error=callback");
  });
});

describe("safeNext", () => {
  it.each([["/surveys", "/surveys"], ["/a?b=1", "/a?b=1"], ["//x", "/overview"], ["https://x", "/overview"], ["", "/overview"], [null, "/overview"], ["/a" + BS + "b", "/overview"], ["/a\r\nb", "/overview"]] as const)("%s", (v, want) => {
    expect(safeNext(v)).toBe(want);
  });
});
