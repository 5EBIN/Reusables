import { useLang } from "@/components/I18n";
import { tableFor } from "./i18n/registry";

// PLACEHOLDER catalogue: the real tables hold the product's copy. Add your keys to `en` first; `ar` (and any other language) falls back to English per key.
const M = {
  en: {
    greeting: "Hello, {name}", save: "Save", cancel: "Cancel", nav_menu: "Menu",
    items_count: "{count} items",
  },
  ar: {
    greeting: "[ar] Hello, {name}", save: "[ar] Save", cancel: "[ar] Cancel", nav_menu: "[ar] Menu",
    items_count: "[ar] {count} items",
  },
} as const;
export const MESSAGES_EN: Readonly<Record<string, string>> = M.en;
export const MESSAGES_AR: Readonly<Record<string, string>> = M.ar;
export type MsgKey = keyof (typeof M)["en"];
export const hasMsg = (key: string): key is MsgKey => Object.prototype.hasOwnProperty.call(M.en, key);

export function format(lang: string, key: MsgKey, vars: Record<string, string | number> = {}): string {
  const table = (lang === "ar" ? M.ar : (tableFor(lang, "messages", M.ar) ?? M.en)) as Record<string, string>;
  return Object.entries(vars).reduce((s, [k, v]) => s.replace(`{${k}}`, String(v)), table[key] ?? (M.en as Record<string, string>)[key] ?? String(key));
}

export function useMsg() {
  const { lang } = useLang();
  return (key: MsgKey, vars?: Record<string, string | number>) => format(lang, key, vars);
}
