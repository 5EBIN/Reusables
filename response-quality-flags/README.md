# Careless-response and data-quality flags

**Exercised in the product?** Used in the product, run on demand from the quality screen (not on every submission).

## What it does
Rules that flag straight-lining, speeding and similar patterns. Flags mark responses; they do not delete or exclude them.

## When to use it
You collect survey responses and want a transparent, rule-based quality check.

## How it works
* `core/quality.py`: pure rules over a response's answers and timings. `db/repos/quality_rules.py` stores per-organisation thresholds. `app/routers/quality.py` runs them.

## Files

The Python package was renamed to `app` (imports look like `from app.core.verifier import ...`; the source tree is `backend/src/app/`, which contains its own `app/` sub-package) and the Postgres roles are `app_api` (runtime) and `app_owner` (tables and migrations). Capitalised brand names were replaced with `Acme`.

**src/ (copied as is; names and identifiers redacted)**

* `backend/src/app/app/routers/quality.py`  <- `backend/src/app/app/routers/quality.py`
* `backend/src/app/core/quality.py`  <- `backend/src/app/core/quality.py`
* `backend/src/app/db/repos/quality_rules.py`  <- `backend/src/app/db/repos/quality_rules.py`

**tests/**

* `backend/tests/integration/test_panels_quality.py`  <- `backend/tests/integration/test_panels_quality.py`
* `backend/tests/unit/test_quality.py`  <- `backend/tests/unit/test_quality.py`

## Depends on repository files that were NOT copied

Generated from the imports in the copied files. Each is needed (or must be replaced by your own equivalent) before this wires into a project.

* `backend/src/app/app/audit.py`
* `backend/src/app/app/deps.py`
* `backend/src/app/app/routers/surveys.py`
* `backend/src/app/db/__init__.py`
* `backend/src/app/db/repos/__init__.py`
* `backend/src/app/db/repos/answers.py`
* `backend/src/app/db/repos/responses.py`
* `backend/src/app/db/repos/surveys.py`

## External dependencies

* asyncpg
* fastapi
* pytest

## Known limits and notes
* Panel verification flags (identity, device checks) are typed in by staff, not computed here.

## What was redacted or neutralised in these copies

* nothing needed redacting

No `.env` file, key, token, respondent data or account identifier is included. See the top-level `SECRET_SCAN.md`.
