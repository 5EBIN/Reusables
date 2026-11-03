# body-size-limit

**Category:** backend-helpers  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
A pure-ASGI middleware that refuses oversize request bodies with 413, by Content-Length or by counting streamed bytes.

## Problem it solved
Frameworks parse a body before authentication runs, so any caller could make the server buffer a huge body.

## Public interface
* `app/core/body_limit.py`: `def limit_for(path: str) -> int`
* `app/core/body_limit.py`: `class BodyTooLarge`
* `app/core/body_limit.py`: `class BodyLimitMiddleware`

## Dependencies
None beyond the standard library.

## Stubs and what the host must provide
No stubs: every import resolves inside the module.

## Known limits
Per-route overrides are a regex list in the file; the default is 2 MB.

## Quality
B (no tests copied)  
Tests copied: 0 (copied from the source, not run here).

## How to reuse
Add `BodyLimitMiddleware` first in the middleware stack and list heavy routes in `OVERRIDES`.
