import { useLang } from "@/components/I18n";
import { format, hasMsg } from "./messages";

/** View-models carry translatable sentences as "\u0001key|arg0|arg1" so server loaders stay language-agnostic. Plain strings pass through untouched
 *  (user content can never select a message: an unknown key returns the original text). */
const MARK = "\u0001";
const esc = (s: string) => s.replace(/%/g, "%25").replace(/\|/g, "%7C");
const unesc = (s: string) => s.replace(/%7C/g, "|").replace(/%25/g, "%");

export function enc(key: string, ...args: (string | number)[]): string {
  return MARK + [key, ...args.map((a) => esc(String(a)))].join("|");
}

/** Remove the marker from everything that came from the API (user-authored titles, names, free text) so content can never be mistaken for a message. Call once at the top of a loader's toView. */
export function stripMarks<T>(v: T): T {
  return JSON.parse(JSON.stringify(v), (_k, x) => (typeof x === "string" ? x.split(MARK).join("") : x)) as T;
}

export function decode(lang: string, v: string | undefined, depth = 0): string {
  if (!v || v[0] !== MARK) return v ?? "";
  const [key, ...args] = v.slice(1).split("|");
  if (!hasMsg(key)) return v.slice(1);                 // unknown key: show the text without the marker, never a message chosen by content
  // An argument may itself be a message built by a loader (enc inside enc, e.g. a relative time); API data never carries the marker (stripMarks).
  return format(lang, key, Object.fromEntries(args.map((a, i) => [String(i), depth < 3 ? decode(lang, unesc(a), depth + 1) : unesc(a)])));
}

/** Hook for client pages: `const m = useDecode(); m(d.field)`. */
export function useDecode() {
  const { lang } = useLang();
  return (v?: string) => decode(lang, v);
}
