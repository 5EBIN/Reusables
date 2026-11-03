// surveys.html -> live list (GET /v1/surveys with status/language/owner/q filters taken from the URL), header actions (new survey, from template, draft with assistant).
const STATUSES = ["all", "live", "draft", "closed"];
const LANGS = ["all", "en", "ar", "ur", "hi", "ru", "fil"];
const LABELS = { status: ["Status: all", "Live", "Draft", "Closed"], lang: ["Language: all", "English", "Arabic", "Urdu", "Hindi", "Russian", "Filipino"] };

export default {
  loader: "params",
  client: true,
  extraData: { fQ: "", fStatus: "", fLang: "", fOwnerId: "", fOwnerLabel: "", ownerIds: "", filtered: "" },
  imports: ['import { useRef, useState } from "react";', 'import { useRouter } from "next/navigation";', 'import { bff, post } from "@/lib/client-api";', 'import { uuid } from "@/lib/uuid";', 'import { useMsg } from "@/lib/messages";'],
  prelude: `
  const t = useMsg(); const router = useRouter(); const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(false);
  const STATUSES = ${JSON.stringify(STATUSES)}; const LANGS = ${JSON.stringify(LANGS)};
  const go = (patch: Record<string, string>) => {
    const q = new URLSearchParams();
    const cur: Record<string, string> = { q: d.fQ, status: d.fStatus, language: d.fLang, owner: d.fOwnerId ?? "", ...patch };
    for (const [k, v] of Object.entries(cur)) if (v && v !== "all") q.set(k, v);
    router.replace(q.toString() ? \`/surveys?\${q}\` : "/surveys");
  };
  const typing = (v: string) => { if (timer.current) clearTimeout(timer.current); timer.current = setTimeout(() => go({ q: v.trim() }), 300); };
  const newSurvey = async () => {
    setBusy(true); setErr(false);
    const r = await post<{ id: string }>(bff("v1/surveys"), { id: uuid(), title: { default: "Untitled survey" } });
    if (!r.ok) { setBusy(false); setErr(true); return; }
    router.push(\`/builder?survey=\${r.data.id}\`);
  };
`,
  rules: [
    { sel: ".ph .acts button:nth-of-type(1)", attrs: { onClick: '() => router.push("/templates")' } },
    { sel: ".ph .acts button:nth-of-type(2)", attrs: { onClick: '() => router.push("/ai-draft")' } },
    { sel: ".ph .acts button:nth-of-type(3)", attrs: { onClick: "newSurvey", disabled: "busy" }, after: '{err && <div className="notice bad mt8" role="alert">{t("sv_create_failed")}</div>}' },
    { sel: ".tbar input.in", attrs: { defaultValue: "d.fQ || undefined", onChange: "(e) => typing(e.target.value)", type: '"search"', "aria-label": '"Search surveys"' } },
    { sel: ".tbar select:nth-of-type(1)", attrs: { defaultValue: `d.fStatus ? ${JSON.stringify(LABELS.status)}[STATUSES.indexOf(d.fStatus)] : undefined`, onChange: "(e) => go({ status: STATUSES[e.target.selectedIndex] })" } },
    { sel: ".tbar select:nth-of-type(2)", attrs: { defaultValue: `d.fLang ? ${JSON.stringify(LABELS.lang)}[LANGS.indexOf(d.fLang)] : undefined`, onChange: "(e) => go({ language: LANGS[e.target.selectedIndex] })" } },
    { sel: ".tbar select:nth-of-type(3)", attrs: { defaultValue: "d.fOwnerLabel || undefined", onChange: '(e) => go({ owner: d.ownerIds.split(",")[e.target.selectedIndex] ?? "" })' } },
    { sel: ".tbar select:nth-of-type(3) option", rows: { name: "owners", as: "o", fields: { ".": "label" } } },
    { sel: ".tbar .sm.muted", bind: "count" },
    { sel: "table.t tbody tr", rows: { name: "surveys", as: "s", fields: {
      "td:nth-child(2) a": { wrap: "link", attrs: { href: "href" }, optional: true }, "td:nth-child(2) b": "title", "td:nth-child(2) .sub": "sub",
      "td:nth-child(3)": { list: "langs" },
      "td:nth-child(4) .badge": { text: "status", attrs: { class: "statusCls" } },
      "td:nth-child(5)": "responses", "td:nth-child(6)": "completion",
      "td:nth-child(7) svg": { show: "spark", optional: true }, "td:nth-child(7) polyline": { attrs: { points: "spark", stroke: "sparkColor" }, optional: true },
      "td:nth-child(8)": { list: "team" }, "td:nth-child(9)": "updated",
    } } },
    { sel: "table.t", after: '{d.surveys.length === 0 ? <div className="empty"><b>{t("sv_empty_title")}</b>{t("sv_empty_body")}{d.filtered ? <div className="mt8"><button className="btn sm" onClick={() => router.replace("/surveys")}>{t("sv_clear")}</button></div> : null}</div> : null}' },
  ],
};
