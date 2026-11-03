# Typed query plan: the model plans, code compiles and runs

**Exercised in the product?** Used in the product (the "Ask your data" screen). Checked against a real model on 24 Oct 2026: 30 of 32 golden questions.

## What it does
A pattern for letting a language model answer questions about your data without letting it write SQL. The model returns a typed `QueryPlan` (metric, dimensions, filters, period). Code validates the plan, compiles it to parameterised SQL from a fixed registry of metrics, runs it, and returns one of four outcomes: ANSWER, CLARIFY (ask the user something), CANT_YET (the data cannot answer it) or REFUSE (off-topic or asks for individual people).

## When to use it
You have a database of facts and want natural-language questions over it, with no free-form SQL and a small-group rule enforced in code.

## How it works
* `core/ask_plan.py` builds the strict JSON schema the model must follow (`plan_schema`) and converts the raw answer into a validated `QueryPlan` (`to_query_plan`). `plan_key` caches plans by question and catalogue fingerprint.
* `core/query_plan.py` holds the typed plan (`QueryPlan`, `Filter`, `TextMatch`, `DateRange`), the `Outcome` enum, the date-range rules (at most three years) and the minimum group size (`MIN_N = 5`). The metric and dimension ids come from `core/plan_vocabulary.py`: a two-member PLACEHOLDER in `src/`; the original product's six metrics and eight dimensions are in `examples/`.
* `app/analytics/compiler.py` turns a plan into SQL with bound parameters, capped at 5,000 rows. `app/analytics/engine.py` runs it with a timeout and applies per-row suppression of small groups.
* `core/period.py` resolves words such as "last month" into dates in code, so the model never does date arithmetic.

## Files

The Python package was renamed to `app` (imports look like `from app.core.verifier import ...`; the source tree is `backend/src/app/`, which contains its own `app/` sub-package) and the Postgres roles are `app_api` (runtime) and `app_owner` (tables and migrations). Capitalised brand names were replaced with `Acme`.

**src/ (copied as is; names and identifiers redacted)**

* `backend/src/app/app/analytics/compiler.py`  <- `backend/src/app/app/analytics/compiler.py`
* `backend/src/app/app/analytics/engine.py`  <- `backend/src/app/app/analytics/engine.py`
* `backend/src/app/core/ask_plan.py`  <- `backend/src/app/core/ask_plan.py`
* `backend/src/app/core/period.py`  <- `backend/src/app/core/period.py`
* `backend/src/app/core/query_plan.py`  <- `backend/src/app/core/query_plan.py` (MetricId and DimId removed)
* `backend/src/app/core/plan_vocabulary.py`  <- NEW placeholder, written for this package

**tests/**

* `backend/tests/integration/test_ask_data.py`  <- `backend/tests/integration/test_ask_data.py`
* `backend/tests/unit/test_ask_plan.py`  <- `backend/tests/unit/test_ask_plan.py`
* `backend/tests/unit/test_query_plan.py`  <- `backend/tests/unit/test_query_plan.py`

**examples/ (product-specific; shown as examples only)**

* `backend/src/app/app/analytics/__init__.py`  <- `backend/src/app/app/analytics/__init__.py`
* `backend/src/app/app/analytics/catalogue.py`  <- `backend/src/app/app/analytics/catalogue.py`
* `backend/src/app/app/analytics/semantic.py`  <- `backend/src/app/app/analytics/semantic.py`
* `backend/tests/golden_ask.py`  <- `backend/tests/golden_ask.py`
* `backend/src/app/core/plan_vocabulary.py`  <- the original `MetricId` and `DimId` enums, split out of `core/query_plan.py`

## Depends on repository files that were NOT copied

Generated from the imports in the copied files. Each is needed (or must be replaced by your own equivalent) before this wires into a project.

* `backend/src/app/adapters/llm_tasks.py`
* `backend/src/app/app/ai_guard.py`
* `backend/src/app/core/rag.py`
* `backend/src/app/core/redact.py`
* `backend/src/app/db/__init__.py`
* `backend/src/app/db/repos/surveys.py`

## External dependencies

* asyncpg
* pydantic
* pytest

## Known limits and notes
* The vocabulary was split out: `src/.../core/plan_vocabulary.py` is a PLACEHOLDER (`MetricId` has COUNT and AVERAGE, `DimId` has GROUP and DAY). The original six metrics and eight dimensions are in `examples/.../core/plan_vocabulary.py`; copy that over the placeholder to get the original behaviour, or write your own. The plan types, the schema builder and the compiler follow whatever is defined there. `compiler.py` and the examples' `semantic.py` still reference the original members (for example `MetricId.NPS`).
* `app/analytics/compiler.py` and `engine.py` assume the original tables (responses, answers, surveys). The query shapes are the part to rewrite for another schema.
* The metric registry (`semantic.py`), the catalogue builder that tells the model what exists (`catalogue.py`) and the golden questions (`golden_ask.py`) are under `examples/`: they are product-specific, shown so you can see the shape a registry takes.
* The prompt that asks the model for a plan lives in `llm-provider-adapter/examples/backend/src/app/adapters/llm_task_definitions.py` (`PLAN_INSTRUCTION`). `tests/.../test_ask_plan.py` imports that module to register the schemas.

## Changes made after extraction

* `core/query_plan.py`: the `MetricId` and `DimId` enums were removed and replaced by `from app.core.plan_vocabulary import DimId, MetricId`, which re-exports them so existing imports keep working. Nothing else in the file changed.
* Smoke-tested with the example vocabulary first on the path: `QueryPlan(metric="NPS", dimensions=["MONTH"])` validates (6 metrics, 8 dimensions).

## What was redacted or neutralised in these copies

* nothing needed redacting

No `.env` file, key, token, respondent data or account identifier is included. See the top-level `SECRET_SCAN.md`.
