# HTML mockup to Next.js code maker

**Exercised in the product?** Used in the product as a build step: 38 pages are generated from mockups, 33 of them wired to live data.

## What it does
A converter turns each static HTML mockup into a React page with the same markup, classes and text, and a small wiring language binds regions of it to data. A test renders every unwired page and compares its element tree to the mockup, so the design is kept 1:1.

## When to use it
A designer or a model produces finished static screens and you need them as a working app without redrawing them.

## How it works
* See `PROCESS.md` for the step-by-step method. `scripts/mockup-to-tsx.mjs` is the generator, `scripts/lib/convert.mjs` the engine and wiring DSL, `scripts/sync-design.mjs` copies the stylesheet byte for byte, and `tests/fidelity.test.tsx` is the 1:1 check.
* `examples/` has two complete screens end to end: `surveys` (a server-loaded list with filters) and `approvals` (a client page with state, bulk actions and writes): mockup, wiring file, loader, generated page, tests, and the backend router.

## Files

The Python package was renamed to `app` (imports look like `from app.core.verifier import ...`; the source tree is `backend/src/app/`, which contains its own `app/` sub-package) and the Postgres roles are `app_api` (runtime) and `app_owner` (tables and migrations). Capitalised brand names were replaced with `Acme`.

**src/ (copied as is; names and identifiers redacted)**

* `frontend/scripts/lib/convert.mjs`  <- `frontend/scripts/lib/convert.mjs`
* `frontend/scripts/mockup-to-tsx.mjs`  <- `frontend/scripts/mockup-to-tsx.mjs`
* `frontend/scripts/sync-design.mjs`  <- `frontend/scripts/sync-design.mjs`
* `frontend/tests/convert-swap.test.ts`  <- `frontend/tests/convert-swap.test.ts`
* `frontend/tests/fidelity.test.tsx`  <- `frontend/tests/fidelity.test.tsx`
* `frontend/tests/helpers/normalize.ts`  <- `frontend/tests/helpers/normalize.ts`
* `frontend/vitest.config.ts`  <- `frontend/vitest.config.ts`

**examples/ (product-specific; shown as examples only)**

* `backend/src/app/app/routers/approvals.py`  <- `backend/src/app/app/routers/approvals.py`
* `backend/src/app/app/routers/surveys.py`  <- `backend/src/app/app/routers/surveys.py`
* `docs/design/approvals.html`  <- `docs/design/approvals.html`
* `docs/design/assets/app.css`  <- `docs/design/assets/app.css`
* `docs/design/surveys.html`  <- `docs/design/surveys.html`
* `frontend/app/(generated)/approvals/content.tsx`  <- `frontend/app/(generated)/approvals/content.tsx`
* `frontend/app/(generated)/approvals/page.tsx`  <- `frontend/app/(generated)/approvals/page.tsx`
* `frontend/app/(generated)/surveys/content.tsx`  <- `frontend/app/(generated)/surveys/content.tsx`
* `frontend/app/(generated)/surveys/page.tsx`  <- `frontend/app/(generated)/surveys/page.tsx`
* `frontend/components/ShellChrome.tsx`  <- `frontend/components/ShellChrome.tsx`
* `frontend/lib/approvals-model.ts`  <- `frontend/lib/approvals-model.ts`
* `frontend/lib/format.ts`  <- `frontend/lib/format.ts`
* `frontend/lib/loaders/_util.ts`  <- `frontend/lib/loaders/_util.ts`
* `frontend/lib/loaders/approvals.ts`  <- `frontend/lib/loaders/approvals.ts`
* `frontend/lib/loaders/surveys.ts`  <- `frontend/lib/loaders/surveys.ts`
* `frontend/lib/loaders/util.ts`  <- `frontend/lib/loaders/util.ts`
* `frontend/scripts/wiring/_chrome.mjs`  <- `frontend/scripts/wiring/_chrome.mjs`
* `frontend/scripts/wiring/approvals.mjs`  <- `frontend/scripts/wiring/approvals.mjs`
* `frontend/scripts/wiring/surveys.mjs`  <- `frontend/scripts/wiring/surveys.mjs`
* `frontend/tests/approvals.test.tsx`  <- `frontend/tests/approvals.test.tsx`
* `frontend/tests/surveys.test.tsx`  <- `frontend/tests/surveys.test.tsx`

