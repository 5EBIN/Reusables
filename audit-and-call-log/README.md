# Audit log and model-call log

**Exercised in the product?** Used in the product.

## What it does
An audit row for each sensitive write (`audit(...)`), and one `ai_calls` row per model answer (task, model, tokens, cost, attempt, whether it was re-asked) plus a per-day total in `ai_usage`. Structured logs carry a hashed organisation id and never any text or key.

## When to use it
You must be able to explain who did what and what each model call cost.

## How it works
* `app/audit.py` and `db/repos/audit_log.py`; `db/repos/ai_budget.py` (`record_call`); `core/obs.py` (metrics registry and `hash_ref`).

## Files

The Python package was renamed to `app` (imports look like `from app.core.verifier import ...`; the source tree is `backend/src/app/`, which contains its own `app/` sub-package) and the Postgres roles are `app_api` (runtime) and `app_owner` (tables and migrations). Capitalised brand names were replaced with `Acme`.

**src/ (copied as is; names and identifiers redacted)**

* `backend/src/app/app/audit.py`  <- `backend/src/app/app/audit.py`
* `backend/src/app/core/obs.py`  <- `backend/src/app/core/obs.py`
* `backend/src/app/db/repos/ai_budget.py`  <- `backend/src/app/db/repos/ai_budget.py`
* `backend/src/app/db/repos/audit_log.py`  <- `backend/src/app/db/repos/audit_log.py`

**tests/**

* `backend/tests/integration/test_observability.py`  <- `backend/tests/integration/test_observability.py`
* `backend/tests/unit/test_ai_rate_and_log.py`  <- `backend/tests/unit/test_ai_rate_and_log.py`
* `backend/tests/unit/test_obs.py`  <- `backend/tests/unit/test_obs.py`

## Depends on repository files that were NOT copied

Generated from the imports in the copied files. Each is needed (or must be replaced by your own equivalent) before this wires into a project.

* `backend/src/app/adapters/llm_openai_compat.py`
* `backend/src/app/adapters/llm_tasks.py`
* `backend/src/app/app/__init__.py`
* `backend/src/app/app/ai_guard.py`
* `backend/src/app/app/routers/privacy.py`
* `backend/src/app/app/settings.py`

## External dependencies

* asyncpg
* httpx
* pydantic
* pytest

## Known limits and notes
* The tables' migrations were not copied. The columns are visible in the SQL inside the repository files.

## What was redacted or neutralised in these copies

* api_key: 1
* bearer_token: 1
* brand_name: 1

No `.env` file, key, token, respondent data or account identifier is included. See the top-level `SECRET_SCAN.md`.
