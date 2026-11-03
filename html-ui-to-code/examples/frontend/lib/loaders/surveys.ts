import { api } from "@/lib/api-server";
import { orElse } from "./_util";
import { DASH, initials, lastDays, num, pct, relTime, sparkPoints } from "@/lib/format";
import { fullName } from "@/lib/people";
import type { Data } from "@/app/(generated)/surveys/content";

type Survey = {
  id: string; title: Record<string, string>; status: "live" | "draft" | "closed"; languages: string[]; version: number | null; questions: number; responses: number;
  completion: number | null; last_14_days: { date: string; n: number }[]; team: { email: string; role: string }[]; updated_at: string;
};
export type Member = { user_id: string; email: string; role: string };
export type Filters = { q: string; status: string; language: string; owner: string };

const STATUS = { live: ["Live", "badge ok"], draft: ["Draft", "badge warn"], closed: ["Closed", "badge "] } as const;
const COLORS = ["#3b6ea8", "#4e9f7d", "#d98e2b", "#b5524e", "#7c6bb0"];
export const STATUSES = ["all", "live", "draft", "closed"] as const;
export const LANGUAGES = ["all", "en", "ar", "ur", "hi", "ru", "fil"] as const;
export const STATUS_LABELS = ["Status: all", "Live", "Draft", "Closed"];
export const LANGUAGE_LABELS = ["Language: all", "English", "Arabic", "Urdu", "Hindi", "Russian", "Filipino"];
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Filters from the page URL, validated: anything unexpected is ignored (it is only ever forwarded as an API query parameter). */
export function filtersFrom(params: Record<string, string | string[] | undefined> = {}): Filters {
  const one = (k: string) => (Array.isArray(params[k]) ? (params[k] as string[])[0] : (params[k] as string | undefined)) ?? "";
  const status = one("status"), language = one("language"), owner = one("owner");
  return {
    q: one("q").trim().slice(0, 80),
    status: (STATUSES as readonly string[]).includes(status) && status !== "all" ? status : "",
    language: (LANGUAGES as readonly string[]).includes(language) && language !== "all" ? language : "",
    owner: UUID.test(owner) ? owner : "",
  };
}
export function queryString(f: Filters): string {
  const q = new URLSearchParams();
  if (f.status) q.set("status", f.status);
  if (f.language) q.set("language", f.language);
  if (f.owner) q.set("owner", f.owner);
  if (f.q) q.set("q", f.q);
  return q.toString();
}

/** "user@example.com" -> "Jordan Lee"; "user@example.com" -> "Alex". */
const shortName = (email: string) => { const n = fullName(email).split(" "); return n.length > 1 ? `${n[0]} ${n[n.length - 1][0]}.` : n[0]; };

export function toView(res: { total: number; items: Survey[] }, now = new Date(), ctx: { filters?: Filters; members?: Member[] } = {}): Data {
  const f = ctx.filters ?? { q: "", status: "", language: "", owner: "" };
  const owners = (ctx.members ?? []).filter((m) => m.role !== "employee");
  const owner = owners.find((m) => m.user_id === f.owner);
  return {
    count: `${res.items.length} of ${res.total}`,
    fQ: f.q, fStatus: f.status, fLang: f.language, fOwnerId: f.owner, fOwnerLabel: owner ? shortName(owner.email) : "", filtered: f.q || f.status || f.language || f.owner ? "1" : "",
    ownerIds: ["", ...owners.map((m) => m.user_id)].join(","), owners: [{ label: "Owner: anyone" }, ...owners.map((m) => ({ label: shortName(m.email) }))],
    surveys: res.items.map((s, i) => {
      const [status, statusCls] = STATUS[s.status];
      const noData = s.responses === 0;
      const spark = sparkPoints(lastDays(s.last_14_days, 14, now));
      return {
        link: "1", href: `/builder?survey=${s.id}`,
        title: s.title.default ?? Object.values(s.title)[0] ?? "Untitled",
        sub: `${s.questions} question${s.questions === 1 ? "" : "s"} · v${s.version ?? 1}`,
        langs: s.languages.map((l) => l.toUpperCase()).join(","),
        status, statusCls,
        responses: noData ? DASH : num(s.responses), completion: noData ? DASH : pct(s.completion),
        ...(spark ? { spark, sparkColor: COLORS[i % COLORS.length] } : { spark: "" }),
        team: [...new Set(s.team.map((m) => initials(m.email)))].join(","),
        updated: relTime(s.updated_at, now),
      };
    }),
  };
}

export async function load(params: Record<string, string | string[] | undefined> = {}, now = new Date()): Promise<Data> {
  const filters = filtersFrom(params), qs = queryString(filters);
  const [res, members] = await Promise.all([api<{ total: number; items: Survey[] }>(`/v1/surveys${qs ? `?${qs}` : ""}`), orElse(api<{ members: Member[] }>("/v1/members"), [] as Member[], (r: { members: Member[] }) => r.members)]);
  return toView(res, now, { filters, members });
}
