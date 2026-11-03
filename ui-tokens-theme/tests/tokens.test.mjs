// R2: the token layer. What Tailwind emits for a colour class, that the old token names are all aliases of defined tokens, and that the retired colours are gone.
//   node --test tests/tokens.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const ROOT = path.resolve(import.meta.dirname, "..");
const css = fs.readFileSync(path.join(ROOT, "src", "styles", "globals.css"), "utf8").replace(/\r\n/g, "\n");
const config = createRequire(import.meta.url)(path.join(ROOT, "tailwind.config.js"));
const colors = config.theme.extend.colors;

test("a colour class reads its CSS variable, and an opacity modifier mixes it with transparent", () => {
  assert.equal(colors.accent.DEFAULT({}), "var(--accent)");
  assert.equal(colors.accent.DEFAULT({ opacityValue: "1" }), "var(--accent)");
  assert.equal(colors.fail({ opacityValue: "0.15" }), "color-mix(in srgb, var(--fail) calc(0.15 * 100%), transparent)");
  assert.equal(colors.line2({ opacityValue: "var(--tw-border-opacity)" }), "color-mix(in srgb, var(--line2) calc(var(--tw-border-opacity) * 100%), transparent)");
});

test("no hex value lives in the Tailwind config: the slate and indigo palette is gone, every colour is a variable", () => {
  const seen = [];
  (function walk(o) { for (const v of Object.values(o)) { if (typeof v === "function") seen.push(v({})); else walk(v); } })(colors);
  assert.ok(seen.length > 25);
  for (const c of seen) assert.match(c, /^var\(--[a-z0-9-]+\)$/);
  assert.doesNotMatch(fs.readFileSync(path.join(ROOT, "tailwind.config.js"), "utf8"), /#[0-9a-f]{3,6}\b/i);
});

/** The `--name: value;` declarations of the block that opens with `selector {`. */
function declarations(selector, from = 0) {
  const at = css.indexOf(selector + " {", from);
  assert.ok(at >= 0, selector);
  const body = css.slice(css.indexOf("{", at) + 1, css.indexOf("}", at));
  return Object.fromEntries([...body.matchAll(/--([a-z0-9-]+)\s*:\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]));
}
const light = declarations(':root, [data-theme="light"]');
const dark = declarations('[data-theme="dark"]');
const darkByOs = declarations(':root:not([data-theme="light"])', css.indexOf("prefers-color-scheme"));
const aliases = declarations(":root, [data-theme]");

test("light and dark define the same tokens, and the OS dark block equals the explicit dark block", () => {
  assert.deepEqual(Object.keys(dark).sort(), Object.keys(light).sort());
  assert.deepEqual(darkByOs, dark);
  for (const t of ["bg", "card", "sunk", "t1", "t2", "t3", "accent", "accent-fg", "pass", "fail", "warn", "info", "ai", "neutral", "locked", "ctl", "line", "line2", "scrim"]) assert.ok(light[t] && dark[t], t);
});

test("the demo's values are the ones in use (dark: the olive palette with lime accent; light: white cards, blue accent)", () => {
  assert.deepEqual([dark.bg, dark.card, dark.accent, dark.t1, dark.fail], ["#0c0c0a", "#151511", "#4ade80", "#eaeadd", "#f0714f"]);
  assert.deepEqual([light.bg, light.card, light.accent, light.t1, light.fail], ["#f5f5f7", "#ffffff", "#0066cc", "#1d1d1f", "#c4132a"]);
});

test("every old token name is an alias of a token that exists, and none of them holds a colour of its own", () => {
  const OLD = ["bg2", "bg3", "surface", "surface2", "border", "border2", "border-active", "text", "text-muted", "text-dim", "green", "green-mid", "green-light", "green-glow", "green-dim", "green-subtle", "green-subtle2", "green-line", "amber", "amber-dim", "stall", "stall-dim", "blue"];
  for (const name of OLD) {
    assert.ok(aliases[name], `--${name} is still defined`);
    assert.doesNotMatch(aliases[name], /#[0-9a-f]{3,8}\b|rgba?\(/i, `--${name} holds no colour literal`);
    for (const used of aliases[name].matchAll(/var\(--([a-z0-9-]+)\)/g)) assert.ok(light[used[1]], `--${name} points at --${used[1]}, which exists`);
  }
});

test("the retired colours are gone from the source: #2db370 everywhere, and the slate/indigo hexes in styles and config", () => {
  const files = [];
  (function walk(d) { for (const e of fs.readdirSync(d, { withFileTypes: true })) { const p = path.join(d, e.name); if (e.isDirectory()) walk(p); else if (/\.(tsx?|css)$/.test(e.name)) files.push(p); } })(path.join(ROOT, "src"));
  const withBrandGreen = files.filter((f) => /#2db370/i.test(fs.readFileSync(f, "utf8"))).map((f) => path.relative(ROOT, f).replace(/\\/g, "/"));
  // the landing page keeps its own palette until R9; the design canvases and the generated-app template render INSIDE other documents, where our variables do not exist
  const allowed = withBrandGreen.filter((f) => /components\/landing\/|design-editor\/(GrapesCanvas|DesignCanvas|blockDefs)|lib\/editor\/failsafeTemplate/.test(f));
  assert.deepEqual(withBrandGreen, allowed, "#2db370 outside landing / design canvases / the generated template");
  for (const hex of ["#6366f1", "#4f46e5", "#818cf8", "#0f172a", "#1e293b", "#334155", "#475569", "#64748b", "#94a3b8", "#cbd5e1", "#e2e8f0", "#f1f5f9"]) assert.ok(!css.toLowerCase().includes(hex), `${hex} in globals.css`);
});
