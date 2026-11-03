import { renderToStaticMarkup } from "react-dom/server";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import Content from "../app/(generated)/surveys/content";
import { load, toView } from "../lib/loaders/surveys";
import { server, useMsw } from "./msw";

vi.mock("next/headers", () => ({ cookies: async () => ({ get: (n: string) => ({ sv_at: { value: "tok" }, sv_org: { value: "org-1" } } as Record<string, { value: string }>)[n] }) }));
useMsw();
const NOW = new Date("2026-10-07T12:00:00Z");

const live = { id: "1", title: { default: "Sample Survey A", ar: "نبض السكان" }, status: "live", languages: ["en", "ar", "ur"], version: 4, questions: 14, responses: 3906, completion: 94,
  last_14_days: [{ date: "2026-10-06", n: 10 }, { date: "2026-10-07", n: 30 }], team: [{ email: "user@example.com", role: "owner" }, { email: "user@example.com", role: "editor" }, { email: "user@example.com", role: "viewer" }], updated_at: "2026-10-07T10:00:00Z" };
const draft = { id: "2", title: { default: "Sample Survey E" }, status: "draft", languages: ["en"], version: 1, questions: 38, responses: 0, completion: null, last_14_days: [], team: [], updated_at: "2026-10-06T09:00:00Z" };

describe("surveys page", () => {
  it("maps API rows to the exact strings the mockup shows", () => {
    const v = toView({ total: 2, items: [live, draft] } as any, NOW);
    expect(v.count).toBe("2 of 2");
    expect(v.surveys[0]).toMatchObject({ title: "Sample Survey A", sub: "14 questions · v4", langs: "EN,AR,UR", status: "Live", statusCls: "badge ok", responses: "3,906", completion: "94%", team: "JL,TK", updated: "2 h ago" });
    expect(v.surveys[0].spark).not.toBe("");
    expect(v.surveys[1]).toMatchObject({ status: "Draft", statusCls: "badge warn", responses: "—", completion: "—", spark: "", team: "", updated: "Yesterday" });
  });

  it("renders rows from live data: draft rows have no sparkline, closed rows an unstyled badge", () => {
    const v = toView({ total: 2, items: [live, draft, { ...live, id: "3", status: "closed" }] } as any, NOW);
    const html = renderToStaticMarkup(<Content d={v} />);
    expect(html).toContain("Sample Survey A"); expect(html).toContain("Sample Survey E"); expect(html).toContain('class="badge "');
    const rows = html.split("<tr").slice(2);
    expect(rows[0]).toContain("<polyline"); expect(rows[1]).not.toContain("<polyline");
  });

  it("escapes hostile titles", () => {
    const html = renderToStaticMarkup(<Content d={toView({ total: 1, items: [{ ...live, title: { default: "<img src=x onerror=alert(1)>" } }] } as any, NOW)} />);
    expect(html).not.toContain("<img src=x"); expect(html).toContain("&lt;img");
  });

  it("loader calls the API with the session's bearer token and organisation", async () => {
    let h: Headers | undefined;
    server.use(http.get("http://127.0.0.1:8000/v1/surveys", ({ request }) => { h = request.headers; return HttpResponse.json({ total: 1, items: [live] }); }),
      http.get("http://127.0.0.1:8000/v1/members", () => HttpResponse.json({ detail: "forbidden" }, { status: 403 })));     // an ordinary refusal of the owner list leaves the page without owners, not without surveys
    const d = await load();
    expect(h?.get("authorization")).toBe("Bearer tok"); expect(h?.get("x-org-id")).toBe("org-1"); expect(d.surveys).toHaveLength(1);
  });

  it("an empty workspace renders no rows", () => {
    expect(renderToStaticMarkup(<Content d={toView({ total: 0, items: [] } as any, NOW)} />)).toContain("0 of 0");
  });
});
