# SSRF guard, input sanitising and personal-data redaction

**Exercised in the product?** Used in the product.

## What it does
`netguard` is a pure outbound-URL guard: the host must look like a public host name and every address it resolves to must be public (DNS resolution is injected, so tests never touch the network, and the check is re-run at send time against DNS rebinding); it also holds webhook signature helpers. `sanitize` is an allow-list HTML sanitiser for display-only content (a small tag list, no attributes except a safe `href`, no scripts, styles or handlers). `redact` removes emails, phone numbers, national ids, card numbers and IBANs before text is sent to a model provider. `http_out` is the outbound HTTP port: a fake for tests and an httpx sender with no redirects and a short timeout; the caller re-checks the resolved address.

## When to use it
Your server fetches user-supplied URLs or sends user text to a third party.

## How it works
* Pure functions in `core/`; `adapters/http_out.py` applies the guard.

## Files

The Python package was renamed to `app` (imports look like `from app.core.verifier import ...`; the source tree is `backend/src/app/`, which contains its own `app/` sub-package) and the Postgres roles are `app_api` (runtime) and `app_owner` (tables and migrations). Capitalised brand names were replaced with `Acme`.

**src/ (copied as is; names and identifiers redacted)**

* `backend/src/app/adapters/http_out.py`  <- `backend/src/app/adapters/http_out.py`
* `backend/src/app/core/netguard.py`  <- `backend/src/app/core/netguard.py`
* `backend/src/app/core/redact.py`  <- `backend/src/app/core/redact.py`
* `backend/src/app/core/sanitize.py`  <- `backend/src/app/core/sanitize.py`

**tests/**

* `backend/tests/unit/test_netguard.py`  <- `backend/tests/unit/test_netguard.py`
* `backend/tests/unit/test_redact.py`  <- `backend/tests/unit/test_redact.py`

## Depends on repository files that were NOT copied

Generated from the imports in the copied files. Each is needed (or must be replaced by your own equivalent) before this wires into a project.

* `backend/src/app/adapters/llm_openai_compat.py`

## External dependencies

* httpx
* hypothesis
* pytest

## Known limits and notes
* `redact` patterns target the original product's region (UAE phone numbers and Emirates ID); add your own formats.

## What was redacted or neutralised in these copies

* email: 7

No `.env` file, key, token, respondent data or account identifier is included. See the top-level `SECRET_SCAN.md`.
