# Narrative verifier: model-written text can only show numbers by reference

**Exercised in the product?** Used in the product (report summaries and the answers to "Ask your survey").

## What it does
Checks text drafted by a model before anyone sees it. Every number must be a `{{ref:id}}` placeholder that code resolves from computed values. A bare digit (Latin, Arabic-Indic or fullwidth), a number written in words, or a causal or trend word that is not backed by a computed change makes the whole draft fail.

## When to use it
A model writes prose around figures you compute, and a wrong or invented number would be harmful.

## How it works
* `verify(text, claims)` parses placeholders, rejects any other number form after normalising digits (`core/normalize_ar.py`), and renders each claim from the computed value with `render_claim`.
* `core/narrative.py` builds the claims from computed results. The fuzz test feeds many hostile phrasings (English and Arabic) and requires every unreferenced number to be rejected.

## Files

The Python package was renamed to `app` (imports look like `from app.core.verifier import ...`; the source tree is `backend/src/app/`, which contains its own `app/` sub-package) and the Postgres roles are `app_api` (runtime) and `app_owner` (tables and migrations). Capitalised brand names were replaced with `Acme`.

**src/ (copied as is; names and identifiers redacted)**

* `backend/src/app/core/narrative.py`  <- `backend/src/app/core/narrative.py`
* `backend/src/app/core/normalize_ar.py`  <- `backend/src/app/core/normalize_ar.py`
* `backend/src/app/core/verifier.py`  <- `backend/src/app/core/verifier.py`

**tests/**

* `backend/tests/fixtures/stress/verifier_fuzz.py`  <- `backend/tests/fixtures/stress/verifier_fuzz.py`
* `backend/tests/unit/test_verifier_fuzz.py`  <- `backend/tests/unit/test_verifier_fuzz.py`

## Depends on repository files that were NOT copied

Generated from the imports in the copied files. Each is needed (or must be replaced by your own equivalent) before this wires into a project.

* none

## External dependencies

* pytest

## Known limits and notes
* It checks numbers and some wording, not whether a sentence is true or well written.
* The word lists for trend and causal words are English and Arabic only.

## What was redacted or neutralised in these copies

* nothing needed redacting

No `.env` file, key, token, respondent data or account identifier is included. See the top-level `SECRET_SCAN.md`.
