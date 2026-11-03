// Node-only (tests and scripts/i18n-export.ts): the English page text that the generated pages wrap in <T ar="...">{"English"}</T>.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

export function pageLeaves(root = join(process.cwd(), "app", "(generated)")): { en: string; ar: string }[] {
  const out = new Map<string, string>();
  for (const dir of readdirSync(root, { withFileTypes: true })) {
    if (!dir.isDirectory()) continue;
    let src = "";
    try { src = readFileSync(join(root, dir.name, "content.tsx"), "utf8"); } catch { continue; }
    for (const m of src.matchAll(/<T ar="([^"]*)">\{"((?:[^"\\]|\\.)*)"\}<\/T>/g)) out.set(JSON.parse(`"${m[2]}"`), m[1]);
  }
  return [...out].map(([en, ar]) => ({ en, ar })).sort((a, b) => a.en.localeCompare(b.en));
}
