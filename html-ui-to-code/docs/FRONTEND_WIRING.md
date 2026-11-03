# Wiring a mockup page to the product

Every page under `frontend/app/(generated)/<name>/content.tsx` is GENERATED from `docs/design/<name>.html` by `frontend/scripts/mockup-to-tsx.mjs`.
Never edit generated files. To make a page live you add `frontend/scripts/wiring/<name>.mjs` (+ a loader, + backend endpoints if missing, + tests).

## The 1:1 rule
The unwired render of `<Content />` MUST equal the mockup (test `tests/fidelity.test.tsx`, all 38 pages). The values the mockup shows become the `SAMPLE`
default props, extracted automatically. Wiring may only change: text, attribute values, repetition of rows, conditional rendering and handlers.
Functional attributes on inputs/buttons (type, autocomplete, disabled, name, aria-label, inputmode, maxlength) are allowed (see `tests/helpers/normalize.ts`).
Extra elements (error notices, forms for new states) are allowed ONLY when they render nothing in the default sample (use `before`/`after` with a conditional).

## Wiring DSL (`scripts/wiring/<name>.mjs`, default export)
```js
export default {
  loader: true,                 // page.tsx becomes async and calls load() from frontend/lib/loaders/<name>.ts -> Content d={data}
  client: true,                 // "use client" (needs state/handlers); then loaders cannot be used - fetch via the BFF in the component
  imports: ['import ... from "..."'], preamble: "module-level code", prelude: "code inside the component before return (hooks)",
  extraData: { flag: "" },      // extra string fields on Data that are not bound to text
  rules: [
    { sel: "css selector (css-select)", bind: "field" },                          // replace the element's text with {d.field}
    { sel: "...", bindAttr: { className: "cls" } },                               // attribute from data (sample = mockup value)
    { sel: "...", attrs: { onClick: "handler", disabled: "busy" }, drop: ["value"] },   // raw JSX expressions / remove attributes
    { sel: "...", children: "<jsx/>" },                                           // replace children
    { sel: "...", before: "{...}", after: "{cond && <div/>}" },                   // siblings (must render nothing by default)
    { sel: "...", show: "field" },                                                // render only if d.field is truthy
    { sel: "tbody tr", rows: { name: "items", as: "r", fields: {                  // repeat the FIRST matching row for d.items[]
        "td:nth-child(2) b": "title",                                              // text -> r.title
        ".badge": { text: "status", attrs: { class: "statusCls" } },               // text + attribute
        "td:nth-child(3)": { list: "tags" },                                       // comma-separated string -> repeated first child (e.g. badges)
        "td:nth-child(4) svg": { show: "spark", optional: true },                  // conditional element (optional if absent in some rows)
        "td:nth-child(2) a": { wrap: "link", attrs: { href: "href" }, optional: true },  // wrapper element that may be absent
      } } },
  ],
};
```
Data is always strings (the view-model the mockup shows: "3,906", "94%", "2 h ago"). The loader maps API -> view-model using `lib/format.ts`.
See `scripts/wiring/surveys.mjs` + `lib/loaders/surveys.ts` (server loader) and `scripts/wiring/auth.mjs` (client form) as the reference implementations.
If a construct is missing from the DSL, extend `scripts/lib/convert.mjs` in a backwards-compatible way and cover it with a test.

## Required for every wired page
1. `scripts/wiring/<name>.mjs` + `lib/loaders/<name>.ts` (pure `toView(apiData, now)` + `load()` using `api()` from `lib/api-server.ts`).
2. Tests (vitest, `tests/<name>.test.tsx`): mapping API->view-model (including empty, zero, long/hostile text, Arabic text), render with live data, loader sends the session token + org (MSW + mocked `next/headers`, see `tests/surveys.test.tsx`), every handler/interaction (see `tests/auth.test.tsx`), error states.
3. Writes go through the BFF: `post(bff("v1/..."), body)` from `lib/client-api.ts` (CSRF header + cookies handled). Never put tokens in client code.
4. Arabic/RTL: messages via `lib/messages.ts` (add keys in EN + AR); text with `data-ar` is translated by `<T>` automatically.
5. If the backend lacks an endpoint the page needs, ADD it (backend rules below). No page may show invented numbers: every figure comes from an endpoint.
6. Keep `npm run verify` green (sync-design, gen-pages, typecheck, vitest) from `frontend/`.

