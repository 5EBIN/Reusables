# Consent, quiet hours and quota checked at send time

**Exercised in the product?** Used in the product for email. SMS and WhatsApp sending have only run against a fake provider.

## What it does
When an approved invitation is executed, the executor checks again, per contact: consent, the suppression list, quiet hours (default 21:00 to 08:00 in the organisation's time zone) and the daily quota (non-email channels only).

## When to use it
Messages are queued or approved ahead of time and conditions can change before they go out.

## How it works
* `app/executors/send_invites.py` does the per-contact checks; `core/schedule.py` computes quiet-hour windows; `core/distribution.py` builds recipient lists; `db/repos/org_settings.py` stores the organisation's window and quota.

## Files

The Python package was renamed to `app` (imports look like `from app.core.verifier import ...`; the source tree is `backend/src/app/`, which contains its own `app/` sub-package) and the Postgres roles are `app_api` (runtime) and `app_owner` (tables and migrations). Capitalised brand names were replaced with `Acme`.

**src/ (copied as is; names and identifiers redacted)**

* `backend/src/app/app/executors/send_invites.py`  <- `backend/src/app/app/executors/send_invites.py`
* `backend/src/app/core/distribution.py`  <- `backend/src/app/core/distribution.py`
* `backend/src/app/core/schedule.py`  <- `backend/src/app/core/schedule.py`
* `backend/src/app/db/repos/org_settings.py`  <- `backend/src/app/db/repos/org_settings.py`

**tests/**

* `backend/tests/integration/test_authoring_distribution.py`  <- `backend/tests/integration/test_authoring_distribution.py`
* `backend/tests/integration/test_distribute.py`  <- `backend/tests/integration/test_distribute.py`
* `backend/tests/integration/test_distribution_flow.py`  <- `backend/tests/integration/test_distribution_flow.py`
* `backend/tests/unit/test_distribution.py`  <- `backend/tests/unit/test_distribution.py`
* `backend/tests/unit/test_schedule.py`  <- `backend/tests/unit/test_schedule.py`

## Depends on repository files that were NOT copied

Generated from the imports in the copied files. Each is needed (or must be replaced by your own equivalent) before this wires into a project.

* `backend/src/app/app/__init__.py`
* `backend/src/app/app/audience.py`
* `backend/src/app/app/run_approved.py`
* `backend/src/app/app/worker.py`
* `backend/src/app/core/approvals.py`
* `backend/src/app/core/ports.py`
* `backend/src/app/core/survey_schema.py`
* `backend/src/app/db/__init__.py`
* `backend/src/app/db/repos/__init__.py`
* `backend/src/app/db/repos/deliveries.py`
* `backend/src/app/db/repos/invitations.py`
* `backend/src/app/seeds/templates.py`

## External dependencies

* asyncpg
* pydantic
* pytest

## Known limits and notes
* Quiet hours and quota depend on `org_settings`; reminders are medium risk and need no second person.

## What was redacted or neutralised in these copies

* email: 27

No `.env` file, key, token, respondent data or account identifier is included. See the top-level `SECRET_SCAN.md`.
