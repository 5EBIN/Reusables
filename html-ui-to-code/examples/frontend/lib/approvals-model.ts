/** Approvals view-model: pure API -> strings. The list rows carry a JSON `detail` so the client can derive the side panel for whichever row is selected. */
import type { Data } from "@/app/(generated)/approvals/content";
import { enc, stripMarks } from "./decode";
import { DASH, num, relTimeEnc } from "./format";
import type { MsgKey } from "./messages";
import { hhmm, personName, whenLabelEnc } from "./people";

type Preview = { selected?: number; will_receive?: number; channels?: string[]; exclusions?: { no_consent: number; suppressed: number; recently_contacted: number }; quiet_hours?: string; checks?: string[]; body?: Record<string, string> };
export type ApprovalItem = {
  id: string; action_type: string; risk: "low" | "medium" | "high"; status: string; preview: Preview; proposed_by_email?: string | null; decided_by_email?: string | null;
  scheduled_for: string | null; created_at: string; executed_at?: string | null; confirmation?: string; decision_comment?: string | null; title?: string; subtitle?: string; recipients?: number | null;
};
export type ApprovalsApi = { counts: Record<string, number>; items: ApprovalItem[]; receipts: ApprovalItem[]; can_decide: boolean };
export type DetailVM = {
  title: string; meta: string; two: boolean; blast: boolean; contacts: string; one?: boolean; channels: string; oneChannel?: boolean; excluded: string; ex: { label: string; n: string }[];
  quotes: { text: string; cls: string; dir: string; lang: string }[]; notice: string; canAct: boolean;
};

const CHECKS: Record<string, string> = { consent: "consent", suppression: "suppression", "quiet hrs": "quiet", quota: "quota" };
const RTL = new Set(["ar", "ur"]);
const TABS: Record<string, string> = { p: "pending", a: "approved", r: "rejected", e: "executed" };
export const statusOf = (code: string) => TABS[code] ?? "pending";

const quiet = (q?: string) => (q ? q.replace(/\s+[A-Za-z_]+\/[A-Za-z_]+$/, "").replace("-", "–") : "");

function detailOf(it: ApprovalItem, canDecide: boolean, now: Date): DetailVM {
  const p = it.preview ?? {};
  const invite = typeof p.will_receive === "number";
  const by = personName(it.proposed_by_email) || "";
  const sched = it.scheduled_for;
  let notice: string;
  if (it.status === "executed") notice = enc("ap_decided_executed", it.confirmation ?? "");
  else if (it.status === "approved") notice = enc("ap_decided_approved");
  else if (it.status === "rejected") notice = enc("ap_sent_back_by", personName(it.decided_by_email) || DASH, it.decision_comment ?? "");
  else if (sched) notice = quiet(p.quiet_hours) ? enc("ap_scheduled_for", `${hhmm(new Date(sched))} GST`, quiet(p.quiet_hours)) : enc("ap_scheduled_plain", whenLabelEnc(sched, now));
  else notice = enc("ap_not_scheduled");
  const langs = Object.keys(p.body ?? {}).sort((a, b) => (a === "en" ? -1 : b === "en" ? 1 : a.localeCompare(b)));
  return {
    title: it.title ?? it.action_type, meta: enc("ap_proposed_by", by || DASH, relTimeEnc(it.created_at, now)), two: it.risk === "high", blast: invite,
    contacts: num(p.will_receive ?? 0), one: p.will_receive === 1, channels: String((p.channels ?? []).length), oneChannel: (p.channels ?? []).length === 1, excluded: num(Math.max(0, (p.selected ?? 0) - (p.will_receive ?? 0))),
    ex: invite ? [["ap_ex_no_consent", p.exclusions?.no_consent], ["ap_ex_suppressed", p.exclusions?.suppressed], ["ap_ex_recent", p.exclusions?.recently_contacted]].map(([k, n]) => ({ label: enc(k as string), n: num((n as number) ?? 0) })) : [],
    quotes: langs.map((l, i) => ({ text: (p.body as Record<string, string>)[l], cls: i === 0 ? "quote" : "quote mt8", dir: RTL.has(l) ? "rtl" : "", lang: i === 0 && !RTL.has(l) ? "" : l })),
    notice, canAct: it.status === "pending" && canDecide,
  };
}