## Backend rules (when you add endpoints)
- Routers auto-register: put `router`/`public`/`api` in `backend/src/app/app/routers/<name>.py`. Use `org_ctx` + `o.tx(ROLES)`; RLS on every new org table (`app.apply_org_rls`), grants minimal; new migration in YOUR assigned number range; append-only where the spec says so.
- Pure logic goes in `backend/src/app/core/` (no DB/vendors). Numbers shown to users are computed by code. Min group size 5. No LLM output without the verifier.
- Tests: unit + integration (incl. tenant isolation, role checks, replay/idempotency for writes, Arabic case), `@pytest.mark.security` for authz/isolation. `ruff check` + `lint-imports` clean.
- Do not edit existing migrations. Do not xfail security tests.

## Parallel work rules
- Use your own database: `export SV_DB=app_<yourname>`; run `SV_DB=$SV_DB ./scripts/dev-db.sh && (cd backend && SV_DB=$SV_DB alembic upgrade head)` and pytest with the same env var.
  The frontend BFF talks to `BACKEND_URL` (default http://127.0.0.1:8000); unit tests mock it with MSW, so you never need a running API for vitest.
- Do NOT run `scripts/phase-done.sh`, do not edit `docs/PHASES.md`, do not push. Commit on your worktree branch with clear messages; the lead merges.
- Touch only: your pages' wiring/loaders/tests, your backend routers/core/migrations/tests, and (carefully, backwards-compatibly) `scripts/lib/convert.mjs`.

## DSL extensions added by the workspace-core pages (all backwards compatible; see `scripts/lib/convert.mjs`)
- `loader: "params"`: `page.tsx` passes `await searchParams` to `load(params)` (URL-driven filters, see `surveys`, `approvals`). `client: true` + a loader is fine: the server page loads, the client `Content` receives `d`.
- `textWrap: "m"`: every bound text is rendered as `{m(value)}`. With `lib/decode.ts` a loader encodes translatable sentences as `enc("key", arg0, ...)` and the client translates them (`useDecode()`); plain strings pass through, unknown keys never render a message chosen by content. Call `stripMarks()` on API data at the top of `toView`.
- `derive: "<expr>"`: the component signature becomes `({ d: d0 })` and `const d: Data = <expr>` is computed after `prelude` (client-side overrides of loader data: range toggles, filters, selected row).
- Row field options: `own: "field"` (bind only the element's own text node, keep child elements), `raw: { attr: "jsxExpr" }` and `drop: [...]` (per-row expressions such as `onClick`/`checked`), `listSel` + `listWrap` (list of descendants, optional wrapper rendered only for 2+ items), and rows option `extra: ["id", ...]` (optional string fields the loader may add that are not in the mockup).
- `rows` samples come from the rule's own matches (not "all siblings with the same tag"); the template row is the matching row that contains the most field elements, so optional parts that the first row lacks (e.g. a "Draft" badge) are still generated.
- `before` / `after` siblings are emitted outside a `show` condition on the same element. `bindAttr: { style: "field" }` parses a CSS string at runtime; `dir`/`lang` bindings omit the attribute when empty.
- `own` with no text node in the sample appends the bound text after the element's children (used for cells that hold either a badge or a dash).
- Gotcha: in jsdom `querySelector('[data-panel=i]')` treats a bare `i` as the case-insensitivity flag; quote attribute values in tests (`[data-panel="i"]`).

## DSL additions (analysis & reporting group)
- `search: true` (with `loader: true`): `page.tsx` passes the awaited `searchParams` to `load(sp)`.
- `{ sel, html: "field", htmlExpr?: "expr" }` (also as a rows field): children are drawn from a string (SVG charts, stacked bars). The SAMPLE is the mockup's inner HTML, so the unwired page is unchanged. Builders live in `lib/charts.ts` and escape all text. Bind the *parent* when the element is an `<svg>` (the builders return the whole `<svg>`).
- `{ sel, tail: "field", tailExpr?: "expr" }`: replaces only the trailing text node of an element (e.g. a checkbox label whose count comes from an endpoint).
- rows fields accept `expr: { onClick: "() => ..." }` (raw JSX expressions using the row variable and `i`) and `drop: [...]`; the rows sample now follows the rule's own matches (not every same-tag sibling).
- Drawers and modals that the mockup places next to `.app` are rendered after `<main>`; the fidelity test compares them too. Unquoted `style=a:b c` values in mockups spill into bogus attributes; they are dropped on both sides.
- Report pages share `scripts/wiring/_report.mjs` (filter chips, tab strip, exports, saved views), `lib/loaders/reports.ts` (scope/period/survey, soft failures) and `components/ReportBar.tsx`.
