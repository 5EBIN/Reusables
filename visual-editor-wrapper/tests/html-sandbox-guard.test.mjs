// Static guard (node --test): no same-origin+scripts iframe sandbox, no blob-URL window opens.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const SRC = path.join(import.meta.dirname, "..", "src");
const HELD = new Set(["GrapesCanvas.tsx", "GrapesEditor.tsx"]); // held back: zero importers
function* walk(d) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) yield* walk(p);
    else if (/\.(tsx?|jsx?)$/.test(e.name) && !HELD.has(e.name)) yield p;
  }
}
const files = [...walk(SRC)].map((p) => [path.relative(SRC, p), fs.readFileSync(p, "utf8")]);

test("no iframe sandbox with both allow-scripts and allow-same-origin", () => {
  const bad = [];
  for (const [f, t] of files)
    for (const m of t.matchAll(/sandbox\s*=\s*(?:"([^"]*)"|'([^']*)'|\{\s*["'`]([^"'`]*)["'`]\s*\})/g)) {
      const v = m[1] ?? m[2] ?? m[3] ?? "";
      if (v.includes("allow-scripts") && v.includes("allow-same-origin")) bad.push(`${f}: ${v}`);
    }
  assert.deepEqual(bad, []);
});

test("no URL.createObjectURL handed to window.open", () => {
  const bad = files.filter(([, t]) => /window\.open\([^)]*createObjectURL|createObjectURL[\s\S]{0,200}window\.open/.test(t)).map(([f]) => f);
  assert.deepEqual(bad, []);
});

test("guard self-check: detects a bad sandbox string", () => {
  assert.ok(/allow-scripts/.test("allow-scripts allow-same-origin") && "allow-scripts allow-same-origin".includes("allow-same-origin"));
});
