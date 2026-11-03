import { parseDocument } from "htmlparser2";
import { isTag, isText, type Element, type ChildNode } from "domhandler";

const routeFor = (n: string) => (n === "site-home" ? "/" : n === "index" ? "/design" : `/${n}`);

function normStyle(s: string): string {
  return s.split(";").map((x) => x.trim()).filter(Boolean).map((x) => { const i = x.indexOf(":"); return `${x.slice(0, i).trim()}:${x.slice(i + 1).trim()}`; }).sort().join(";");
}

export function canon(node: ChildNode, out: string[] = [], pre = false): string[] {
  if (isText(node)) {
    if (pre) { out.push(JSON.stringify(node.data.replace(/\r\n?/g, "\n"))); return out; }       // line endings are not content: a CRLF checkout of the mockup must match the LF text the page renders
    const t = node.data.replace(/\s+/g, " ");
    if (t.trim() || t === " ") out.push(JSON.stringify(t === " " ? " " : t.trim() === t ? t : t));
    return out;
  }
  if (!isTag(node)) return out;
  const el = node as Element;
  if (el.name === "script") return out;
  // Functional attributes the product must add for real forms (password masking, autofill, OTP entry, busy state). Layout/markup stays 1:1.
  const FUNCTIONAL = new Set(["type", "autocomplete", "inputmode", "maxlength", "aria-label", "value", "disabled", "name", "required", "role", "aria-live"]);
  const functional = (k0: string) => { const k = k0.toLowerCase(); return ((el.name === "input" || el.name === "select" || el.name === "textarea") && FUNCTIONAL.has(k) && !(k === "type" && ["checkbox", "radio"].includes(el.attribs.type))) || (el.name === "button" && k === "disabled"); };
  const entries = Object.entries(el.attribs);
  const valid = (k: string) => /^[A-Za-z_:][-A-Za-z0-9_:.]*$/.test(k);
  const kept = entries.every(([k]) => valid(k)) ? entries : entries.findIndex(([k]) => k === "style") < 0 ? entries.filter(([k]) => valid(k)) : entries.slice(0, entries.findIndex(([k]) => k === "style") + 1);   // mirrors withoutSpill() in scripts/lib/convert.mjs
  const at = kept.filter(([k, v]) => !(k === "style" && !v.trim()) && !functional(k)).map(([k0, v]) => {
    const k = k0.toLowerCase();
    if (k === "href" && /^[a-z0-9-]+\.html/.test(v)) return `${k}=${routeFor(v.replace(/\.html.*$/, ""))}${v.includes("#") ? v.slice(v.indexOf("#")) : ""}`;
    if (k === "style") return `${k}=${normStyle(v)}`;
    if (el.name === "option" && k === "selected") return "selected";
    return `${k}=${v}`;
  }).sort();
  out.push(`<${el.name} ${at.join(" ")}>`);
  for (const c of el.children) canon(c, out, pre || el.name === "pre");
  out.push(`</${el.name}>`);
  return out;
}

/** Merge adjacent text tokens and drop whitespace-only text between block tags so formatting differences don't matter. */
export function tokens(html: string, root: (d: ReturnType<typeof parseDocument>) => ChildNode[]): string[] {
  const doc = parseDocument(html, { lowerCaseTags: false, lowerCaseAttributeNames: false, decodeEntities: true });
  const raw: string[] = [];
  for (const n of root(doc)) canon(n, raw);
  const out: string[] = [];
  for (const t of raw) {
    if (t.startsWith('"') && out.length && out[out.length - 1].startsWith('"')) out[out.length - 1] = JSON.stringify(JSON.parse(out[out.length - 1]) + JSON.parse(t));
    else out.push(t);
  }
  return out.filter((t) => !(t.startsWith('"') && JSON.parse(t).trim() === ""));
}

export function findAll(node: ChildNode | ReturnType<typeof parseDocument>, pred: (e: Element) => boolean): Element[] {
  const res: Element[] = [];
  const walk = (n: any) => { if (isTag(n) && pred(n)) res.push(n); for (const c of n.children ?? []) walk(c); };
  walk(node);
  return res;
}
