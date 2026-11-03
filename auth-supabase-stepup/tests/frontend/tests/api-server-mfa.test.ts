import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { api } from "../lib/api-server";
import { soft } from "../lib/loaders/_util";
import { server, useMsw } from "./msw";

vi.mock("next/headers", () => ({ cookies: async () => ({ get: (n: string) => (n === "sv_at" ? { value: "tok" } : undefined) }), headers: async () => new Headers() }));
useMsw();
const API = "http://127.0.0.1:8000";

describe("server calls to the backend when the role needs the second step", () => {
  it("send the user to sign-in to enrol or verify, even inside soft()", async () => {
    server.use(http.get(`${API}/v1/surveys`, () => HttpResponse.json({ detail: { code: "mfa_required", action: "enrol_or_verify" } }, { status: 403 })));
    await expect(api("/v1/surveys")).rejects.toThrow("NEXT_REDIRECT /auth?mfa=1");
    await expect(soft(api("/v1/surveys"))).rejects.toThrow("NEXT_REDIRECT /auth?mfa=1");     // a section does not quietly come back empty
  });
  it("leave other 403s alone", async () => {
    server.use(http.get(`${API}/v1/surveys`, () => HttpResponse.json({ detail: "forbidden" }, { status: 403 })));
    expect(await soft(api("/v1/surveys"))).toBeNull();
  });
});
