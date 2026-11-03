// Mockup HTML -> JSX. 1:1 markup; optional "wiring" binds regions to data without changing the markup:
//   rules: [{ sel, bind: "field" | text, bindAttr: { className: "field" }, attrs: { onClick: "expr" }, drop: ["value"], children: "<jsx/>", client: true,
//            rows: { name, as: "r", fields: { "relative selector": "field" | { text: "field", attrs: { class: "field" } } } } }]
// Values shown in the mockup become the SAMPLE data (default props), so the unwired render equals the mockup exactly.
import { isTag, isText } from "domhandler";
import { selectAll, selectOne } from "css-select";
import { textContent } from "domutils";
import render from "dom-serializer";

const innerHtml = (el) => render(el.children, { encodeEntities: "utf8" });
export const HELPERS = { textContent, selectOne, selectAll, innerHtml, collapse: (s) => s.replace(/\s+/g, " ").trim() };

export const SHELL_ONLY = true;
export const routeFor = (name) => (name === "site-home" ? "/" : name === "index" ? "/design" : `/${name}`);

const VOID = new Set(["area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"]);
const ATTR = { class: "className", for: "htmlFor", colspan: "colSpan", rowspan: "rowSpan", tabindex: "tabIndex", maxlength: "maxLength", readonly: "readOnly", autocomplete: "autoComplete",
  contenteditable: "contentEditable", inputmode: "inputMode", spellcheck: "spellCheck", crossorigin: "crossOrigin", srcset: "srcSet", charset: "charSet", novalidate: "noValidate", autofocus: "autoFocus", enctype: "encType",
  checked: "defaultChecked", value: "defaultValue", cellpadding: "cellPadding", cellspacing: "cellSpacing", "xlink:href": "xlinkHref", "xml:space": "xmlSpace" };
const NUMERIC = new Set(["rows", "cols", "size", "maxLength", "colSpan", "rowSpan", "tabIndex"]);
const BOOL = new Set(["disabled", "readonly", "required", "checked", "hidden", "open", "multiple", "autofocus", "novalidate", "selected"]);

/** An unquoted style value in a mockup (style=a:b;c:d e) spills into bogus attributes after `style`; browsers keep them, JSX cannot. Drop everything after `style` when any name is invalid. */
function withoutSpill(attribs) {
  const e = Object.entries(attribs);
  if (e.every(([k]) => /^[A-Za-z_:][-A-Za-z0-9_:.]*$/.test(k))) return e;
  const i = e.findIndex(([k]) => k === "style");
  return i < 0 ? e.filter(([k]) => /^[A-Za-z_:][-A-Za-z0-9_:.]*$/.test(k)) : e.slice(0, i + 1);
}
const camel = (s) => s.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
const attrName = (k) => ATTR[k] ?? (k.startsWith("data-") || k.startsWith("aria-") ? k : k.includes("-") ? camel(k) : k);
const collapse = (s) => s.replace(/\s+/g, " ").trim();

function styleObj(s) {
  const out = [];
  for (const part of s.split(";")) {
    const i = part.indexOf(":");
    if (i < 0) continue;
    const k = part.slice(0, i).trim(), v = part.slice(i + 1).trim();
    if (k) out.push(`${k.startsWith("--") ? JSON.stringify(k) : camel(k)}: ${JSON.stringify(v)}`);
  }
  return `{{ ${out.join(", ")} }}`;
}

