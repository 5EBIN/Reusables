// MACHINE-DRAFTED, NEEDS NATIVE REVIEW: the Urdu, Hindi, Russian and Filipino interface strings were drafted without a native speaker.
// See docs/I18N.md for the review checklist and how to export the strings for a translator. Keys are never translated; {placeholders} are kept as is.
import fil from "./fil";
import hi from "./hi";
import ru from "./ru";
import ur from "./ur";

export type TableId = "messages" | "d" | "e" | "reports" | "authoring" | "distribute" | "runner" | "interview" | "site";
export const TABLE_IDS: readonly TableId[] = ["messages", "d", "e", "reports", "authoring", "distribute", "runner", "interview", "site"];
/** `t`: English page text (the <T> leaves of the generated pages) -> translation. `msgs`: per message table, key -> translation. */
export type Locale = { t: Record<string, string>; msgs: Record<TableId, Record<string, string>> };
export const LOCALE_CODES = ["ur", "hi", "ru", "fil"] as const;
export const LOCALES: Record<(typeof LOCALE_CODES)[number], Locale> = { ur, hi, ru, fil };
