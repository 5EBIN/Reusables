// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import Content from "../app/(generated)/approvals/content";
import { detailFields, errorKey, toView, type ApprovalItem, type ApprovalsApi } from "../lib/approvals-model";
import { I18nProvider } from "../components/I18n";
import { decode } from "../lib/decode";
import { load } from "../lib/loaders/approvals";
import { personName, whenLabel } from "../lib/people";
import { server, useMsw } from "./msw";

vi.mock("next/headers", () => ({ cookies: async () => ({ get: (n: string) => ({ sv_at: { value: "tok" }, sv_org: { value: "org-1" } } as Record<string, { value: string }>)[n] }) }));
useMsw();
afterEach(cleanup);
const NOW = new Date("2026-10-07T04:00:00Z");                                   // 08:00 local time
const en = (v: string) => decode("en", v);

const invites: ApprovalItem = {
  id: "a1", action_type: "send_survey_invites", risk: "high", status: "pending", title: "Send invitations", subtitle: "Sample Survey G · email + chat", recipients: 3180,
  proposed_by_email: "user@example.com", decided_by_email: null, scheduled_for: "2026-10-07T06:00:00Z", created_at: "2026-10-07T02:00:00Z",
  preview: { selected: 3592, will_receive: 3180, channels: ["email", "whatsapp"], exclusions: { no_consent: 287, suppressed: 96, recently_contacted: 29 }, quiet_hours: "21:00-08:00 Asia/Dubai",
    checks: ["consent", "suppression", "quiet hrs", "quota"], body: { ar: "مرحباً {first_name} {link}", en: "Hello {first_name}, {link}" } },
};
const remind: ApprovalItem = { ...invites, id: "a2", action_type: "send_reminder", risk: "medium", title: "Send reminder", subtitle: "Sample Survey B · email", recipients: 412, proposed_by_email: null,
  scheduled_for: "2026-10-07T12:00:00Z", preview: { ...invites.preview, will_receive: 412, selected: 412, channels: ["email"], checks: ["consent", "quota"], exclusions: { no_consent: 0, suppressed: 0, recently_contacted: 0 } } };
const publish: ApprovalItem = { id: "a3", action_type: "publish_benchmark_rows", risk: "high", status: "pending", title: "Publish benchmark rows", subtitle: "Sector A · Region A · 3 rows", recipients: null, proposed_by_email: "user@example.com",
  decided_by_email: null, scheduled_for: null, created_at: "2026-10-07T01:00:00Z", preview: { checks: ["source check"] } };
const executed: ApprovalItem = { ...invites, id: "r1", status: "executed", decided_by_email: "user@example.com", executed_at: "2026-10-06T06:02:00Z", scheduled_for: null, confirmation: "1,044 sent · 1,031 delivered", title: "Send reminder" };
const API: ApprovalsApi = { counts: { pending: 4, executed: 1 }, items: [invites, remind, publish], receipts: [executed], can_decide: true };

