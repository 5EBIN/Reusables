# object-storage-wrapper

**Category:** backend-helpers  
**Origin:** extracted from a production Next.js/FastAPI app.

## What it does
Server-side wrapper over Supabase Storage: ensure bucket, upload with content hash, signed URL, download.

## Problem it solved
Keeps the service-role key out of responses and logs, and gives uploads stable hashed names.

## Public interface
* `app/core/supabase_storage.py`: `def ensure_bucket() -> None`
* `app/core/supabase_storage.py`: `def upload_object(owner_id: str, filename: str, content: bytes, content_type: str) -> dict`
* `app/core/supabase_storage.py`: `def signed_url(path: str, expires_in: int=300) -> str`
* `app/core/supabase_storage.py`: `def download_object(path: str) -> bytes`

## Dependencies
Python (`deps.txt`): `supabase>=2.10`

## Stubs and what the host must provide
`src/app/_stubs.py` / `src/_stubs.ts` keep imports resolvable. The host must replace: `get_settings`.

## Known limits
Needs a settings object with `supabase_url`, `supabase_service_role_key` and `storage_bucket`.

## Quality
B (no tests copied)  
Tests copied: 0 (copied from the source, not run here).

## How to reuse
Call `ensure_bucket()` at startup, then `upload_object` / `signed_url`.

(Stub signatures were derived from the host code they stand for; they carry no behaviour.)