**docs/**

* `FRONTEND_WIRING.md`  <- `docs/FRONTEND_WIRING.md`
* `LANDING_HANDOFF.md`  <- `docs/app-landing-handoff/docs/LANDING_HANDOFF.md`
* `PHASES.md`  <- `docs/PHASES.md`
* `PROD_HANDOFF.md`  <- `docs/app-prod-handoff/docs/PROD_HANDOFF.md`

**Written for this package (not copied)**

* `PROCESS.md`
* `docs/package-scripts.json`

## Depends on repository files that were NOT copied

Generated from the imports in the copied files. Each is needed (or must be replaced by your own equivalent) before this wires into a project.

* `backend/src/app/adapters/queue_pg.py`
* `backend/src/app/app/access.py`
* `backend/src/app/app/audience.py`
* `backend/src/app/app/audit.py`
* `backend/src/app/app/billing.py`
* `backend/src/app/app/deps.py`
* `backend/src/app/app/routers/feedback360.py`
* `backend/src/app/app/routers/privacy.py`
* `backend/src/app/core/approvals.py`
* `backend/src/app/core/conversation.py`
* `backend/src/app/core/logic.py`
* `backend/src/app/core/sanitize.py`
* `backend/src/app/core/studio.py`
* `backend/src/app/core/survey_schema.py`
* `backend/src/app/db/repos/__init__.py`
* `backend/src/app/db/repos/approvals.py`
* `backend/src/app/db/repos/collectors.py`
* `backend/src/app/db/repos/cx_cases.py`
* `backend/src/app/db/repos/feedback_cycles.py`
* `backend/src/app/db/repos/invitations.py`
* `backend/src/app/db/repos/surveys.py`
* `backend/src/app/db/repos/users.py`
* `frontend/app/(generated)/loading.tsx`
* `frontend/app/(generated)/routes.json`
* `frontend/components/AvatarMenu.tsx`
* `frontend/components/DirToggle.tsx`
* `frontend/components/I18n.tsx`
* `frontend/components/NavA.tsx`
* `frontend/components/OrgMenu.tsx`
* `frontend/components/Shell.tsx`
* `frontend/components/T.tsx`
* `frontend/lib/api-server.ts`
* `frontend/lib/client-api.ts`
* `frontend/lib/decode.ts`
* `frontend/lib/loaders/${name}  (unresolved)`
* `frontend/lib/menu-data.ts`
* `frontend/lib/messages.ts`
* `frontend/lib/people.ts`
* `frontend/lib/uuid.ts`
* `frontend/loading  (unresolved)`
* `frontend/scripts/content  (unresolved)`
* `frontend/tests/msw.ts`

## External dependencies

* @testing-library/react
* @vitejs/plugin-react
* asyncpg
* css-select
* dom-serializer
* domhandler
* domutils
* fastapi
* htmlparser2
* msw
* next
* pydantic
* react
* react-dom
* vitest

## Known limits and notes
* The two mockups (`surveys`, `approvals`), their generated pages, loaders and tests carry NEUTRAL SAMPLE DATA (invented people such as Alex Morgan and Jordan Lee, "Sample Survey A" to "G", "Sector A", "Example Service"). Replace them with your own screens. `app.css` contains no sample copy or names; it does carry the product's colour palette as CSS variables (`--brand` and its shades), which you will want to change for your own brand.
* The process documents were cleaned of account identifiers, but they still describe the original product's phases; use them as a template for your own plan.
* The converter does not generate loaders, endpoints or tests: those are written by hand following the documented pattern.

## Changes made after extraction

* Sample names, titles and copy in `examples/docs/design/surveys.html` and `approvals.html` were replaced with neutral placeholders (100 replacements), and the same map was applied to the pages generated from them, `ShellChrome.tsx`, the loader, `format.ts` and the two tests so the example set stays consistent: person names, avatar initials, survey titles, the property name in the message preview (and its Arabic sentence, now "[ar] ..."), "Real estate" and "WhatsApp".
* Left as they are: the generic interface vocabulary (menu items, column headings, buttons), the sample figures (3,906, 94% ...), dates, the "GST" time-zone label (it is produced by `lib/approvals-model.ts`) and the "عربي" language-toggle label.
* The tests compare against these strings, so they were updated with the same map, but they were not run.

## What was redacted or neutralised in these copies

* arabic_T_attr: 32
* arabic_data_attr: 62
* brand_domain: 10
* brand_name: 15
* brand_name_upper: 4
* client_name: 5
* email: 12
* owner_name: 15
* rename:app/(site): 2
* rename:landing-mockup: 3

No `.env` file, key, token, respondent data or account identifier is included. See the top-level `SECRET_SCAN.md`.
