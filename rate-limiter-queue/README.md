# Rate limiter and Postgres job queue

**Exercised in the product?** Used in the product.

## What it does
A fixed-window rate limiter with an in-memory backend (tests and development) and a Postgres backend (shared across instances; one atomic SQL function on an UNLOGGED table), and a Postgres job queue that claims jobs with SKIP LOCKED through a definer function, retries with exponential backoff and dead-letters after a maximum number of attempts. A worker and a scheduler run them.

## When to use it
You need limits and background jobs without adding Redis or a broker.

## How it works
* `adapters/ratelimit.py` implements the `RateLimiter` port; `adapters/queue_pg.py` implements `JobQueue`; `app/worker.py` and `app/scheduler.py` run jobs and schedules; `core/ports.py` has the protocols.

## Files

The Python package was renamed to `app` (imports look like `from app.core.verifier import ...`; the source tree is `backend/src/app/`, which contains its own `app/` sub-package) and the Postgres roles are `app_api` (runtime) and `app_owner` (tables and migrations). Capitalised brand names were replaced with `Acme`.

**src/ (copied as is; names and identifiers redacted)**

* `backend/src/app/adapters/queue_pg.py`  <- `backend/src/app/adapters/queue_pg.py`
* `backend/src/app/adapters/ratelimit.py`  <- `backend/src/app/adapters/ratelimit.py`
* `backend/src/app/app/scheduler.py`  <- `backend/src/app/app/scheduler.py`
* `backend/src/app/app/worker.py`  <- `backend/src/app/app/worker.py`
* `backend/src/app/core/ports.py`  <- `backend/src/app/core/ports.py`

**tests/**

* `backend/tests/integration/test_ai_rate_limit.py`  <- `backend/tests/integration/test_ai_rate_limit.py`
* `backend/tests/integration/test_scheduler.py`  <- `backend/tests/integration/test_scheduler.py`
* `backend/tests/unit/test_ports_contract.py`  <- `backend/tests/unit/test_ports_contract.py`

## Depends on repository files that were NOT copied

Generated from the imports in the copied files. Each is needed (or must be replaced by your own equivalent) before this wires into a project.

* `backend/src/app/adapters/auth_fake.py`
* `backend/src/app/adapters/auth_supabase.py`
* `backend/src/app/app/__init__.py`
* `backend/src/app/app/container.py`
* `backend/src/app/app/cx_rules.py`
* `backend/src/app/app/revocation.py`
* `backend/src/app/app/routers/dashboards.py`
* `backend/src/app/app/routers/engagement.py`
* `backend/src/app/app/routers/exports.py`
* `backend/src/app/app/routers/privacy.py`
* `backend/src/app/app/routers/research.py`
* `backend/src/app/app/run_approved.py`
* `backend/src/app/app/webhooks.py`
* `backend/src/app/core/obs.py`
* `backend/src/app/db/__init__.py`

## External dependencies

* PyJWT
* pytest

## Known limits and notes
* The Postgres backend needs the original tables for limits and jobs; their migrations were not copied.

## What was redacted or neutralised in these copies

* email: 1

No `.env` file, key, token, respondent data or account identifier is included. See the top-level `SECRET_SCAN.md`.