/** b = binding for this element (from a top-level rule and/or row field spec); scope = "d" or the row variable. */
function attrs(el, tag, b, scope, ctx) {
  const out = [];
  const bound = new Set([...Object.keys(b?.attrs ?? {}), ...Object.keys(b?.bindAttr ?? {})]);
  for (const [k, v] of withoutSpill(el.attribs)) {
    if (/^on/.test(k)) continue;
    if (b?.drop?.includes(k)) continue;
    if (tag === "option" && k === "selected") continue;
    const name = attrName(k);
    if (bound.has(name)) continue;
    if (tag === "input" && k === "value" && ["checkbox", "radio"].includes(el.attribs.type)) { out.push(`value=${JSON.stringify(v)}`); continue; }
    if (k === "href" && /^[a-z0-9-]+\.html(#.*)?$/.test(v)) { out.push(`href=${JSON.stringify(routeFor(v.replace(/\.html.*$/, "")) + (v.includes("#") ? v.slice(v.indexOf("#")) : ""))}`); continue; }
    if (k === "style") out.push(`style=${styleObj(v)}`);
    else if (BOOL.has(k) && (v === "" || v === k)) out.push(name);
    else if (NUMERIC.has(name) && /^-?\d+$/.test(v)) out.push(`${name}={${v}}`);
    else out.push(`${name}=${JSON.stringify(v)}`);
  }
  for (const [k, expr] of Object.entries(b?.attrs ?? {})) if (expr !== null) out.push(`${k}={${expr}}`);
  for (const [k, field] of Object.entries(b?.bindAttr ?? {})) {
    const origKey = Object.keys(el.attribs).find((x) => attrName(x) === k);
    ctx.capture(scope, field, origKey ? el.attribs[origKey] : "");
    if (k === "style") out.push(`style={Object.fromEntries(${scope}.${field}.split(";").filter(Boolean).map((x) => { const i = x.indexOf(":"); return [x.slice(0, i).trim().replace(/-([a-z])/g, (_m, c) => c.toUpperCase()), x.slice(i + 1).trim()]; }))}`);
    else out.push(k === "dir" || k === "lang" || ctx.absentAttr.has(field) ? `${k}={${scope}.${field} || undefined}` : `${k}={${scope}.${field}}`);   // an attribute missing in some sample rows (or dir/lang) stays absent when empty
  }
  return out;
}

/** `key: "value"` pairs of an inline style, minus the properties listed in `skip` (used where some properties become data-driven). */
function styleEntries(s, skip = []) {
  const out = [];
  for (const part of s.split(";")) {
    const i = part.indexOf(":");
    if (i < 0) continue;
    const k = part.slice(0, i).trim(), v = part.slice(i + 1).trim();
    if (k && !skip.includes(k)) out.push(`${k.startsWith("--") ? JSON.stringify(k) : camel(k)}: ${JSON.stringify(v)}`);
  }
  return out;
}

const textExpr = (s) => (/[{}<>&"'\\\n]/.test(s) ? `{${JSON.stringify(s)}}` : s);

function ser(node, ctx, scope = "d", rowSpec = null, depth = 0) {
  const top0 = isTag(node) ? ctx.rules.get(node) : null;
  if (top0 && !top0.skip && (top0.before || top0.after) && !top0._split) {         // siblings are emitted outside any `show` condition on the same element
    const { before, after, ...rest } = top0;
    ctx.rules.set(node, { ...rest, _split: true });
    const body = ser(node, ctx, scope, rowSpec, depth);
    ctx.rules.set(node, top0);
    return `${before ?? ""}${body}${after ?? ""}`;
  }
  const show = isTag(node) ? (rowSpec?.get(node)?.show ?? ctx.rules.get(node)?.show) : null;
  if (!show) return serEl(node, ctx, scope, rowSpec, depth);
  const sc = rowSpec?.get(node) ? scope : "d";
  const inner = serEl(node, ctx, scope, rowSpec, depth);
  const cond = /^\w+$/.test(show) ? `${sc}.${show}` : show;                          // a data field of the page, or an expression such as showUnbuilt()
  return inner ? `{${cond} ? (${inner}) : null}` : "";
}

function serEl(node, ctx, scope = "d", rowSpec = null, depth = 0) {
  if (isText(node)) {
    const d = node.data;
    if (ctx.pre) return `{${JSON.stringify(d)}}`;
    if (!d.trim()) return d.length ? '{" "}' : "";
    return textExpr(d.replace(/\s+/g, " "));
  }
  if (!isTag(node)) return "";
  const tag = node.name;
  if (tag === "script") return "";
  if (tag === "style") return `<style dangerouslySetInnerHTML={{ __html: ${JSON.stringify(node.children.map((c) => c.data ?? "").join(""))} }} />`;
  const top = ctx.rules.get(node);
  if (top?.skip) return "";
  if (top?.swap !== undefined) {                       // { sel, swap: "<jsx/>", when: "expr" }: live component when `when` holds, otherwise the mockup element unchanged (1:1 by default)
    const { swap, when, ...rest } = top;
    ctx.rules.set(node, rest);
    const orig = ser(node, ctx, scope, rowSpec, depth);
    ctx.rules.set(node, top);
    return `{${when} ? (${swap}) : (${orig || "null"})}`;
  }
  if (top?.before || top?.after) {
    const { before, after, ...rest } = top;
    ctx.rules.set(node, rest);
    const body = ser(node, ctx, scope, rowSpec, depth);
    ctx.rules.set(node, top);
    return `${before ?? ""}${body}${after ?? ""}`;
  }
  if (top?.rowsSpec) return rowsBlock(node, top.rowsSpec, ctx, top.rowHits);
  const rowB = rowSpec?.get(node);
  const b = top || rowB ? { ...(top ?? {}), ...(rowB ?? {}) } : null;
  if (node.attribs.id === "dirToggle") { ctx.usesDirToggle = true; return node.attribs.title ? `<DirToggle title=${JSON.stringify(node.attribs.title)} />` : "<DirToggle />"; }
  const a = attrs(node, tag, b, rowB ? scope : "d", ctx);
  if (tag === "select") {
    const sel = node.children.filter(isTag).find((o) => o.name === "option" && "selected" in o.attribs);
    if (sel) a.push(`defaultValue=${JSON.stringify(sel.attribs.value ?? sel.children.map((c) => c.data ?? "").join(""))}`);
  }
  if (tag === "textarea") {
    const v = node.children.map((c) => c.data ?? "").join("");
    return `<textarea ${a.join(" ")} defaultValue=${JSON.stringify(v)} />`;
  }
  const open = a.length ? `<${tag} ${a.join(" ")}` : `<${tag}`;
  if (VOID.has(tag)) return `${open} />`;
  if (b?.wrap) {
    ctx.usesFragment = true;
    const sc = rowB ? scope : "d";
    const kids = node.children.map((c) => ser(c, ctx, scope, rowSpec, depth + 1)).join("");
    return `{${sc}.${b.wrap} ? (${open}>${kids}</${tag}>) : (<Fragment>${kids}</Fragment>)}`;
  }
  if (b?.list) {
    ctx.usesFragment = true;
    const sc = rowB ? scope : "d";
    // items are the element's children, or (listSel) its descendants matching listSel; listWrap = optional wrapper element around the items, rendered only when there are 2+ items
    const items = b.listSel ? selectAll(b.listSel, node).filter(isTag) : node.children.filter(isTag);
    const first = items[0];
    const fa = first ? attrs(first, first.name, null, "d", ctx) : [];
    const tpl = first ? `<${first.name}${fa.length ? " " + fa.join(" ") : ""}>{${ctx.textWrap ? `${ctx.textWrap}(x)` : "x"}}</${first.name}>` : "null";
    const list = `${sc}.${b.list}.split(",").filter(Boolean).map((x, j) => (<Fragment key={j}>{j > 0 && " "}${tpl}</Fragment>))`;
    const wrapEl = b.listWrap ? selectOne(b.listWrap, node) : null;
    if (!wrapEl) return `${open}>{${list}}</${tag}>`;
    const wa = attrs(wrapEl, wrapEl.name, null, "d", ctx);
    return `${open}>{${sc}.${b.list}.split(",").filter(Boolean).length > 1 ? (<${wrapEl.name}${wa.length ? " " + wa.join(" ") : ""}>{${list}}</${wrapEl.name}>) : (<Fragment>{${list}}</Fragment>)}</${tag}>`;
  }
  if (b?.html) {                                              // children are drawn from data (SVG charts, stacked bars): the string is produced by lib/charts.ts, which escapes all text
    const sc = rowB ? scope : "d";
    ctx.capture(sc, b.html, innerHtml(node));
    return `${open} dangerouslySetInnerHTML={{ __html: ${b.htmlExpr ?? `${sc}.${b.html}`} }} />`;
  }
  const field = b?.text ?? b?.bind;
  if (field) {
    const sc = rowB ? scope : "d";
    ctx.capture(sc, field, collapse(textContent(node)));
    const value = b.expr ?? `${sc}.${field}`;
    const dyn = ctx.textWrap && !b.expr ? `{${ctx.textWrap}(${value})}` : `{${value}}`;
    const ar = node.attribs["data-ar"];
    if (ar !== undefined) { ctx.usesT = true; return `${open}><T ar={${sc}.${field}Ar ?? ${JSON.stringify(ar)}}>{${value}}</T></${tag}>`; }
    return `${open}>${dyn}</${tag}>`;
  }
  if (b?.tail) {
    const sc = rowB ? scope : "d";
    let k = node.children.length;
    while (k > 0 && isText(node.children[k - 1])) k--;
    ctx.capture(sc, b.tail, node.children.slice(k).map((c) => c.data).join("").replace(/\s+/g, " "));
    const head = node.children.slice(0, k).map((c) => ser(c, ctx, scope, rowSpec, depth + 1)).join("");
    return `${open}>${head}{${b.tailExpr ?? `${sc}.${b.tail}`}}</${tag}>`;
  }
  if (b?.html) {
    const sc = rowB ? scope : "d";
    ctx.capture(sc, b.html, innerHtml(node));
    return `${open} dangerouslySetInnerHTML={{ __html: ${sc}.${b.html} }} />`;
  }
  if (b?.jsx) { if (b.sample && !rowB) Object.assign(ctx.sample.top, b.sample(node, HELPERS)); return `${open}>${b.jsx}</${tag}>`; }
  if (b?.children !== undefined) {
    const kids = b.children.includes("$SAMPLE") ? b.children.replaceAll("$SAMPLE", `<>${node.children.map((c) => ser(c, ctx, scope, rowSpec, depth + 1)).join("")}</>`) : b.children;
    return `${open}>${kids}</${tag}>`;
  }
  if (b?.own) {                                            // bind only the element's own text node(s); element children stay as in the mockup
    const sc = rowB ? scope : "d";
    const firstText = node.children.findIndex((c) => isText(c) && c.data.trim());
    const lead = firstText >= 0 && /^\s/.test(node.children[firstText].data);
    const w = ctx.textWrap ? (x) => `${ctx.textWrap}(${x})` : (x) => x;
    const kids = node.children.map((c, i) => (isText(c) ? (i === firstText ? `${lead ? '{" "}' : ""}{${w(`${sc}.${b.own}`)}}` : "") : ser(c, ctx, scope, rowSpec, depth + 1))).join("");
    return `${open}>${kids}${firstText < 0 ? `{${w(`${sc}.${b.own}`)}}` : ""}</${tag}>`;   // no own text in this node: the bound text goes after its element children
  }
  const ar = node.attribs["data-ar"];
  if (ar !== undefined && node.children.every(isText)) {
    ctx.usesT = true;
    return `${open}><T ar=${JSON.stringify(ar)}>{${JSON.stringify(collapse(node.children.map((c) => c.data).join("")))}}</T></${tag}>`;
  }
  const wasPre = ctx.pre;
  if (tag === "pre") ctx.pre = true;
  const inner = node.children.map((c) => ser(c, ctx, scope, rowSpec, depth + 1)).join("");
  ctx.pre = wasPre;
  return inner ? `${open}>${inner}</${tag}>` : `${open}></${tag}>`;
}

function rowsBlock(first, spec, ctx, hits) {
  const v = spec.as ?? "r";
  const siblings = (hits?.length ? hits : spec.hits ?? first.parent.children.filter((c) => isTag(c) && c.name === first.name)).filter((c) => !spec.sameClass || c.attribs.class === first.attribs.class);
  const fieldBindings = Object.entries(spec.fields).map(([sel, f]) => [sel, typeof f === "string" ? { text: f } : f]);
  const sample = [];
  for (const sib of siblings) {
    const row = {};
    for (const [sel, f] of fieldBindings) {
      const el = sel === "." ? sib : selectOne(sel, sib);
      if (f.show) row[f.show] = el ? "1" : "";
      if (f.has) row[f.has] = el ? "1" : "";
      if (f.wrap) row[f.wrap] = el ? "1" : "";
      if (!el) continue;
      if (f.text) row[f.text] = textContent(el).replace(/\s+/g, " ");      // keep edge spaces: the mockup compares text exactly
      if (f.own) row[f.own] = collapse(el.children.filter(isText).map((c) => c.data).join(""));
      if (f.html) row[f.html] = innerHtml(el);
      if (typeof f.sample === "function") Object.assign(row, f.sample(el, HELPERS));
      else if (f.sample) row[f.sample] = collapse(textContent(el));
      for (const [prop, field] of Object.entries(f.styleVar ?? {})) row[field] = (el.attribs.style ?? "").split(";").map((x) => x.split(":")).find(([k]) => k.trim() === prop)?.[1]?.trim() ?? "";
      if (f.list) row[f.list] = (f.listSel ? selectAll(f.listSel, el).filter(isTag) : el.children.filter(isTag)).map((c) => collapse(textContent(c))).join(",");
      for (const [attr, field] of Object.entries(f.attrs ?? {})) { row[field] = el.attribs[attr] ?? ""; if (el.attribs[attr] === undefined) ctx.absentAttr.add(field); }
    }
    for (const k of spec.extra ?? []) row[k] ??= "";            // loader-supplied string fields default to "" in the sample
    sample.push(row);
  }
  for (const [sel, f] of fieldBindings) {
    if (!f.sampleChildren) continue;
    const frags = siblings.map((sib) => {
      const el = sel === "." ? sib : selectOne(sel, sib);
      return `(<>${el ? el.children.map((c) => ser(c, ctx, "d", null, 1)).join("") : ""}</>)`;
    });
    ctx.usesFragment = true;
    ctx.decls.push(`const __SB_${spec.name}: React.ReactNode[] = [${frags.join(", ")}];`);
    f.children = f.children.replaceAll("$SAMPLE", `__SB_${spec.name}[i]`);
  }
  ctx.sample.rows[spec.name] = spec.samples ? sample.map((r, i) => ({ ...r, ...(spec.samples[i] ?? {}) })) : sample;
  if (spec.extra || spec.extraAbsent) ctx.rowExtra[spec.name] = [...(spec.extra ?? []), ...(spec.extraAbsent ?? [])];               // optional string fields the loader may add (not in the mockup)
  // template row = the sibling that contains the most field elements (so optional parts that the first row lacks, e.g. a "Draft" badge, are still generated)
  const covered = (s) => fieldBindings.filter(([sel]) => sel === "." || selectOne(sel, s)).length;
  const tmpl = siblings.reduce((best, s) => (covered(s) > covered(best) ? s : best), first);
  const rowSpec = new Map();
  if (spec.rowAttrs) rowSpec.set(tmpl, { attrs: spec.rowAttrs, drop: spec.rowDrop ?? [] });
  for (const [sel, f] of fieldBindings) {
    const el = sel === "." ? tmpl : selectOne(sel, tmpl);
    if (!el) { if (f.optional || f.has) continue; throw new Error(`rows field matches nothing: ${sel}`); }
    const bindAttr = {};
    for (const [attr, field] of Object.entries(f.attrs ?? {})) bindAttr[attrName(attr)] = field;
    if (f.has && !f.text && !f.show && !f.list && !f.wrap && !f.children && !f.attrExpr && !f.styleVar && !f.attrs) continue;
    rowSpec.set(el, { ...(rowSpec.get(el) ?? {}), ...(f.text ? { text: f.text } : {}), ...(f.html ? { html: f.html, ...(f.htmlExpr ? { htmlExpr: f.htmlExpr } : {}) } : {}), ...(f.jsx ? { jsx: f.jsx } : {}), ...(f.list ? { list: f.list, listSel: f.listSel, listWrap: f.listWrap } : {}), ...(f.own ? { own: f.own } : {}), ...(f.show ? { show: f.show } : {}), ...(f.wrap ? { wrap: f.wrap } : {}), ...(Object.keys(bindAttr).length ? { bindAttr } : {}), ...((f.raw || f.expr || f.styleVar || f.attrExpr) ? { attrs: { ...(rowSpec.get(el)?.attrs ?? {}), ...(f.raw ?? {}), ...(f.expr ?? {}), ...(f.styleVar ? { style: `{ ${[...styleEntries(el.attribs.style ?? "", Object.keys(f.styleVar)), ...Object.entries(f.styleVar).map(([prop, field]) => `${camel(prop)}: ${v}.${field}`)].join(", ")} }` } : {}), ...(f.attrExpr ?? {}) } } : {}), ...(f.drop || f.styleVar ? { drop: [...(f.drop ?? []), ...(f.styleVar ? ["style"] : [])] } : {}), ...(f.children !== undefined ? { children: f.children } : {}) });
  }
  const rowCapture = ctx.capture;
  ctx.capture = () => {};                                   // row samples were captured above across all rows
  // serialise the first row without re-applying the rows rule to itself
  const savedFirst = ctx.rules.get(first), savedTmpl = ctx.rules.get(tmpl);
  ctx.rules.delete(first); ctx.rules.delete(tmpl);
  const inner = ser(tmpl, ctx, v, rowSpec, 0);
  ctx.rules.set(first, savedFirst); if (tmpl !== first) ctx.rules.set(tmpl, savedTmpl);
  ctx.capture = rowCapture;
  const withKey = inner.replace(/^<([a-zA-Z0-9]+)/, "<$1 key={i}");
  return `{${spec.src ?? `d.${spec.name}`}.map((${v}, i) => (${withKey}))}`;
}

function find(node, pred) {
  if (isTag(node) && pred(node)) return node;
  for (const c of node.children ?? []) { const r = find(c, pred); if (r) return r; }
  return null;
}

function compileRules(doc, wiring) {
  const map = new Map();
  for (const rule of wiring?.rules ?? []) {
    const hits = selectAll(rule.sel, doc);
    if (!hits.length) throw new Error(`wiring rule matches nothing: ${rule.sel}`);
    if (rule.rows) {
      map.set(hits[0], { ...(map.get(hits[0]) ?? {}), rowsSpec: rule.rows, rowHits: hits });
      for (const h of hits.slice(1)) map.set(h, { skip: true });
    } else {
      const { sel, ...rest } = rule;
      for (const n of hits) map.set(n, { ...(map.get(n) ?? {}), ...rest });
    }
  }
  return map;
}

function mkCtx(doc, wiring) {
  const sample = { top: {}, rows: {} };
  return {
    absentAttr: new Set(), usesT: false, usesDirToggle: false, usesFragment: false, pre: false, rules: compileRules(doc, wiring), sample, textWrap: wiring?.textWrap, decls: [], rowExtra: {},
    capture(scope, field, value) { if (scope === "d") sample.top[field] = value; },
  };
}

export function convertChrome(doc, wiring) {
  const ctx = mkCtx(doc, wiring);
  Object.assign(ctx.sample.top, wiring?.extraData ?? {});
  const sb = find(doc, (n) => n.name === "nav" && (n.attribs.class ?? "").split(" ").includes("sb"));
  const hd = find(doc, (n) => n.name === "header" && (n.attribs.class ?? "").split(" ").includes("hd"));
  const sbInner = sb.children.map((c) => {
    if (isTag(c) && c.name === "a" && (c.attribs.class ?? "").split(" ").includes("nav")) {
      const href = c.attribs.href.replace(/\.html$/, "");
      const inner = c.children.map((x) => ser(x, ctx)).join("");
      const nav = `<NavA name=${JSON.stringify(href)} href=${JSON.stringify(routeFor(href))} active={active}>${inner}</NavA>`;
      const sh = ctx.rules.get(c)?.show;
      return sh ? `{d.${sh} ? (${nav}) : null}` : nav;
    }
    return ser(c, ctx);
  }).join("");
  const hdInner = hd.children.map((c) => ser(c, ctx)).join("");
  const imports = [`import { NavA } from "@/components/NavA";`, ctx.usesT ? `import { T } from "@/components/T";` : "", ctx.usesDirToggle ? `import { DirToggle } from "@/components/DirToggle";` : "", ...(wiring?.imports ?? [])].filter(Boolean).join("\n");
  const decl = `export type ChromeData = { ${Object.keys(ctx.sample.top).map((k) => `${k}: string`).join("; ")} };\nexport const CHROME_SAMPLE: ChromeData = ${JSON.stringify(ctx.sample.top, null, 1)};\n`;
  return { tsx: `${imports}\n\n${decl}\nexport function Sidebar({ active, d = CHROME_SAMPLE }: { active: string; d?: ChromeData }) {\n  return (\n    <nav className="sb">${sbInner}</nav>\n  );\n}\n\nexport function Header({ d = CHROME_SAMPLE }: { d?: ChromeData }) {\n  return (\n    <header className="hd">${hdInner}</header>\n  );\n}\n` };
}

const tsType = (rows, extra = []) => {
  const keys = [...new Set(rows.flatMap((r) => Object.keys(r)))];
  return `{ ${[...keys.map((k) => `${k}${rows.every((r) => k in r) ? "" : "?"}: string`), ...extra.filter((k) => !keys.includes(k)).map((k) => `${k}?: string`)].join("; ")} }`;
};

export function convertPage(doc, name, wiring) {
  const ctx = mkCtx(doc, wiring);
  const title = (find(doc, (n) => n.name === "title")?.children[0]?.data ?? name).trim();
  const body = find(doc, (n) => n.name === "body");
  const main = find(doc, (n) => n.name === "main" && (n.attribs.class ?? "").split(" ").includes("page"));
  const sb = find(doc, (n) => n.name === "nav" && (n.attribs.class ?? "").split(" ").includes("sb"));
  const shell = Boolean(main && sb);
  const root = shell ? main : body;
  Object.assign(ctx.sample.top, wiring?.extraData ?? {});
  const inner = root.children.map((c) => ser(c, ctx)).join("");
  // drawers and modals sit next to .app in the mockup (outside <main>); they belong to the page, so they are rendered right after it
  const app = find(doc, (n) => n.name === "div" && (n.attribs.class ?? "").split(" ").includes("app"));
  const extras = shell ? body.children.filter((c) => isTag(c) && c !== app && c.name !== "script").map((c) => ser(c, ctx)).join("") : "";
  const wrapper = shell ? (extras ? `<><main className="page">${inner}</main>${extras}</>` : `<main className="page">${inner}</main>`) : `<>${inner}</>`;
  const imports = [wiring?.client ? '"use client";' : "", ctx.usesFragment ? 'import { Fragment } from "react";' : "", wiring?.live ? 'import { useEffect, useState } from "react";' : "", ctx.usesT ? `import { T } from "@/components/T";` : "", ctx.usesDirToggle ? `import { DirToggle } from "@/components/DirToggle";` : "", ...(wiring?.imports ?? [])].filter(Boolean).join("\n");
  const wired = Object.keys(ctx.sample.top).length || Object.keys(ctx.sample.rows).length || Object.keys(wiring?.extraArrays ?? {}).length;
  let dataDecl = "";
  let sig = "()";
  if (wired) {
    const rowTypes = [...Object.entries(ctx.sample.rows).map(([k, rows]) => `${k}: ${tsType(rows, ctx.rowExtra[k])}[]`), ...Object.entries(wiring?.extraArrays ?? {}).map(([k, t]) => `${k}: ${t}[]`)];
    const topTypes = Object.keys(ctx.sample.top).map((k) => `${k}: string`);
    dataDecl = `export type Data = { ${[...topTypes, ...rowTypes].join("; ")} };\nexport const SAMPLE: Data = ${JSON.stringify({ ...ctx.sample.top, ...ctx.sample.rows, ...Object.fromEntries(Object.keys(wiring?.extraArrays ?? {}).map((k) => [k, []])) }, null, 1)};\n\n`;
    sig = (wiring?.derive || wiring?.live) ? "({ d: d0 = SAMPLE }: { d?: Data })" : "({ d = SAMPLE }: { d?: Data })";
  }
  const livePre = wiring?.live ? "  const [d, setD] = useState<Data>(d0);\n  useEffect(() => { setD(d0); }, [d0]);\n" : "";
  const prelude = livePre + (wiring?.prelude ? `${wiring.prelude}\n` : "") + (wired && wiring?.derive ? `  const d: Data = ${wiring.derive};\n` : "");
  const decls = ctx.decls.length ? ctx.decls.join("\n") + "\n\n" : "";
  const tsx = `${imports}${imports ? "\n" : ""}${wiring?.preamble ? wiring.preamble + "\n" : ""}${dataDecl}${decls}export default function Content${sig} {\n${prelude}  return (\n    ${wrapper}\n  );\n}\n`;
  return { tsx, shell, title, bodyClass: body?.attribs.class ?? "", wired: Boolean(wired), loader: wiring?.loader ?? false, query: Boolean(wiring?.query), searchParams: Boolean(wiring?.searchParams), search: Boolean(wiring?.search) };
}
