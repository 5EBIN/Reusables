# Small-group suppression and anonymity rules

**Exercised in the product?** Used in the product (reports, engagement results, 360 reviews, Ask your data).

## What it does
Hides any group with fewer than five answers, adds complementary suppression when hiding one cell would let a reader subtract it back from a total, and merges or hides small peer groups in 360 reports.

## When to use it
You publish aggregates to people who must not be able to identify individuals.

## How it works
* `core/anonymity.py`: pure functions on lists of counts; no database or framework.

## Files

The Python package was renamed to `app` (imports look like `from app.core.verifier import ...`; the source tree is `backend/src/app/`, which contains its own `app/` sub-package) and the Postgres roles are `app_api` (runtime) and `app_owner` (tables and migrations). Capitalised brand names were replaced with `Acme`.

**src/ (copied as is; names and identifiers redacted)**

* `backend/src/app/core/anonymity.py`  <- `backend/src/app/core/anonymity.py`

**tests/**

* `backend/tests/unit/test_anonymity.py`  <- `backend/tests/unit/test_anonymity.py`

## Depends on repository files that were NOT copied

Generated from the imports in the copied files. Each is needed (or must be replaced by your own equivalent) before this wires into a project.

* none

## External dependencies

* hypothesis
* pytest

## Known limits and notes
* The threshold of 5 is a constant in the original product; some callers read it from organisation settings.

## What was redacted or neutralised in these copies

* client_name: 3

No `.env` file, key, token, respondent data or account identifier is included. See the top-level `SECRET_SCAN.md`.
