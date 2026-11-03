// Contrast check of the design tokens in src/styles/globals.css, in both themes. WCAG 2.x ratios.
//   node scripts/contrastCheck.mjs          prints every pair and exits 1 if any required pair fails
// Text must reach 4.5:1; borders of controls, icons and the focus ring must reach 3:1. Hairlines that only separate (--line, --line2) are decorative: they are
// printed with their ratio and never fail the run (WCAG does not ask for 3:1 on them), but nothing that marks the edge of a control may use them: that is --ctl.
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const CSS = fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "src", "styles", "globals.css"), "utf8").replace(/\r\n/g, "\n")

/** The declarations of the block that starts with `selector {` (the first one in the file). */
function block(selector, from = 0) {
  const start = CSS.indexOf(selector + " {", from)
  if (start < 0) throw new Error(`no block ${selector}`)
  const open = CSS.indexOf("{", start)
  const close = CSS.indexOf("}", open)
  return CSS.slice(open + 1, close)
}
const decls = body => Object.fromEntries([...body.matchAll(/--([a-z0-9-]+)\s*:\s*([^;]+);/g)].map(m => [m[1], m[2].trim()]))

const light = decls(block(':root, [data-theme="light"]'))
const darkExplicit = decls(block('[data-theme="dark"]'))
const darkOs = decls(block(':root:not([data-theme="light"])', CSS.indexOf("prefers-color-scheme")))

function parse(v) {
  let m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(v)
  if (m) { const h = m[1].length === 3 ? [...m[1]].map(c => c + c).join("") : m[1]; return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)).concat(1) }
  m = /^rgba?\(([^)]+)\)$/.exec(v)
  if (m) { const p = m[1].split(",").map(x => parseFloat(x)); return [p[0], p[1], p[2], p[3] ?? 1] }
  throw new Error(`cannot read colour ${v}`)
}
/** `fg` laid over opaque `bg`. */
const over = (fg, bg) => [0, 1, 2].map(i => fg[i] * fg[3] + bg[i] * (1 - fg[3])).concat(1)
const lum = ([r, g, b]) => { const f = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4 }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b) }
const ratio = (a, b) => { const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x); return (hi + 0.05) / (lo + 0.05) }

const KINDS = ["accent", "pass", "fail", "warn", "info", "ai", "locked"]
const SURFACES = ["bg", "card", "sunk"]

/** [label, fgToken, bg (token, or {token, tint, over}), minimum, required]. */
function pairs() {
  const out = []
  const text = (label, fg, bg) => out.push({ label, fg, bg, min: 4.5, required: true })
  const edge = (label, fg, bg) => out.push({ label, fg, bg, min: 3, required: true })
  for (const s of SURFACES) {
    for (const t of ["t1", "t2", "t3"]) text(`text ${t} on ${s}`, t, s)
    for (const k of KINDS) text(`${k} text on ${s}`, k, s)
    edge(`control border (ctl) on ${s}`, "ctl", s)
    edge(`focus ring (info) on ${s}`, "info", s)
  }
  text("button: accent-fg on accent", "accent-fg", "accent")
  text("danger button: accent-fg on fail", "accent-fg", "fail")
  for (const k of KINDS.filter(k => k !== "accent")) {
    text(`pill ${k}: text on its 10% tint over card`, k, { token: k, alpha: 0.1, over: "card" })
    text(`pill ${k}: text on its 10% tint over bg`, k, { token: k, alpha: 0.1, over: "bg" })
  }
  text("pill neutral: t2 on hover over card", "t2", { token: "hover", over: "card" })
  text("count warn: text on its 15% tint over card", "warn", { token: "warn", alpha: 0.15, over: "card" })
  text("count fail: text on its 15% tint over card", "fail", { token: "fail", alpha: 0.15, over: "card" })
  text("selected row: t1 on sel over card", "t1", { token: "sel", over: "card" })
  edge("switch on: knob (accent-fg) on track (accent)", "accent-fg", "accent")
  edge("switch off: knob (t3) on track (sunk)", "t3", "sunk")
  edge("accent on bg (links, selected tab underline)", "accent", "bg")
  for (const s of SURFACES) out.push({ label: `hairline (line2) on ${s}`, fg: "line2", bg: s, min: 3, required: false })
  for (const s of SURFACES) out.push({ label: `hairline (line) on ${s}`, fg: "line", bg: s, min: 3, required: false })
  return out
}

function evaluate(name, tokens) {
  const get = t => parse(tokens[t] ?? (() => { throw new Error(`${name}: no --${t}`) })())
  const surface = t => { const c = get(t); return c[3] < 1 ? over(c, get("bg")) : c }
  const results = []
  for (const p of pairs()) {
    const bg = typeof p.bg === "string" ? surface(p.bg) : (() => {
      const base = surface(p.bg.over)
      const tint = get(p.bg.token)
      return over(p.bg.alpha ? [...tint.slice(0, 3), p.bg.alpha] : tint, base)
    })()
    results.push({ theme: name, ...p, ratio: ratio(over(get(p.fg), bg), bg) })
  }
  return results
}

const all = [...evaluate("light", light), ...evaluate("dark", darkExplicit)]
const failures = all.filter(r => r.required && r.ratio < r.min)
const decorative = all.filter(r => !r.required)
const same = JSON.stringify(darkExplicit) === JSON.stringify(darkOs)

const fmt = r => `${r.ratio.toFixed(2).padStart(5)}:1  (needs ${r.min})  ${r.theme.padEnd(5)}  ${r.label}`
if (process.argv.includes("--all")) all.forEach(r => console.log((r.ratio >= r.min ? "ok   " : r.required ? "FAIL " : "deco ") + fmt(r)))
console.log(`checked ${all.length} pairs in 2 themes: ${all.filter(r => r.required).length - failures.length} of ${all.filter(r => r.required).length} required pairs pass`)
if (!same) { console.log("FAIL the two dark blocks differ (the OS block and [data-theme=dark] must hold the same values)"); for (const k of new Set([...Object.keys(darkExplicit), ...Object.keys(darkOs)])) if (darkExplicit[k] !== darkOs[k]) console.log(`       --${k}: ${darkOs[k]} vs ${darkExplicit[k]}`) }
for (const r of failures) console.log("FAIL " + fmt(r))
console.log(`decorative hairlines (not required, shown for the record): ${decorative.map(r => `${r.theme} ${r.label} ${r.ratio.toFixed(2)}`).join("; ")}`)
process.exit(failures.length || !same ? 1 : 0)
