import type { Dict } from "@/components/I18n";
import { LOCALES } from "@/lib/i18n/locales";

/** English-keyed text of the generated pages (the <T> leaves) for the languages beyond the mockups' EN/AR.
 *  MACHINE-DRAFTED, NEEDS NATIVE REVIEW: see docs/I18N.md. Unlisted strings fall back to English. */
export const dictionary: Dict = { ur: LOCALES.ur.t, hi: LOCALES.hi.t, ru: LOCALES.ru.t, fil: LOCALES.fil.t };
