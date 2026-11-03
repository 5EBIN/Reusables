# Approval gate: one place where risky writes run

**Exercised in the product?** Used in the product (invitations, reminders, publishing, 360 launches, case follow-ups, conversation starts).

## What it does
A proposed action is stored as an approval with a risk level that depends on the action type. High-risk actions need a second person (the proposer cannot approve). Approved actions run through exactly one function, `run_approved`, which executes them once and records a receipt; the executor checks again at the moment of sending.

## When to use it
Anything that sends messages, publishes or changes shared state should pass a human review, and you want the review to be impossible to bypass by accident.

## How it works
* `core/approvals.py` holds the risk table (`action type -> risk`), the allowed status transitions and the two-person rule (`check_transition`).
* `app/run_approved.py` is the ONLY module allowed to import the executors. The import-linter contract `executors-only-via-run-approved` in `.importlinter` fails the build if any other module imports them.
* `db/repos/approvals.py` stores approvals with row locking (`get_for_update`) so a double submit cannot run twice.

## Files

The Python package was renamed to `app` (imports look like `from app.core.verifier import ...`; the source tree is `backend/src/app/`, which contains its own `app/` sub-package) and the Postgres roles are `app_api` (runtime) and `app_owner` (tables and migrations). Capitalised brand names were replaced with `Acme`.

**src/ (copied as is; names and identifiers redacted)**

* `backend/.importlinter`  <- `backend/.importlinter`
* `backend/src/app/app/run_approved.py`  <- `backend/src/app/app/run_approved.py`
* `backend/src/app/core/approvals.py`  <- `backend/src/app/core/approvals.py`
* `backend/src/app/db/repos/approvals.py`  <- `backend/src/app/db/repos/approvals.py`

**tests/**

* `backend/tests/integration/test_approvals_view.py`  <- `backend/tests/integration/test_approvals_view.py`
* `backend/tests/integration/test_distribution_flow.py`  <- `backend/tests/integration/test_distribution_flow.py`
* `backend/tests/unit/test_approvals_core.py`  <- `backend/tests/unit/test_approvals_core.py`
* `backend/tests/unit/test_approvals_labels.py`  <- `backend/tests/unit/test_approvals_labels.py`

**examples/ (product-specific; shown as examples only)**

* `backend/src/app/app/executors/__init__.py`  <- `backend/src/app/app/executors/__init__.py`
* `backend/src/app/app/executors/case_followup.py`  <- `backend/src/app/app/executors/case_followup.py`
* `backend/src/app/app/executors/launch_360.py`  <- `backend/src/app/app/executors/launch_360.py`
* `backend/src/app/app/executors/publish.py`  <- `backend/src/app/app/executors/publish.py`
* `backend/src/app/app/executors/send_invites.py`  <- `backend/src/app/app/executors/send_invites.py`
* `backend/src/app/app/executors/start_conversations.py`  <- `backend/src/app/app/executors/start_conversations.py`

## Depends on repository files that were NOT copied

Generated from the imports in the copied files. Each is needed (or must be replaced by your own equivalent) before this wires into a project.

* `backend/src/app/adapters/queue_pg.py`
* `backend/src/app/app/__init__.py`
* `backend/src/app/app/audience.py`
* `backend/src/app/app/worker.py`
* `backend/src/app/core/conversation.py`
* `backend/src/app/core/distribution.py`
* `backend/src/app/core/ports.py`
* `backend/src/app/db/__init__.py`
* `backend/src/app/db/repos/__init__.py`
* `backend/src/app/db/repos/contacts.py`
* `backend/src/app/db/repos/conversations.py`
* `backend/src/app/db/repos/cx.py`
* `backend/src/app/db/repos/cx_cases.py`
* `backend/src/app/db/repos/deliveries.py`
* `backend/src/app/db/repos/employees.py`
* `backend/src/app/db/repos/feedback360.py`
* `backend/src/app/db/repos/invitations.py`
* `backend/src/app/db/repos/org_settings.py`
* `backend/src/app/db/repos/surveys.py`

## External dependencies

* asyncpg
* pydantic
* pytest

## Known limits and notes
* The risk table in `core/approvals.py` is product-specific (invitations high, reminders medium and so on); reminders need no second person by design.
* The executors under `examples/` are the product's actions: they show the shape (`async def execute(conn, notifier, approval, base_url, now=None)`), not logic to reuse.
* The 'bypass' protection is the import contract plus the tests; there is no runtime check that an action was approved other than `run_approved`'s own status check.

## What was redacted or neutralised in these copies

* email: 10

No `.env` file, key, token, respondent data or account identifier is included. See the top-level `SECRET_SCAN.md`.
