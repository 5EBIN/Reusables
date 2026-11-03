// Module hook for node --test: resolves the app's `@/…` alias and extensionless relative imports under src/, so a test can import code (the assistant store) that is written for Next.js.
// Test-only; the app itself is untouched. Registered by alias.mjs.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const SRC = path.resolve(import.meta.dirname, "..", "..", "src");
const SRC_URL = pathToFileURL(SRC).href;
const asFile = base => [base, `${base}.ts`, `${base}.tsx`, path.join(base, "index.ts")].find(p => fs.existsSync(p) && fs.statSync(p).isFile());

export async function resolve(specifier, context, next) {
  if (specifier.startsWith("@/")) {
    const file = asFile(path.join(SRC, specifier.slice(2)));
    if (file) return next(pathToFileURL(file).href, context);
  } else if ((specifier.startsWith("./") || specifier.startsWith("../")) && context.parentURL?.startsWith(SRC_URL) && !path.extname(specifier)) {
    const file = asFile(path.resolve(path.dirname(fileURLToPath(context.parentURL)), specifier));
    if (file) return next(pathToFileURL(file).href, context);
  }
  return next(specifier, context);
}