describe("approvals mapping", () => {
  const v = toView(API, "p", NOW);
  it("builds the list rows the mockup shows", () => {
    expect(en(v.listTitle)).toBe("Pending · 4");
    expect(v.items.map((r) => [r.title, r.sub, en(r.risk), r.riskCls, r.recipients, en(r.by), en(r.when)])).toEqual([
      ["Send invitations", "Sample Survey G · email + chat", "High", "badge bad", "3,180", "Alex", "Today 10:00"],
      ["Send reminder", "Sample Survey B · email", "Medium", "badge warn", "412", "System schedule", "Today 16:00"],
      ["Publish benchmark rows", "Sector A · Region A · 3 rows", "High", "badge bad", "—", "A. Agent", "—"] ]);
    expect(v.items.map((r) => r.checks.split(",").filter(Boolean).map(en))).toEqual([["consent", "suppression", "quiet hrs", "quota"], ["consent", "quota"], ["source check"]]);
    expect(v.items.every((r) => r.pending === "1")).toBe(true);
    expect(v.receipts.map((r) => ({ ...r, at: en(r.at) }))).toEqual([{ at: "Yesterday 10:02", action: "Send reminder", result: "1,044 sent · 1,031 delivered", by: "Chris Park" }]);
  });

  it("derives the detail panel from the selected row", () => {
    const d = { ...v, ...detailFields(v, null) } as any;
    expect([d.dTitle, d.dContacts, d.dChannels, d.dExcluded, d.showTwo, d.showBlast, d.canAct]).toEqual(["Send invitations", "3,180", "2", "412", "1", "1", "1"]);
    expect(d.exRows.map((x: any) => [en(x.label), x.n])).toEqual([["No consent for the channel", "287"], ["On suppression list", "96"], ["Contacted recently", "29"]]);
    expect(d.quotes).toEqual([{ text: "Hello {first_name}, {link}", cls: "quote", dir: "", lang: "" }, { text: "مرحباً {first_name} {link}", cls: "quote mt8", dir: "rtl", lang: "ar" }]);
    expect(en(d.dNotice)).toBe("Scheduled for 10:00 GST. Quiet hours (21:00–08:00) are respected; nothing sends outside them.");
    expect(en(d.dMeta)).toBe("Proposed by Alex · 2 h ago");
    const p = { ...v, ...detailFields(v, "a3") } as any;                         // not a send: no blast radius, exclusions, preview or two-person... (benchmark rows are high risk)
    expect([p.showBlast, p.showEx, p.showPreview, p.showTwo, p.dTitle]).toEqual(["", "", "", "1", "Publish benchmark rows"]);
    expect(en(p.dNotice)).toBe("No schedule: it runs as soon as it is approved.");
    expect(detailFields({ ...v, items: [] }, null)).toEqual({ hasDetail: "" });
  });

  it("other tabs: counts from the API, decision outcome in the notice, no actions", () => {
    const x = toView({ counts: { executed: 1 }, items: [executed, { ...invites, id: "r2", status: "rejected", decided_by_email: "user@example.com", decision_comment: "Wrong audience: عملاء" }], receipts: [], can_decide: true }, "e", NOW);
    expect(en(x.listTitle)).toBe("Executed · 1"); expect(x.canBulk).toBe(""); expect(x.items.every((r) => r.pending === "")).toBe(true);
    const d1 = detailFields(x, "r1") as any, d2 = detailFields(x, "r2") as any;
    expect([d1.canAct, en(d1.dNotice)]).toEqual(["", "Executed. 1,044 sent · 1,031 delivered"]);
    expect([d2.canAct, en(d2.dNotice)]).toEqual(["", "Sent back by Taylor Kim. Wrong audience: عملاء"]);
  });

  it("a viewer (cannot decide) sees the data but no actions", () => {
    const x = toView({ ...API, can_decide: false }, "p", NOW);
    expect(x.canBulk).toBe(""); expect(x.items.every((r) => r.pending === "")).toBe(true); expect((detailFields(x, null) as any).canAct).toBe("");
  });

  it("empty list hides the detail panel and offers an empty state", () => {
    const x = toView({ counts: {}, items: [], receipts: [], can_decide: true }, "p", NOW);
    expect(x.hasDetail).toBe(""); expect(en(x.listTitle)).toBe("Pending · 0");
    const html = renderToStaticMarkup(<I18nProvider initial="en"><Content d={x} /></I18nProvider>);
    expect(html).toContain("Nothing here"); expect(html).not.toContain("Blast radius");
  });

  it("escapes hostile text and keeps Arabic; Arabic UI translates the chrome strings", () => {
    const evil = "<script>alert(1)</script>";
    const x = toView({ ...API, items: [{ ...invites, title: evil, subtitle: "مسح السكان", proposed_by_email: "user@example.com", preview: { ...invites.preview, body: { en: evil, ar: "مرحباً" } } }] }, "p", NOW);
    const html = renderToStaticMarkup(<I18nProvider initial="en"><Content d={x} /></I18nProvider>);
    expect(html).not.toContain("<script>alert"); expect(html).toContain("&lt;script&gt;"); expect(html).toContain("مسح السكان");
    const ar = renderToStaticMarkup(<I18nProvider initial="ar"><Content d={toView(API, "p", NOW)} /></I18nProvider>);
    expect(ar).toContain("مرتفع"); expect(ar).toContain("نطاق التأثير"); expect(ar).toContain("وافق ونفّذ");
  });

  it("error classification and helpers", () => {
    expect([errorKey(403, "two-person rule: approver cannot be the proposer for high-risk actions"), errorKey(403, "role cannot approve"), errorKey(409, "already decided"), errorKey(500, "x"), errorKey(0, "network")])
      .toEqual(["ap_err_two_person", "ap_err_role", "ap_err_decided", "ap_err_generic", "ap_err_generic"]);
    expect([personName("user@example.com"), personName("user@example.com"), personName(null)]).toEqual(["J. Lee", "Alex", ""]);
    expect([whenLabel("2026-10-07T06:00:00Z", NOW), whenLabel("2026-10-08T06:00:00Z", NOW), whenLabel("2026-10-03T11:30:00Z", NOW), whenLabel(null, NOW), whenLabel("nope", NOW)]).toEqual(["Today 10:00", "Tomorrow 10:00", "3 Oct 15:30", "—", "—"]);
  });
});

