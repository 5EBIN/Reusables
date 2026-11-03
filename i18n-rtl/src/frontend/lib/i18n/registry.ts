// Single entry point for every interface-string table. The English + Arabic tables stay next to the screens that use them (so each screen's keys
// are reviewed with its code); Urdu, Hindi, Russian and Filipino live under lib/i18n/<lang>/ and are looked up here. Anything missing falls back to English.
import { LOCALES, type TableId } from "./locales";

export type { TableId };

/** The lookup table for `lang`: Arabic is hand-written next to the screen, the other languages come from lib/i18n/<lang>/. Callers fall back to English per key. */
export function tableFor(lang: string, id: TableId, ar: Readonly<Record<string, string>>): Readonly<Record<string, string>> | undefined {
  if (lang === "ar") return ar;
  if (lang === "en") return undefined;
  return (LOCALES as Record<string, { msgs: Partial<Record<TableId, Record<string, string>>> } | undefined>)[lang]?.msgs[id];
}
