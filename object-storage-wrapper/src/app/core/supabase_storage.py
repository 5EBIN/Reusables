"""app/core/supabase_storage.py — thin Supabase Storage client for server-side use only.

The service-role key used here MUST never be exposed in API responses or logs.
"""
from __future__ import annotations
import hashlib
import logging
from functools import lru_cache

from app.core.soft_step import soft_failure

logger = logging.getLogger(__name__)


@lru_cache
def _client():
    from supabase import create_client
    from app._stubs import get_settings
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_role_key)


def _bucket() -> str:
    from app._stubs import get_settings
    return get_settings().storage_bucket


def ensure_bucket() -> None:
    """Idempotent: create the private bucket if it doesn't exist."""
    try:
        c = _client()
        existing = {b.name for b in c.storage.list_buckets()}
        if _bucket() not in existing:
            c.storage.create_bucket(_bucket(), options={"public": False})
            logger.info("[object_storage] Created bucket '%s'", _bucket())
    except Exception as exc:
        soft_failure("supabase_storage ensure_bucket", exc)


def upload_object(owner_id: str, filename: str, content: bytes, content_type: str) -> dict:
    """Upload one file. Returns {path, hash}. Never logs content."""
    file_hash = hashlib.sha256(content).hexdigest()
    path = f"{owner_id}/{file_hash[:12]}_{filename}"
    _client().storage.from_(_bucket()).upload(
        path, content,
        {"content-type": content_type, "upsert": "true"},
    )
    return {"path": path, "hash": file_hash}


def signed_url(path: str, expires_in: int = 300) -> str:
    res = _client().storage.from_(_bucket()).create_signed_url(path, expires_in)
    return res["signedURL"]


def download_object(path: str) -> bytes:
    return bytes(_client().storage.from_(_bucket()).download(path))
