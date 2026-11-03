// Export every interface string for a translator.  Usage (from frontend/):
//   npx vite-node -c vitest.config.ts scripts/i18n-export.ts            > strings.json   (default)
//   I18N_FORMAT=csv npx vite-node -c vitest.config.ts scripts/i18n-export.ts > strings.csv    (table,key,english,arabic,ur,hi,ru,fil)
// Table `t` is the page text of the generated pages that is wrapped in <T> (key = the English text itself); the others are the message tables.
import { CATALOG_AR, CATALOG_EN } from "../lib/i18n/catalog";
import { pageLeaves } from "../lib/i18n/leaves";
import { LOCALES, LOCALE_CODES, TABLE_IDS } from "../lib/i18n/locales";

const rows: string[][] = [["table", "key", "english", "arabic", ...LOCALE_CODES]];
for (const l of pageLeaves()) rows.push(["t", l.en, l.en, l.ar, ...LOCALE_CODES.map((c) => LOCALES[c].t[l.en] ?? "")]);
for (const id of TABLE_IDS) for (const [k, en] of Object.entries(CATALOG_EN[id])) rows.push([id, k, en, CATALOG_AR[id][k] ?? "", ...LOCALE_CODES.map((c) => LOCALES[c].msgs[id][k] ?? "")]);

const csv = (s: string) => (/[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);
if (process.env.I18N_FORMAT === "csv") process.stdout.write(rows.map((r) => r.map(csv).join(",")).join("\n") + "\n");
else process.stdout.write(JSON.stringify(rows.slice(1).map((r) => Object.fromEntries(rows[0].map((h, i) => [h, r[i]]))), null, 2) + "\n");
