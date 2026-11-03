# NavDrawer: slide-over menu for narrow screens

**Exercised in the product?** Used in the product (the signed-in app below 1100 px).

## What it does
A menu button that opens the sidebar as a slide-over from the start side, closing on a link, Escape or the backdrop, moving focus in and back, and working right-to-left.

## When to use it
A fixed sidebar layout needs a mobile version without a separate component tree.

## How it works
* `components/NavDrawer.tsx` toggles a `nav-open` class on the closest `.app` element and manages focus; the CSS in `docs/nav-drawer.css` does the layout (`position: fixed`, `inset-inline-start`, `translateX`, with a right-to-left override and a reduced-motion rule).
* `examples/Shell.tsx` shows where it is mounted.

## Files

The Python package was renamed to `app` (imports look like `from app.core.verifier import ...`; the source tree is `backend/src/app/`, which contains its own `app/` sub-package) and the Postgres roles are `app_api` (runtime) and `app_owner` (tables and migrations). Capitalised brand names were replaced with `Acme`.

**src/ (copied as is; names and identifiers redacted)**

* `frontend/components/NavDrawer.tsx`  <- `frontend/components/NavDrawer.tsx`

**tests/**

* `frontend/e2e/nav-drawer.spec.ts`  <- `frontend/e2e/nav-drawer.spec.ts`
* `frontend/tests/nav-drawer.test.tsx`  <- `frontend/tests/nav-drawer.test.tsx`

**examples/ (product-specific; shown as examples only)**

* `frontend/components/Shell.tsx`  <- `frontend/components/Shell.tsx`

**Written for this package (not copied)**

* `docs/nav-drawer.css`

## Depends on repository files that were NOT copied

Generated from the imports in the copied files. Each is needed (or must be replaced by your own equivalent) before this wires into a project.

* `frontend/components/I18n.tsx`
* `frontend/components/ImpersonationBanner.tsx`
* `frontend/components/MfaGate.tsx`
* `frontend/components/ShellChrome.tsx`
* `frontend/e2e/support/auth.ts`
* `frontend/lib/loaders/chrome.ts`
* `frontend/lib/messages.ts`

## External dependencies

* @playwright/test
* @testing-library/react
* react
* vitest

## Known limits and notes
* It assumes the markup classes `.app`, `.sb` (sidebar), `.hd` (header) and a CSS variable `--sb` for the sidebar width.
* The button label comes from the message key `nav_menu` through `useMsg()`.

## What was redacted or neutralised in these copies

* nothing needed redacting

No `.env` file, key, token, respondent data or account identifier is included. See the top-level `SECRET_SCAN.md`.
