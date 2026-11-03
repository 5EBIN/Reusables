# Phase gate, Makefile and import contracts

**Exercised in the product?** Development process (not product code).

## What it does
`scripts/phase-gate.sh` runs lint, unit and security-marked tests, the integration tests through a connection pooler, and the frontend `verify`. `Makefile` has the targets. `backend/.importlinter` defines three architecture contracts: the core must not import vendors, the app must not import vendor SDKs, and only `run_approved` may import the executors. `pyproject.toml` has the ruff and pytest settings.

## When to use it
You want architecture rules enforced by the build instead of by review.

## How it works
* Run `make lint` (ruff and `lint-imports`) and `scripts/phase-gate.sh` before merging.

## Files

The Python package was renamed to `app` (imports look like `from app.core.verifier import ...`; the source tree is `backend/src/app/`, which contains its own `app/` sub-package) and the Postgres roles are `app_api` (runtime) and `app_owner` (tables and migrations). Capitalised brand names were replaced with `Acme`.

**src/ (copied as is; names and identifiers redacted)**

* `Makefile`  <- `Makefile`
* `backend/.importlinter`  <- `backend/.importlinter`
* `backend/pyproject.toml`  <- `backend/pyproject.toml`
* `scripts/phase-gate.sh`  <- `scripts/phase-gate.sh`

## Depends on repository files that were NOT copied

Generated from the imports in the copied files. Each is needed (or must be replaced by your own equivalent) before this wires into a project.

* none

## External dependencies

* none beyond the standard library

## Known limits and notes
* The gate script expects a local Postgres and a PgBouncer on port 6432 and the original folder layout.

## What was redacted or neutralised in these copies

* db_credentials: 1

No `.env` file, key, token, respondent data or account identifier is included. See the top-level `SECRET_SCAN.md`.
