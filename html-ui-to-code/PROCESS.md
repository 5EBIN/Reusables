# Repeating the mockup-to-code process on a new project

The idea: design finished static HTML screens first, then turn each one into a working page without redrawing it. The mockup stays the source of truth for the
markup; code only adds data and behaviour on top. A test proves the unwired page still equals the mockup.

## What is code and what is process
* Code: `src/frontend/scripts/mockup-to-tsx.mjs` (generator), `scripts/lib/convert.mjs` (HTML to JSX engine and the wiring language), `scripts/sync-design.mjs`
  (stylesheet copy), `tests/fidelity.test.tsx` (1:1 check), `tests/convert-swap.test.ts` (an example test for the wiring language), `tests/helpers/normalize.ts`.
* Process (documents): `docs/FRONTEND_WIRING.md` (the wiring language and the rules for every wired page), `docs/PHASES.md`, and the two handoff documents
  (`PROD_HANDOFF.md`, `LANDING_HANDOFF.md`) which are phase-by-phase prompts written for a coding assistant.

## Steps
1. **Set up the folders.** `design/` holds one `<name>.html` per screen plus `design/assets/app.css` (one shared stylesheet). The app has `app/(generated)/` (never edited by
   hand) and `app/app.css`. Add the scripts from `docs/package-scripts.json` to your `package.json` and install `htmlparser2`, `css-select`, `domutils`, `dom-serializer`, `domhandler`.
2. **Design the screens as HTML.** One shared chrome (sidebar and header) is taken from one mockup (the generator reads `design/surveys.html` for it; change that in
   `mockup-to-tsx.mjs`), and each screen's `<main class="page">` becomes the page. Use real-looking sample values: they become the default data.
3. **Sync the stylesheet.** `npm run sync-design` copies `design/assets/app.css` to `app/app.css` verbatim. A test asserts the two files are byte-identical; never edit the copy.
4. **Generate.** `npm run gen-pages` writes `app/(generated)/<name>/{content.tsx,page.tsx}` and `routes.json`. Mapping: `<name>.html` -> route `/<name>`; `index` -> `/design`;
   a page marked not-an-app-page (your marketing site) is excluded from the conversion and built by hand.
5. **Check fidelity.** `npm test` renders every generated page with its sample data and compares the element tree, classes, text and attributes with the mockup.
   Fix the converter, not the generated file, if a page differs.
6. **Wire a page.** Add `scripts/wiring/<name>.mjs` (see `examples/frontend/scripts/wiring/surveys.mjs`, `approvals.mjs`). Each rule picks elements with a CSS selector and binds
   text, attributes, repeated rows, conditional parts or handlers. Wiring may change only text, attribute values, repetition, conditions and handlers; extra elements are
   allowed only if they render nothing in the default sample.
7. **Write the loader.** `lib/loaders/<name>.ts` has a pure `toView(apiData)` that maps the API's JSON to the strings the mockup shows ("3,906", "94%", "2 h ago"), and a
   `load()` that calls the API from the server with the session. Values shown to users come from the endpoint, never from the mockup sample.
8. **Add the endpoint** if the backend lacks it (`examples/backend/.../routers/surveys.py` and `approvals.py`): a router file, authorised per role, row-level security on any new table.
   Writes from the browser go through one proxy route (the BFF) that adds the CSRF header and cookies, so no token reaches client code.
9. **Test the page.** A test for the mapping (empty, zero, very long text, hostile text, right-to-left text), a render with live-looking data, a check that the loader sends the
   session, and every handler. See `examples/frontend/tests/surveys.test.tsx` and `approvals.test.tsx`.
10. **Run the gate.** `npm run verify` (sync, generate, typecheck, tests) must pass before you commit. Commit generated files with the change that caused them.

## When the wiring language lacks something
Extend `scripts/lib/convert.mjs` in a backwards-compatible way and add a test next to `convert-swap.test.ts`. Do not hand-edit generated files.

## Pitfalls the original project hit
* An unquoted `style=a:b` in a mockup spills into invalid attributes in JSX; the converter drops them on both sides of the comparison.
* Drawers and modals placed next to the app container in the mockup must be rendered after `<main>`.
* In tests, quote attribute values in selectors (`[data-panel="i"]`), or jsdom reads a bare `i` as a flag.
* Keep every number a page shows traceable to an endpoint; do not let a mockup's sample number reach production.
