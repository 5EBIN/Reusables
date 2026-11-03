# scrub-safe-error-v2

**Category:** backend-helpers  
**Origin:** extracted from a production Next.js/FastAPI app.

**Variant of:** `ssrf-and-input-hygiene` (existing module). **How it differs:** that module redacts personal data (emails, IBAN, phone, card) and guards outbound URLs; this one redacts credentials and secret-shaped values and filters logs.

## What it does
Two redaction layers for secrets: a logging filter that masks `token=`-style query parameters in access and error logs, and a recursive payload redactor (sensitive keys, JWT, bearer, PEM, cloud key, `sk-` and `ghp_` tokens, URL credentials, long-string truncation with a hash).

## Problem it solved
Session tokens in URLs ended up in access logs, and audit payloads can carry credentials.

## Public interface
* `app/core/log_redaction.py`: `def redact(text: str) -> str`
* `app/core/log_redaction.py`: `class RedactSecretsFilter`
* `app/core/log_redaction.py`: `def install_log_redaction() -> None`
* `app/payload_redaction.py`: `def redact_value(secret: str) -> str`
* `app/payload_redaction.py`: `def redact_string(text: str) -> str`
* `app/payload_redaction.py`: `def redact(value, _key: str | None=None)`

## Dependencies
None beyond the standard library.

## Stubs and what the host must provide
No stubs: every import resolves inside the module.

## Known limits
Pattern lists are conservative, not exhaustive; review them for your providers.

## Quality
A (8 tests copied; pure functions)  
Tests copied: 1 (copied from the source, not run here).

## How to reuse
Call `install_log_redaction()` at startup and `redact(payload)` before storing a payload.
