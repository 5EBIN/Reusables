# LLM provider adapter, task layer, guard and budget

**Exercised in the product?** Used in the product with the OpenAI-compatible adapter on OpenRouter. `llm_anthropic.py` is NOT used in production (the production settings check requires the OpenAI-compatible provider); it exists for experiments and is covered by unit tests.

## What it does
A hand-written `httpx` client for an OpenAI-compatible API (OpenRouter) behind a port (`LLMClient` in `core/ports.py`), with retries and backoff, a circuit breaker per model, a process-wide concurrency limit, strict JSON-schema output with one re-ask, redaction before sending, `<data>` wrapping of untrusted text, and a fake provider for tests. Around it, `app/ai_guard.py` is the gate in front of every model call (per-minute limits, an on/off switch per organisation, daily token and USD caps, plan credits) and the meter behind it (every answer recorded with tokens, cost and model).

## When to use it
You call a hosted model from a multi-tenant app and need cost caps, failure handling and a record of every call.

## How it works
* `adapters/llm_openai_compat.py`: the HTTP client. 401 and 402 are treated as an operator problem (logged, never retried); other 4xx are not retried; 429 and 5xx back off.
* `adapters/llm_guard.py`: `CircuitBreaker` (5 failures opens it for 60 seconds, then one probe) and `AiGate` (concurrency).
* `adapters/llm_tasks.py`: the GENERIC base: result and error types, the strict-schema helpers (`strict_compatible`, `_obj`), the untrusted-data wrapper (`_wrap`), the result collector, and `LLMTasks._call` (validate, one re-ask, record). It knows no tasks: they are registered in three dictionaries (`SCHEMAS`, `TASKS`, `OUTPUTS`, all empty here) and the task methods come from a mixin. The original product's 11 tasks live in `examples/` (see below).
* `examples/backend/src/app/adapters/llm_task_definitions.py`: the 11 product tasks (plan, classify, themes, narrate, interview, facts, benchmarks, cluster labels, rag, sentiment, survey draft): their JSON schemas, token limits, output models, prompts, and a `ProductTasks(LLMTasks)` mixin with the task methods. Importing it registers them in the base. Replace it with your own tasks.
* `app/ai_guard.py` + `db/repos/ai_budget.py`: `gate` (limits, switch, caps, credits) and `metered` (records usage even if the route fails afterwards).
* `adapters/llm_fake.py`: a deterministic stand-in so no test calls a real model.

## Files

The Python package was renamed to `app` (imports look like `from app.core.verifier import ...`; the source tree is `backend/src/app/`, which contains its own `app/` sub-package) and the Postgres roles are `app_api` (runtime) and `app_owner` (tables and migrations). Capitalised brand names were replaced with `Acme`.

**src/ (copied as is; names and identifiers redacted)**

* `backend/src/app/adapters/llm_anthropic.py`  <- `backend/src/app/adapters/llm_anthropic.py`
* `backend/src/app/adapters/llm_fake.py`  <- `backend/src/app/adapters/llm_fake.py`
* `backend/src/app/adapters/llm_guard.py`  <- `backend/src/app/adapters/llm_guard.py`
* `backend/src/app/adapters/llm_openai_compat.py`  <- `backend/src/app/adapters/llm_openai_compat.py`
* `backend/src/app/adapters/llm_tasks.py`  <- `backend/src/app/adapters/llm_tasks.py`
* `backend/src/app/adapters/openrouter_options.py`  <- `backend/src/app/adapters/openrouter_options.py`
* `backend/src/app/adapters/ratelimit.py`  <- `backend/src/app/adapters/ratelimit.py`
* `backend/src/app/app/ai_fallback.py`  <- `backend/src/app/app/ai_fallback.py`
* `backend/src/app/app/ai_guard.py`  <- `backend/src/app/app/ai_guard.py`
* `backend/src/app/core/ports.py`  <- `backend/src/app/core/ports.py`
* `backend/src/app/core/redact.py`  <- `backend/src/app/core/redact.py`
* `backend/src/app/core/secret.py`  <- `backend/src/app/core/secret.py`
* `backend/src/app/db/repos/ai_budget.py`  <- `backend/src/app/db/repos/ai_budget.py`

**examples/ (product-specific; shown as examples only)**

