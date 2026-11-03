# Interface translation and right-to-left layout (six languages)

**Exercised in the product?** Used in the product. English and Arabic are written by hand next to each screen; Urdu, Hindi, Russian and Filipino are machine-drafted and flagged as needing native review.

## What it does
A language switch that sets the document direction (right-to-left for Arabic and Urdu), message tables per screen with English as the fallback for any missing key, and a `<T ar="...">` component for text leaves taken from HTML mockups. Layout uses logical CSS properties (`inline-start`, `padding-inline-start`) so no separate right-to-left stylesheet is needed.

## When to use it
You ship an interface in several languages including right-to-left ones.

## How it works
* `lib/lang.ts`: the language list and which are right-to-left. `components/I18n.tsx`: provider and `useLang`. `lib/i18n/registry.ts` + `locales.ts`: where a table for a language is found, falling back to English per key. `lib/i18n/catalog.ts`: the English source of every table (used by tests and the export script). `scripts/i18n-export.ts`: exports strings for a translator.
* `src/frontend/lib/messages.ts` is REWRITTEN with placeholder strings to show the format (`useMsg`, `{placeholder}` variables).

## Files

The Python package was renamed to `app` (imports look like `from app.core.verifier import ...`; the source tree is `backend/src/app/`, which contains its own `app/` sub-package) and the Postgres roles are `app_api` (runtime) and `app_owner` (tables and migrations). Capitalised brand names were replaced with `Acme`.

**src/ (copied as is; names and identifiers redacted)**

* `frontend/components/DirToggle.tsx`  <- `frontend/components/DirToggle.tsx`
* `frontend/components/I18n.tsx`  <- `frontend/components/I18n.tsx`
* `frontend/components/T.tsx`  <- `frontend/components/T.tsx`
* `frontend/lib/decode.ts`  <- `frontend/lib/decode.ts`
* `frontend/lib/dictionary.ts`  <- `frontend/lib/dictionary.ts`
* `frontend/lib/i18n/catalog.ts`  <- `frontend/lib/i18n/catalog.ts`
* `frontend/lib/i18n/leaves.ts`  <- `frontend/lib/i18n/leaves.ts`
* `frontend/lib/i18n/locales.ts`  <- `frontend/lib/i18n/locales.ts`
* `frontend/lib/i18n/registry.ts`  <- `frontend/lib/i18n/registry.ts`
* `frontend/lib/lang.ts`  <- `frontend/lib/lang.ts`
* `frontend/scripts/i18n-export.ts`  <- `frontend/scripts/i18n-export.ts`

**tests/**

* `frontend/tests/arabic-coverage.test.tsx`  <- `frontend/tests/arabic-coverage.test.tsx`
* `frontend/tests/i18n.test.tsx`  <- `frontend/tests/i18n.test.tsx`

**examples/ (product-specific; shown as examples only)**

* `frontend/lib/i18n/ur.ts`  <- `frontend/lib/i18n/ur.ts`

**docs/**

* `I18N.md`  <- `docs/I18N.md`

**Written for this package (not copied)**

* `examples/frontend/lib/i18n/xx/messages-1.ts`
* `src/frontend/lib/messages.ts`

## Depends on repository files that were NOT copied

Generated from the imports in the copied files. Each is needed (or must be replaced by your own equivalent) before this wires into a project.

* `frontend/components/distribute/strings.ts`
* `frontend/components/interview/strings.ts`
* `frontend/lib/authoring-messages.ts`
* `frontend/lib/format.ts`
* `frontend/lib/i18n/fil.ts`
* `frontend/lib/i18n/hi.ts`
* `frontend/lib/i18n/ru.ts`
* `frontend/lib/i18n/site/ar.ts`
* `frontend/lib/i18n/site/en.ts`
* `frontend/lib/i18n/site/ur.ts`
* `frontend/lib/i18n/ur/authoring-1.ts`
* `frontend/lib/i18n/ur/authoring-2.ts`
* `frontend/lib/i18n/ur/d.ts`
* `frontend/lib/i18n/ur/distribute-1.ts`
* `frontend/lib/i18n/ur/distribute-2.ts`
* `frontend/lib/i18n/ur/e-reports.ts`
* `frontend/lib/i18n/ur/messages-1.ts`
* `frontend/lib/i18n/ur/messages-2.ts`
* `frontend/lib/i18n/ur/misc.ts`
* `frontend/lib/i18n/ur/respondent.ts`
* `frontend/lib/messages-e.ts`
* `frontend/lib/messages-reports.ts`
* `frontend/lib/messages.ts`
* `frontend/lib/msg-d.ts`
* `frontend/lib/people.ts`
* `frontend/lib/runner/strings.ts`

## External dependencies

* @testing-library/react
* react
* vitest

## Known limits and notes
* ALL CATALOGUE STRINGS WERE REPLACED WITH PLACEHOLDERS. The original tables hold product copy in six languages (about 590 KB) and were not copied.
* `lib/i18n/catalog.ts` and `ur.ts` import tables that were not copied; they show the wiring only. The tests read the generated pages and the real catalogues, so they will not pass here without them.
* Machine-drafted translations need a native speaker before use.

## What was redacted or neutralised in these copies

* brand_name: 2

No `.env` file, key, token, respondent data or account identifier is included. See the top-level `SECRET_SCAN.md`.
