import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { GET as orgGet, POST as orgPost } from "../app/api/org/route";
import { GET as bffGet, POST as bffPost } from "../app/api/bff/[...path]/route";
import { server, useMsw } from "./msw";

useMsw();
const API = "http://127.0.0.1:8000";
const req = (path: string, body?: unknown, init: RequestInit & { csrf?: boolean } = {}) => {
  const { csrf = true, headers, ...rest } = init;
  return new Request(`http://localhost:3000${path}`, { method: "POST", ...rest, headers: { "content-type": "application/json", host: "localhost:3000", ...(csrf ? { "x-sv-csrf": "1", origin: "http://localhost:3000" } : {}), ...(headers as Record<string, string>) }, body: body === undefined ? undefined : JSON.stringify(body) });
};
const cookies = (r: Response) => r.headers.getSetCookie();
const T = { access_token: "a.b.c", refresh_token: "refresh-token-1", expires_in: 900 };

describe("organisation selection", () => {
  const auth = { cookie: "sv_at=tok" };
  it("lists orgs only when signed in", async () => {
    expect((await orgGet(new Request("http://localhost:3000/api/org"))).status).toBe(401);
    server.use(http.get(`${API}/v1/orgs`, ({ request }) => (request.headers.get("authorization") === "Bearer tok" ? HttpResponse.json([{ id: "o1", name: "A", role: "analyst" }]) : HttpResponse.json([], { status: 401 }))));
    expect(await (await orgGet(new Request("http://localhost:3000/api/org", { headers: auth }))).json()).toHaveLength(1);
  });

  it("switching only works for organisations the API says you belong to", async () => {
    server.use(http.get(`${API}/v1/orgs`, () => HttpResponse.json([{ id: "o1", name: "A", role: "analyst" }])));
    expect((await orgPost(req("/api/org", { id: "someone-elses-org" }, { headers: auth }))).status).toBe(403);
    const ok = await orgPost(req("/api/org", { id: "o1" }, { headers: auth }));
    expect(ok.status).toBe(200); expect(cookies(ok).join()).toMatch(/sv_org=o1/);
    expect((await orgPost(req("/api/org", { id: "o1" }, { headers: auth, csrf: false }))).status).toBe(403);
    expect((await orgPost(req("/api/org", { id: "o1" }))).status).toBe(401);
  });

  it("creating an organisation selects it", async () => {
    server.use(http.post(`${API}/v1/orgs`, async ({ request }) => HttpResponse.json({ id: "n1", name: ((await request.json()) as any).name }, { status: 201 })));
    const r = await orgPost(req("/api/org", { name: "<company>" }, { headers: auth }));
    expect(r.status).toBe(201); expect(cookies(r).join()).toMatch(/sv_org=n1/);
  });
});

describe("authenticated proxy: the AI status", () => {
  it("passes X-AI-Status on, so the page can say the result is the fallback", async () => {
    server.use(http.post(`${API}/v1/analytics/ask`, () => HttpResponse.json({ outcome: "CANT_YET" }, { headers: { "x-ai-status": "unavailable", "x-internal": "no" } })));
    const r = await bffPost(req("/api/bff/v1/analytics/ask", { text: "x" }, { headers: { cookie: "sv_at=tok" } }), { params: Promise.resolve({ path: ["v1", "analytics", "ask"] }) });
    expect(r.headers.get("x-ai-status")).toBe("unavailable"); expect(r.headers.get("x-internal")).toBeNull();
  });
});

describe("authenticated proxy: server timing", () => {
  it("passes the backend's Server-Timing on, so the browser's network tab shows where the time went", async () => {
    server.use(http.get(`${API}/v1/surveys`, () => HttpResponse.json([], { headers: { "server-timing": "auth;dur=1.2, total;dur=9", "x-internal": "no" } })));
    const r = await bffGet(new Request("http://localhost:3000/api/bff/v1/surveys", { headers: { cookie: "sv_at=tok" } }), { params: Promise.resolve({ path: ["v1", "surveys"] }) });
    expect(r.headers.get("server-timing")).toBe("auth;dur=1.2, total;dur=9"); expect(r.headers.get("x-internal")).toBeNull();
  });
});

