# Tenant isolation with Postgres row-level security

**Exercised in the product?** Used in the product (every table that holds organisation data).

## What it does
Each request runs in one transaction that sets `app.tenant_id` and `app.user_id` with `set_config(..., true)` (transaction-local, never session-level). A runtime role with no bypass sees only its organisation's rows through RLS policies that are also FORCED on the table owner. Tests prove that one organisation cannot read or write another's rows.

## When to use it
A multi-tenant app where a coding mistake must not leak data between customers.

## How it works
* `db/__init__.py`: `tenant_tx` opens the transaction and sets the context. `app/deps.py` and `app/access.py`: the request dependency that resolves the organisation and role.
* `docs/migration-patterns.md`: the policies and roles, extracted from the migrations (the migrations themselves are not copied).
* Tests: `integration/test_rls.py`, `test_users_rls.py`, `test_semantic_rls.py`, `regression/test_pooler.py` (the context must survive a connection pooler in transaction mode), and the SQL stress fixtures.

## Files

The Python package was renamed to `app` (imports look like `from app.core.verifier import ...`; the source tree is `backend/src/app/`, which contains its own `app/` sub-package) and the Postgres roles are `app_api` (runtime) and `app_owner` (tables and migrations). Capitalised brand names were replaced with `Acme`.

**src/ (copied as is; names and identifiers redacted)**

* `backend/src/app/app/access.py`  <- `backend/src/app/app/access.py`
* `backend/src/app/app/deps.py`  <- `backend/src/app/app/deps.py`
* `backend/src/app/db/__init__.py`  <- `backend/src/app/db/__init__.py`

**tests/**

* `backend/tests/conftest.py`  <- `backend/tests/conftest.py`
* `backend/tests/dsn.py`  <- `backend/tests/dsn.py`
* `backend/tests/fixtures/stress/00_stack_schema.sql`  <- `backend/tests/fixtures/stress/00_stack_schema.sql`
* `backend/tests/fixtures/stress/01_rls_roles_and_setting_scope.sql`  <- `backend/tests/fixtures/stress/01_rls_roles_and_setting_scope.sql`
* `backend/tests/fixtures/stress/02_arabic_trgm_fts.sql`  <- `backend/tests/fixtures/stress/02_arabic_trgm_fts.sql`
* `backend/tests/fixtures/stress/03_rls_policy_perf.sql`  <- `backend/tests/fixtures/stress/03_rls_policy_perf.sql`
* `backend/tests/integration/test_rls.py`  <- `backend/tests/integration/test_rls.py`
* `backend/tests/integration/test_semantic_rls.py`  <- `backend/tests/integration/test_semantic_rls.py`
* `backend/tests/integration/test_users_rls.py`  <- `backend/tests/integration/test_users_rls.py`
* `backend/tests/regression/test_pooler.py`  <- `backend/tests/regression/test_pooler.py`

**Written for this package (not copied)**

* `docs/migration-patterns.md`

## Depends on repository files that were NOT copied

Generated from the imports in the copied files. Each is needed (or must be replaced by your own equivalent) before this wires into a project.

* `backend/src/app/app/main.py`
* `backend/src/app/app/security.py`
* `backend/src/app/core/__init__.py`
* `backend/src/app/core/ports.py`
* `backend/src/app/core/timing.py`
* `backend/src/app/db/repos/__init__.py`
* `backend/src/app/db/repos/users.py`

## External dependencies

* asyncpg
* fastapi
* httpx
* pytest

## Known limits and notes
* Integration tests need a Postgres with the original schema and roles; they will not run without it. The SQL under `tests/fixtures/stress/` is standalone.
* Writing to a table needs the runtime role plus a policy for that role: the table owner role is read-only on some tables by design.

## What was redacted or neutralised in these copies

* brand_name: 1
* db_credentials: 3
* email: 4

No `.env` file, key, token, respondent data or account identifier is included. See the top-level `SECRET_SCAN.md`.