describe("loader", () => {
  it("sends the session token and organisation, honours ?status=", async () => {
    const seen: { h?: Headers; status?: string | null } = {};
    server.use(http.get("http://127.0.0.1:8000/v1/approvals", ({ request }) => { seen.h = request.headers; seen.status = new URL(request.url).searchParams.get("status"); return HttpResponse.json(API); }));
    const d = await load({ status: "executed" }, NOW);
    expect(seen.h?.get("authorization")).toBe("Bearer tok"); expect(seen.h?.get("x-org-id")).toBe("org-1"); expect(seen.status).toBe("executed"); expect(d.tab).toBe("e");
    await load({ status: "bogus" }, NOW); expect(seen.status).toBe("pending");
    await load({}, NOW); expect(seen.status).toBe("pending");
  });
});

describe("interactions", () => {
  const mount = (api: ApprovalsApi = API, lang: "en" | "ar" = "en") => render(<I18nProvider initial={lang}><Content d={toView(api, "p", NOW)} /></I18nProvider>);
  const rows = () => Array.from(document.querySelectorAll("tbody tr")).slice(0, 3);
  const detail = () => document.querySelector(".g-8-4 > section") as HTMLElement;

  it("selecting a row shows that action's detail", () => {
    mount();
    expect(within(detail()).getByRole("heading", { name: "Send invitations" })).toBeInTheDocument(); expect(within(detail()).getByText("3,180")).toBeInTheDocument();
    fireEvent.click(rows()[2].querySelector("td:nth-child(2)")!);
    expect(within(detail()).getByRole("heading", { name: "Publish benchmark rows" })).toBeInTheDocument(); expect(within(detail()).queryByText("Blast radius")).not.toBeInTheDocument();
  });

  it("Approve and run posts the decision with CSRF, shows the result and reloads the list", async () => {
    let body: any, csrf = "", listCalls = 0;
    server.use(
      http.post("/api/bff/v1/approvals/a1/decide", async ({ request }) => { csrf = request.headers.get("x-sv-csrf") ?? ""; body = await request.json(); return HttpResponse.json({ status: "approved", job_id: 1 }); }),
      http.get("/api/bff/v1/approvals", ({ request }) => { listCalls++; expect(new URL(request.url).searchParams.get("status")).toBe("pending"); return HttpResponse.json({ ...API, items: [remind, publish] }); }));
    mount();
    fireEvent.click(screen.getByRole("button", { name: "Approve and run" }));
    expect(await screen.findByText("Approved. It will run shortly.")).toBeInTheDocument();
    expect(body).toEqual({ approve: true }); expect(csrf).toBe("1"); expect(listCalls).toBe(1);
    await waitFor(() => expect(screen.queryByText("Sample Survey G · email + chat")).not.toBeInTheDocument());
  });

  it("shows the two-person rule error and keeps the item pending", async () => {
    server.use(http.post("/api/bff/v1/approvals/a1/decide", () => HttpResponse.json({ detail: "two-person rule: approver cannot be the proposer for high-risk actions" }, { status: 403 })));
    mount();
    fireEvent.click(screen.getByRole("button", { name: "Approve and run" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("You proposed this action. A different approver must decide high-risk actions.");
    expect(screen.getByText("Sample Survey G · email + chat")).toBeInTheDocument();
  });

  it("already decided and generic failures have their own messages", async () => {
    server.use(http.post("/api/bff/v1/approvals/a1/decide", () => HttpResponse.json({ detail: "already decided" }, { status: 409 })));
    mount();
    fireEvent.click(screen.getByRole("button", { name: "Approve and run" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already decided");
    server.use(http.post("/api/bff/v1/approvals/a1/decide", () => HttpResponse.error()));
    fireEvent.click(screen.getByRole("button", { name: "Approve and run" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Could not record the decision"));
  });

  it("Request changes asks for a comment and sends the rejection with it", async () => {
    let body: any;
    server.use(http.post("/api/bff/v1/approvals/a1/decide", async ({ request }) => { body = await request.json(); return HttpResponse.json({ status: "rejected" }); }),
      http.get("/api/bff/v1/approvals", () => HttpResponse.json({ ...API, items: [remind] })));
    mount();
    fireEvent.click(screen.getByRole("button", { name: "Request changes" }));
    const box = await screen.findByLabelText("What should change?");
    fireEvent.change(box, { target: { value: "Wrong audience: عملاء" } });
    fireEvent.click(screen.getByRole("button", { name: "Send back" }));
    expect(await screen.findByText("Sent back to the proposer.")).toBeInTheDocument();
    expect(body).toEqual({ approve: false, comment: "Wrong audience: عملاء" });
    expect(screen.queryByLabelText("What should change?")).not.toBeInTheDocument();
  });

  it("bulk approve decides every ticked row and reports skipped ones", async () => {
    const posted: string[] = [];
    server.use(
      http.post("/api/bff/v1/approvals/:id/decide", ({ params }) => { posted.push(String(params.id)); return params.id === "a2" ? HttpResponse.json({ detail: "role cannot approve" }, { status: 403 }) : HttpResponse.json({ status: "approved" }); }),
      http.get("/api/bff/v1/approvals", () => HttpResponse.json({ ...API, items: [publish] })));
    mount();
    const boxes = Array.from(document.querySelectorAll<HTMLInputElement>("tbody tr td:first-child input[type=checkbox]")).slice(0, 3);
    fireEvent.click(boxes[0]); fireEvent.click(boxes[1]);
    fireEvent.click(screen.getByRole("button", { name: "Approve selected" }));
    expect(await screen.findByText("1 decided, 1 skipped")).toBeInTheDocument();
    expect(posted).toEqual(["a1", "a2"]);
  });

  it("bulk with nothing selected explains instead of posting", async () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(await screen.findByText("Select at least one pending action first.")).toBeInTheDocument();
  });

  it("switching tabs loads that status; a failed load keeps the page and says so", async () => {
    const asked: string[] = [];
    server.use(http.get("/api/bff/v1/approvals", ({ request }) => {
      const s = new URL(request.url).searchParams.get("status")!; asked.push(s);
      return s === "rejected" ? HttpResponse.json({ error: "x" }, { status: 500 }) : HttpResponse.json({ counts: { executed: 1 }, items: [executed], receipts: [executed], can_decide: true });
    }));
    mount();
    fireEvent.click(screen.getByRole("button", { name: "Executed" }));
    expect(await screen.findByText("Executed · 1")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve selected" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve and run" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Rejected" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load the approvals.");
    expect(asked).toEqual(["executed", "rejected"]);
  });
});
