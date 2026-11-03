import { enc } from "./decode";
import { format as msg } from "./messages";

/** View-model formatting shared by the page loaders. Pure, deterministic (the clock is injected) and covered by tests. */
export const DASH = "—";

export const num = (n: number | null | undefined): string => (n === null || n === undefined ? DASH : n.toLocaleString("en-US"));
export const pct = (n: number | null | undefined): string => (n === null || n === undefined ? DASH : `${Math.round(n)}%`);
export const signed = (n: number): string => (n > 0 ? `+${n}` : String(n));

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "3 min ago" / "2 h ago" / "Yesterday" / "12 Sep" (older than a week). */
export function relTime(iso: string, now: Date = new Date()): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return DASH;
  const s = Math.max(0, (now.getTime() - t) / 1000);
  if (s < 60) return "Just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 2 * 86400) return "Yesterday";
  if (s < 7 * 86400) return `${Math.floor(s / 86400)} days ago`;
  const d = new Date(t);
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
}

/** The same wording as relTime, as a message the client translates (pages that decode view-model text with useDecode()). Falls back to English when decoded for an unknown language. */
export function relTimeEnc(iso: string, now: Date = new Date()): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return DASH;
  const s = Math.max(0, (now.getTime() - t) / 1000);
  if (s < 60) return enc("rel_now");
  if (s < 3600) return enc("rel_min", Math.floor(s / 60));
  if (s < 86400) return enc("rel_h", Math.floor(s / 3600));
  if (s < 2 * 86400) return enc("rel_yesterday");
  if (s < 7 * 86400) return enc("rel_days", Math.floor(s / 86400));
  return dayMonthEnc(iso);
}

/** "12 Sep" as a translatable message (day + month name in the reader's language). */
export function dayMonthEnc(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? DASH : enc("date_dm", d.getUTCDate(), enc(`mon_${d.getUTCMonth() + 1}`));
}

/** relTime in the given interface language (for client components that know the language). Unknown languages get English. */
export function relTimeL(lang: string, iso: string, now: Date = new Date()): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return DASH;
  const s = Math.max(0, (now.getTime() - t) / 1000);
  if (s < 60) return msg(lang, "rel_now");
  if (s < 3600) return msg(lang, "rel_min", { 0: Math.floor(s / 60) });
  if (s < 86400) return msg(lang, "rel_h", { 0: Math.floor(s / 3600) });
  if (s < 2 * 86400) return msg(lang, "rel_yesterday");
  if (s < 7 * 86400) return msg(lang, "rel_days", { 0: Math.floor(s / 86400) });
  return dayMonthL(lang, iso);
}

export function dayMonthL(lang: string, iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? DASH : msg(lang, "date_dm", { 0: d.getUTCDate(), 1: msg(lang, `mon_${d.getUTCMonth() + 1}` as "mon_1") });
}

export function dayMonth(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? DASH : `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
}

/** Two-letter avatar initials from an email local part ("jordan.lee@x" -> "JL", "alex@x" -> "AL"). */
export function initials(email: string): string {
  const local = (email.split("@")[0] ?? "").split(/[._\-+]+/).filter(Boolean);
  const out = local.length >= 2 ? local[0][0] + local[1][0] : (local[0] ?? "?").slice(0, 2);
  return out.toUpperCase();
}

/** Polyline points for a 70x24 sparkline from daily counts (any length); "" when there is nothing to draw. */
export function sparkPoints(counts: number[], buckets = 7, w = 70, top = 3, bottom = 21): string {
  if (!counts.length || counts.every((c) => c === 0)) return "";
  const per = Math.max(1, Math.ceil(counts.length / buckets));
  const series: number[] = [];
  for (let i = 0; i < counts.length; i += per) series.push(counts.slice(i, i + per).reduce((a, b) => a + b, 0));
  const lo = Math.min(...series), hi = Math.max(...series);
  const n = series.length;
  return series.map((v, i) => `${((i * w) / Math.max(1, n - 1)).toFixed(1)},${(hi === lo ? (top + bottom) / 2 : bottom - ((v - lo) / (hi - lo)) * (bottom - top)).toFixed(1)}`).join(" ");
}

/** Fill a date-keyed series [{date, n}] into the last `days` calendar days (zeros where missing), oldest first. */
export function lastDays(series: { date: string; n: number }[], days: number, now: Date = new Date()): number[] {
  const m = new Map(series.map((x) => [x.date, x.n]));
  const out: number[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now.getTime() - i * 86400000);
    out.push(m.get(d.toISOString().slice(0, 10)) ?? 0);
  }
  return out;
}
