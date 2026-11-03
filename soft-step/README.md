# soft-step

**Category:** backend-helpers  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
`soft_failure` / `soft_step`: a best-effort step that logs and keeps going, but fails loudly on programming errors (NameError, TypeError, AttributeError, KeyError ...) outside production.

## Problem it solved
Blanket `except Exception: log and continue` hid real bugs behind the same quiet line as a database blip.

## Public interface
* `app/core/soft_step.py`: `def counts() -> dict`
* `app/core/soft_step.py`: `def soft_failure(label: str, exc: BaseException, detail=None, *, expected: tuple | None=None, message: bool=True) -> None`
* `app/core/soft_step.py`: `def soft_step(label: str, detail=None, *, expected: tuple | None=None)`

## Dependencies
Python (`deps.txt`): `httpx>=0.27`, `sqlalchemy[asyncio]>=2.0`

## Stubs and what the host must provide
`src/app/_stubs.py` / `src/_stubs.ts` keep imports resolvable. The host must replace: `get_settings`.

## Known limits
Needs a `get_settings()` with a `treated_as_production` flag; anything unreadable counts as production.

## Quality
A (small, 7 tests copied, no I/O)  
Tests copied: 1 (copied from the source, not run here).

## How to reuse
Replace `except Exception` in best-effort steps with `with soft_step('label'):`.

(Stub signatures were derived from the host code they stand for; they carry no behaviour.)
