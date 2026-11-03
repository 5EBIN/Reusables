import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { load as team } from "../lib/loaders/team";
import { load as templates } from "../lib/loaders/templates";
import { load as surveys } from "../lib/loaders/surveys";
import { server, useMsw } from "./msw";

vi.mock("next/headers", () => ({ cookies: async () => ({ get: (n: string) => (n === "sv_at" ? { value: "tok" } : undefined) }), headers: async () => new Headers() }));
useMsw();
const API = "http://127.0.0.1:8000";
const MFA = () => HttpResponse.json({ detail: { code: "mfa_required", action: "enrol_or_verify" } }, { status: 403 });

// These three loaders used to end every call in `.catch(() => EMPTY)`, which swallowed the redirect to two-step sign-in and left the administrator on an empty page.
const CASES = [
  ["team", () => team(), ["/v1/members", "/v1/permissions"]],
  ["templates", () => templates(), ["/v1/templates", "/v1/presets"]],
  ["surveys", () => surveys(), ["/v1/surveys", "/v1/members"]],
] as const;

describe.each(CASES)("%s loader", (_name, load, paths) => {
  it.each(paths)("sends the user to two-step sign-in when %s needs it", async (path) => {
    for (const p of paths) server.use(http.get(`${API}${p}`, p === path ? MFA : () => HttpResponse.json({}, { status: 404 })));
    await expect(load()).rejects.toThrow("NEXT_REDIRECT /auth?mfa=1");
  });
  it("still degrades to an empty page when the API answers with an ordinary error", async () => {
    for (const p of paths) server.use(http.get(`${API}${p}`, () => (_name === "surveys" && p === "/v1/surveys" ? HttpResponse.json({ total: 0, items: [] }) : HttpResponse.json({ detail: "boom" }, { status: 500 }))));
    await expect(load()).resolves.toBeTruthy();
  });
});