* `backend/src/app/adapters/llm_task_definitions.py`  <- split out of `adapters/llm_tasks.py` (written for this package from that file's code)

**tests/**

* `backend/tests/integration/test_ai_budget.py`  <- `backend/tests/integration/test_ai_budget.py`
* `backend/tests/integration/test_ai_fallbacks.py`  <- `backend/tests/integration/test_ai_fallbacks.py`
* `backend/tests/integration/test_ai_rate_limit.py`  <- `backend/tests/integration/test_ai_rate_limit.py`
* `backend/tests/integration/test_llm_key_hygiene.py`  <- `backend/tests/integration/test_llm_key_hygiene.py`
* `backend/tests/unit/test_ai_rate_and_log.py`  <- `backend/tests/unit/test_ai_rate_and_log.py`
* `backend/tests/unit/test_llm_anthropic.py`  <- `backend/tests/unit/test_llm_anthropic.py`
* `backend/tests/unit/test_llm_cluster_labels.py`  <- `backend/tests/unit/test_llm_cluster_labels.py`
* `backend/tests/unit/test_llm_contract.py`  <- `backend/tests/unit/test_llm_contract.py`
* `backend/tests/unit/test_llm_failures.py`  <- `backend/tests/unit/test_llm_failures.py`
* `backend/tests/unit/test_llm_openai_compat.py`  <- `backend/tests/unit/test_llm_openai_compat.py`
* `backend/tests/unit/test_llm_rag.py`  <- `backend/tests/unit/test_llm_rag.py`
* `backend/tests/unit/test_openrouter_options.py`  <- `backend/tests/unit/test_openrouter_options.py`
* `backend/tests/unit/test_secret.py`  <- `backend/tests/unit/test_secret.py`

## Depends on repository files that were NOT copied

Generated from the imports in the copied files. Each is needed (or must be replaced by your own equivalent) before this wires into a project.

* `backend/src/app/app/__init__.py`
* `backend/src/app/app/billing.py`
* `backend/src/app/app/container.py`
* `backend/src/app/app/routers/__init__.py`
* `backend/src/app/app/routers/privacy.py`
* `backend/src/app/app/routers/sentiment.py`
* `backend/src/app/app/settings.py`
* `backend/src/app/app/worker.py`
* `backend/src/app/core/obs.py`
* `backend/src/app/core/sentiment.py`
* `backend/src/app/db/__init__.py`
* `backend/src/app/db/repos/__init__.py`

## External dependencies

* anthropic
* asyncpg
* fastapi
* httpx
* pydantic
* pytest

## Known limits and notes
* `app/ai_guard.py` imports `app.app.settings.ai_settings` (the typed AI configuration), `app.app.billing` and `app.app.routers.privacy.processor_on`; none were copied. See the generated dependency list.
* A token cap of NULL or 0 does not mean unlimited in the original code: a missing cap falls back to a default of 200,000 and the lower of the database and environment value wins.
* Only OpenRouter was exercised live.

## Changes made after extraction

* `adapters/llm_tasks.py` was split. Kept in `src/`: lines for the errors, `CallInfo`/`CallResult`, the collector and status tracking, `served_model`, `_obj`, `TaskSpec`, `strict_compatible`, `_cap`, `_wrap`, `_Out`, `validate_output` and `LLMTasks` (`_send`, `_call`, `_record`). Moved to `examples/`: the schemas, token sizing, output models, `OUTPUTS` contents, `PLAN_INSTRUCTION`, `RAG_INSTRUCTION` and the ten task methods.
* Code edits at the seams: `SCHEMAS`, `TASKS` and `OUTPUTS` start empty and are filled with `.update(...)` in the examples file; the free-form error message now reads "the answer is not an object"; the base no longer imports `ask_plan`, `query_plan`, `survey_schema` or `themes`.
* The provider classes (`llm_openai_compat.py`, `llm_anthropic.py`, `llm_fake.py`) were not edited. They subclass `LLMTasks`, so a task method such as `plan(...)` exists only if you mix in `ProductTasks` (or your own) and import the definitions module once at startup.
* Tests that read the registries (`test_openrouter_options.py`) or `RAG_INSTRUCTION` (`test_llm_rag.py`) now import `app.adapters.llm_task_definitions`.
* Smoke-tested: the base imports on its own; with the examples imported 11 schemas, 11 token limits and 11 output models register, `ProductTasks` has 11 methods, and `validate_output` accepts and rejects as before.

## What was redacted or neutralised in these copies

* api_key: 7
* brand_name: 4
* email: 4

No `.env` file, key, token, respondent data or account identifier is included. See the top-level `SECRET_SCAN.md`.
