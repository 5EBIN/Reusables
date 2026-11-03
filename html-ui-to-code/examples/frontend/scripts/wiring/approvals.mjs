// approvals.html -> live list by status (GET /v1/approvals), detail panel for the selected action, approve / send back (POST /v1/approvals/{id}/decide), bulk decisions.
// The list rows carry a JSON `detail` string; the client derives the detail-panel fields from the selected row (see lib/approvals-model.ts).
const CARD = ".g-8-4 > .col > section:nth-child(1)";
const REC = ".g-8-4 > .col > section:nth-child(2)";
const DET = ".g-8-4 > section";
const D = (n) => `${DET} .cb > .col > div:nth-child(${n})`;
const TABS = ["p", "a", "r", "e"];
const note = (cond, tone, msg) => `{${cond} && <div className={\`notice \${${tone}} mb16\`} role={${tone} === "bad" ? "alert" : "status"}>{${msg}}</div>}`;

export default {
  loader: "params",
  client: true,
  textWrap: "m",
  derive: "{ ...base, ...detailFields(base, selId) }",
  extraData: { hasDetail: "1", showTwo: "1", showBlast: "1", showEx: "1", showPreview: "1", canAct: "1", canBulk: "1", tab: "p" },
  imports: ['import { useState } from "react";', 'import { bff, get, post } from "@/lib/client-api";', 'import { useDecode } from "@/lib/decode";', 'import { useMsg } from "@/lib/messages";',
    'import { detailFields, errorKey, toView, type ApprovalsApi } from "@/lib/approvals-model";'],
  prelude: `
  const m = useDecode(); const t = useMsg();
  const [tab, setTab] = useState(d0.tab || "p"); const [alt, setAlt] = useState<Partial<Data> | null>(null); const [selId, setSelId] = useState<string | null>(null);
  const [picked, setPicked] = useState<Record<string, boolean>>({}); const [busy, setBusy] = useState(false); const [ask, setAsk] = useState(false); const [comment, setComment] = useState("");
  const [msg, setMsg] = useState<{ tone: "ok" | "bad" | "info"; text: string } | null>(null);
  const base: Data = alt ? ({ ...d0, ...alt } as Data) : d0;
  const reload = async (code: string) => {
    const r = await get<ApprovalsApi>(bff(\`v1/approvals?status=\${{ p: "pending", a: "approved", r: "rejected", e: "executed" }[code] ?? "pending"}\`));
    if (!r.ok) { setMsg({ tone: "bad", text: t("ap_load_failed") }); return; }
    setAlt(toView(r.data, code) as Partial<Data>); setPicked({});
  };
  const pickTab = (code: string) => { setTab(code); setSelId(null); setAsk(false); setMsg(null); void reload(code); };
  const decideOne = async (id: string, approve: boolean, why?: string) => post(bff(\`v1/approvals/\${id}/decide\`), { approve, ...(why ? { comment: why } : {}) });
  const decide = async (approve: boolean) => {
    const id = selId ?? base.items[0]?.id; if (!id) return;
    if (!approve && !ask) { setAsk(true); return; }
    setBusy(true); setMsg(null);
    const r = await decideOne(id, approve, approve ? undefined : comment.trim() || undefined);
    setBusy(false);
    if (!r.ok) { setMsg({ tone: "bad", text: t(errorKey(r.status, r.error)) }); return; }
    setAsk(false); setComment(""); setMsg({ tone: "ok", text: t(approve ? "ap_decided_approved" : "ap_decided_rejected") });
    await reload(tab);
  };
  const bulk = async (approve: boolean) => {
    const ids = Object.keys(picked).filter((k) => picked[k]);
    if (!ids.length) { setMsg({ tone: "info", text: t("ap_bulk_none") }); return; }
    setBusy(true); setMsg(null);
    let done = 0, skipped = 0;
    for (const id of ids) { const r = await decideOne(id, approve); if (r.ok) done++; else skipped++; }
    setBusy(false); setMsg({ tone: skipped ? "info" : "ok", text: t("ap_bulk_done", { 0: done, 1: skipped }) });
    await reload(tab);
  };
`,
  rules: [
    { sel: ".tabs", after: note("msg", "msg.tone", "msg.text") },
    ...TABS.map((c, i) => ({ sel: `.tabs button:nth-child(${i + 1})`, attrs: { className: `tab === ${JSON.stringify(c)} ? "on" : undefined`, onClick: `() => pickTab(${JSON.stringify(c)})` } })),
    // pending list
    { sel: `${CARD} .ch h3`, bind: "listTitle" },
    { sel: `${CARD} .ch button:nth-of-type(1)`, bind: "approveSelected", show: "canBulk", attrs: { onClick: "() => bulk(true)", disabled: "busy" } },
    { sel: `${CARD} .ch button:nth-of-type(2)`, bind: "rejectSelected", show: "canBulk", attrs: { onClick: "() => bulk(false)", disabled: "busy" } },
    { sel: `${CARD} tbody tr`, rows: { name: "items", as: "r", extra: ["id", "detail", "pending"], fields: {
      ".": { raw: { onClick: "() => { setSelId(r.id ?? null); setAsk(false); }" } },
      "td:nth-child(1) input": { raw: { checked: "!!picked[r.id ?? '']", onChange: "() => setPicked((p) => ({ ...p, [r.id ?? '']: !p[r.id ?? ''] }))", disabled: "!r.pending" } },
      "td:nth-child(2) b": "title", "td:nth-child(2) .sub": "sub",
      "td:nth-child(3) .badge": { text: "risk", attrs: { class: "riskCls" } },
      "td:nth-child(4)": "recipients", "td:nth-child(5)": "by", "td:nth-child(6)": "when",
      "td:nth-child(7)": { list: "checks", listSel: ".badge", listWrap: ".row" },
    } } },
    { sel: `${CARD} table.t`, after: '{d.items.length === 0 ? <div className="empty"><b>{t("ap_empty_title")}</b>{t("ap_empty_body")}</div> : null}' },
    // receipts
    { sel: `${REC} tbody tr`, rows: { name: "receipts", as: "r", fields: { "td:nth-child(1)": "at", "td:nth-child(2)": "action", "td:nth-child(3)": "result", "td:nth-child(4)": "by" } } },
    // detail
    { sel: DET, show: "hasDetail" },
    { sel: `${DET} .ch h3`, bind: "dTitle" },
    { sel: `${D(1)} span.sm`, bind: "dMeta" },
    { sel: `${D(1)} span.badge`, show: "showTwo", bind: "dTwo" },
    { sel: D(2), show: "showBlast" },
    { sel: `${D(2)} .g3 > div:nth-child(1) .v`, bind: "dContacts" }, { sel: `${D(2)} .g3 > div:nth-child(1) .xs`, bind: "dContactsL" },
    { sel: `${D(2)} .g3 > div:nth-child(2) .v`, bind: "dChannels" }, { sel: `${D(2)} .g3 > div:nth-child(2) .xs`, bind: "dChannelsL" },
    { sel: `${D(2)} .g3 > div:nth-child(3) .v`, bind: "dExcluded" }, { sel: `${D(2)} .g3 > div:nth-child(3) .xs`, bind: "dExcludedL" },
    { sel: `${D(2)} .cap`, bind: "dBlastH" },
    { sel: D(3), show: "showEx" },
    { sel: `${D(3)} .cap`, bind: "dExH" },
    { sel: `${D(3)} .col > .row`, rows: { name: "exRows", as: "x", fields: { "span": "label", "b.num": "n" } } },
    { sel: D(4), show: "showPreview" },
    { sel: `${D(4)} .cap`, bind: "dPreviewH" },
    { sel: `${D(4)} .quote`, rows: { name: "quotes", as: "q", fields: { ".": { text: "text", attrs: { class: "cls", dir: "dir", lang: "lang" } } } } },
    { sel: `${D(5)} > div`, bind: "dNotice" },
    { sel: `${D(6)} button.btn.pri`, bind: "approveLabel", attrs: { onClick: "() => decide(true)", disabled: "busy" } },
    { sel: `${D(6)} button:nth-of-type(2)`, bind: "changesLabel", attrs: { onClick: "() => decide(false)", disabled: "busy" } },
    { sel: D(6), show: "canAct" },
    { sel: D(7), bind: "dFoot", before: `{ask ? <div className="col" style={{ gap: "8px" }}><label className="f" htmlFor="ap-comment">{t("ap_comment_label")}</label><textarea id="ap-comment" className="in" style={{ width: "100%" }} rows={3} maxLength={300} value={comment} onChange={(e) => setComment(e.target.value)} /><div className="row"><button className="btn pri" onClick={() => decide(false)} disabled={busy}>{t("ap_comment_send")}</button><button className="btn" onClick={() => setAsk(false)}>{t("ap_comment_cancel")}</button></div></div> : null}` },
  ],
};