function row(it: ApprovalItem, canDecide: boolean, now: Date) {
  const checks = (it.preview?.checks ?? []).map((c) => (CHECKS[c] ? enc(`ap_check_${CHECKS[c]}`) : c.replace(/,/g, " "))).join(",");
  return {
    id: it.id, pending: it.status === "pending" && canDecide ? "1" : "", detail: JSON.stringify(detailOf(it, canDecide, now)),
    title: it.title ?? it.action_type, sub: it.subtitle ?? "", risk: enc(`ap_risk_${it.risk}`), riskCls: it.risk === "high" ? "badge bad" : it.risk === "medium" ? "badge warn" : "badge ok",
    recipients: it.recipients == null ? DASH : num(it.recipients), by: it.proposed_by_email ? personName(it.proposed_by_email) : enc("ap_system"),
    when: whenLabelEnc(it.scheduled_for, now), checks,
  };
}

export function toView(raw: ApprovalsApi, code = "p", now = new Date()): Data {
  const a = stripMarks(raw);
  const st = statusOf(code);
  const count = a.counts?.[st] ?? a.items.length;
  const pendingTab = st === "pending";
  return {
    hasDetail: a.items.length ? "1" : "", showTwo: "1", showBlast: "1", showEx: "1", showPreview: "1", canAct: "1", canBulk: pendingTab && a.can_decide && a.items.length ? "1" : "", tab: code,
    listTitle: enc(`ap_title_${st}`, count), approveSelected: enc("ap_approve_selected"), rejectSelected: enc("ap_reject_selected"),
    items: a.items.map((it) => row(it, a.can_decide, now)),
    receipts: a.receipts.map((r) => ({ at: whenLabelEnc(r.executed_at, now), action: r.title ?? r.action_type, result: r.confirmation || DASH, by: personName(r.decided_by_email) || DASH })),
    ...EMPTY_DETAIL, ...(a.items.length ? fieldsOf(detailOf(a.items[0], a.can_decide, now)) : {}),
  } as unknown as Data;
}

const EMPTY_DETAIL = { dTitle: "", dMeta: "", dTwo: enc("ap_two_person"), dBlastH: enc("ap_blast"), dContacts: "", dContactsL: enc("ap_contacts"), dChannels: "", dChannelsL: enc("ap_channels"), dExcluded: "", dExcludedL: enc("ap_excluded"),
  dExH: enc("ap_exclusions"), dPreviewH: enc("ap_preview"), dNotice: "", approveLabel: enc("ap_approve_run"), changesLabel: enc("ap_request_changes"), dFoot: enc("ap_foot"), exRows: [], quotes: [] };

function fieldsOf(v: DetailVM) {
  return {
    ...EMPTY_DETAIL, dTitle: v.title, dMeta: v.meta, showTwo: v.two ? "1" : "", showBlast: v.blast ? "1" : "", showEx: v.blast ? "1" : "", showPreview: v.quotes.length ? "1" : "",
    dContacts: v.contacts, dContactsL: enc(v.one ? "ap_contact_one" : "ap_contacts"), dChannels: v.channels, dChannelsL: enc(v.oneChannel ? "ap_channel_one" : "ap_channels"), dExcluded: v.excluded, exRows: v.ex, dNotice: v.notice, canAct: v.canAct ? "1" : "",
    quotes: v.quotes.map((q) => ({ text: q.text, cls: q.cls, dir: q.dir, lang: q.lang })),
  };
}

/** Client side: detail panel fields for the selected row (first row when nothing is selected). */
export function detailFields(base: Data, selId: string | null): Record<string, unknown> {
  const it = base.items.find((r) => r.id === selId) ?? base.items[0];
  if (!it) return { hasDetail: "" };
  if (!it.detail) return {};                                  // unwired sample rows: keep the mockup's own detail panel
  try {
    return { hasDetail: "1", ...fieldsOf(JSON.parse(it.detail) as DetailVM) };
  } catch {
    return { hasDetail: "" };
  }
}

export function errorKey(status: number, error: string): MsgKey {
  const e = String(error ?? "").toLowerCase();
  if (e.includes("two-person")) return "ap_err_two_person";
  if (e.includes("already") || status === 409) return "ap_err_decided";
  if (e.includes("role cannot") || status === 403) return "ap_err_role";
  return "ap_err_generic";
}
