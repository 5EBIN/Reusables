# owner-only-404

**Category:** backend-helpers  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
A FastAPI dependency pattern: a resource that is missing and one owned by someone else both answer 404.

## Problem it solved
Distinguishing 403 from 404 lets callers probe for other people's ids.

## Public interface
* `app/api/ownership.py`: `async def authorize_item(request: Request, item_id: str, user: dict=Depends(get_current_user), db: AsyncSession=Depends(get_db))`

## Dependencies
Python (`deps.txt`): `fastapi>=0.115`, `sqlalchemy[asyncio]>=2.0`

## Stubs and what the host must provide
`src/app/_stubs.py` / `src/_stubs.ts` keep imports resolvable. The host must replace: `Item`, `get_current_user`, `get_db`.

## Known limits
The `Item` model, `get_current_user` and `get_db` are host stubs.

## Quality
B (no tests copied; 25 lines)  
Tests copied: 0 (copied from the source, not run here).

## How to reuse
Copy the pattern and point `_owned` at your own model.

(Stub signatures were derived from the host code they stand for; they carry no behaviour.)