describe("authenticated proxy", () => {
  const ctx = (p: string[]) => ({ params: Promise.resolve({ path: p }) });
  const session = { cookie: "sv_at=old; sv_rt=rt; sv_org=o1" };

  it("adds the bearer token and org header server-side and only proxies /v1", async () => {
    let seen: Headers | undefined;
    server.use(http.get(`${API}/v1/surveys`, ({ request }) => { seen = request.headers; return HttpResponse.json({ items: [] }); }));
    const r = await bffGet(new Request("http://localhost:3000/api/bff/v1/surveys", { headers: session }), ctx(["v1", "surveys"]));
    expect(r.status).toBe(200); expect(seen?.get("authorization")).toBe("Bearer old"); expect(seen?.get("x-org-id")).toBe("o1");
    for (const p of [["public", "v1", "c", "x"], ["healthz"], ["metrics"], ["v1", "..", "metrics"], ["v1", "a%2e%2e"], ["api", "v1"]]) expect((await bffGet(new Request("http://localhost:3000/x", { headers: session }), ctx(p))).status).toBe(404);
  });

  it("passes the backend's 401 straight through (the proxy refreshes sessions before a request gets here; there is no second refresh path)", async () => {
    let calls = 0;
    server.use(http.get(`${API}/v1/surveys`, () => { calls++; return HttpResponse.json({}, { status: 401 }); }));
    const r = await bffGet(new Request("http://localhost:3000/x", { headers: session }), ctx(["v1", "surveys"]));
    expect(r.status).toBe(401); expect(calls).toBe(1); expect(cookies(r)).toEqual([]);
  });

  it("sends no bearer when there is no session", async () => {
    let seen: Headers | undefined;
    server.use(http.get(`${API}/v1/surveys`, ({ request }) => { seen = request.headers; return HttpResponse.json({}, { status: 401 }); }));
    await bffGet(new Request("http://localhost:3000/x", { headers: { cookie: "sv_org=o1" } }), ctx(["v1", "surveys"]));
    expect(seen?.get("authorization")).toBeNull();
  });

  it("writes need the CSRF header; bodies and content types pass through", async () => {
    let body = "";
    server.use(http.post(`${API}/v1/approvals`, async ({ request }) => { body = await request.text(); return HttpResponse.json({ id: "x" }, { status: 201 }); }));
    expect((await bffPost(req("/api/bff/v1/approvals", { a: 1 }, { csrf: false, headers: session }), ctx(["v1", "approvals"]))).status).toBe(403);
    expect((await bffPost(req("/api/bff/v1/approvals", { a: 1 }, { headers: session }), ctx(["v1", "approvals"]))).status).toBe(201);
    expect(JSON.parse(body)).toEqual({ a: 1 });
  });

  it("streams downloads with their headers", async () => {
    server.use(http.get(`${API}/v1/exports/abc/download`, () => new HttpResponse("a,b\n1,2\n", { headers: { "content-type": "text/csv", "content-disposition": 'attachment; filename="x.csv"' } })));
    const r = await bffGet(new Request("http://localhost:3000/x", { headers: session }), ctx(["v1", "exports", "abc", "download"]));
    expect(r.headers.get("content-type")).toBe("text/csv"); expect(await r.text()).toBe("a,b\n1,2\n");
  });

  it("logo upload: CSRF is required, a multipart body and its boundary reach the API untouched, the logo is read back through the same authenticated route", async () => {
    let seen: { ct: string | null; len: number; org: string | null; auth: string | null } | null = null;
    server.use(http.post(`${API}/v1/org/logo`, async ({ request }) => { const b = await request.arrayBuffer(); seen = { ct: request.headers.get("content-type"), len: b.byteLength, org: request.headers.get("x-org-id"), auth: request.headers.get("authorization") }; return HttpResponse.json({ mime: "image/png", size: 4, version: "abc", url: "/v1/org/logo" }, { status: 201 }); }),
      http.get(`${API}/v1/org/logo`, () => new HttpResponse(new Uint8Array([137, 80, 78, 71]), { headers: { "content-type": "image/png", "cache-control": "private, no-cache", etag: '"x"' } })));
    const fd = new FormData(); fd.append("file", new Blob([new Uint8Array([137, 80, 78, 71])], { type: "image/png" }), "logo.png");
    const mk = (csrf: boolean) => new Request("http://localhost:3000/api/bff/v1/org/logo", { method: "POST", body: fd, headers: { host: "localhost:3000", ...(csrf ? { "x-sv-csrf": "1", origin: "http://localhost:3000" } : {}), cookie: "sv_at=tok; sv_org=org-1" } });
    expect((await bffPost(mk(false), ctx(["v1", "org", "logo"]))).status).toBe(403);
    expect(seen).toBeNull();                                                                                  // nothing reached the API without the CSRF header
    expect((await bffPost(mk(true), ctx(["v1", "org", "logo"]))).status).toBe(201);
    expect(seen!.ct).toMatch(/^multipart\/form-data; boundary=/); expect(seen!.len).toBeGreaterThan(4); expect(seen!.org).toBe("org-1"); expect(seen!.auth).toBe("Bearer tok");
    const g = await bffGet(new Request("http://localhost:3000/api/bff/v1/org/logo?v=abc", { headers: { cookie: "sv_at=tok; sv_org=org-1" } }), ctx(["v1", "org", "logo"]));
    expect(g.status).toBe(200); expect(g.headers.get("content-type")).toBe("image/png"); expect(g.headers.get("etag")).toBe('"x"');
  });
});
