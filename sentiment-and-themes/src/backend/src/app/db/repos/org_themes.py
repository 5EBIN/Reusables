"""SQL for the org_themes table (per-org branding; currently the logo). SQL text is unchanged from the router it was moved out of."""
import uuid
from typing import Any

import asyncpg
from pydantic import BaseModel


class Logo(BaseModel):
    logo_key: str | None
    logo_mime: str | None
    logo_sha256: str | None


async def logo_key(c: asyncpg.Connection) -> str | None:
    return await c.fetchval("select logo_key from org_themes")


async def get_logo(c: asyncpg.Connection) -> Logo | None:
    r = await c.fetchrow("select logo_key, logo_mime, logo_sha256 from org_themes")
    return Logo.model_validate(dict(r)) if r else None


async def set_logo(c: asyncpg.Connection, org_id: uuid.UUID, key: str, mime: str, sha256: str, size: int) -> None:
    await c.execute("insert into org_themes(org_id,logo_key,logo_mime,logo_sha256,logo_size,logo_updated_at) values($1,$2,$3,$4,$5,now()) "
                    "on conflict (org_id) do update set logo_key=excluded.logo_key, logo_mime=excluded.logo_mime, logo_sha256=excluded.logo_sha256, "
                    "logo_size=excluded.logo_size, logo_updated_at=now(), updated_at=now()", org_id, key, mime, sha256, size)


async def clear_logo(c: asyncpg.Connection) -> None:
    await c.execute("update org_themes set logo_key=null, logo_mime=null, logo_sha256=null, logo_size=null, logo_updated_at=null, updated_at=now()")


class Theme(BaseModel):
    tokens: Any                      # JSON text of design tokens
    remove_branding: bool | None


class HostTheme(BaseModel):
    h_tokens: Any                    # JSON text
    h_remove_branding: bool | None


async def get_theme(c: asyncpg.Connection) -> Theme | None:
    r = await c.fetchrow("select tokens, remove_branding from org_themes")
    return Theme.model_validate(dict(r)) if r else None


async def for_host(c: asyncpg.Connection, host: str) -> HostTheme | None:
    """Theme for a custom survey domain, looked up across orgs (runs outside any tenant context)."""
    r = await c.fetchrow("select * from app.resolve_host($1)", host)
    return HostTheme.model_validate(dict(r)) if r else None


class ThemeFull(BaseModel):
    tokens: Any                      # JSON text of design tokens
    remove_branding: bool | None
    logo_key: str | None
    logo_mime: str | None
    logo_size: int | None
    logo_sha256: str | None


async def get_full(c: asyncpg.Connection) -> ThemeFull | None:
    r = await c.fetchrow("select tokens, remove_branding, logo_key, logo_mime, logo_size, logo_sha256 from org_themes")
    return ThemeFull.model_validate(dict(r)) if r else None


async def upsert_tokens(c: asyncpg.Connection, org_id: uuid.UUID, tokens_json: str, remove_branding: bool) -> None:
    await c.execute("insert into org_themes(org_id,tokens,remove_branding) values($1,$2,$3) on conflict (org_id) do update set tokens=excluded.tokens, remove_branding=excluded.remove_branding, updated_at=now()",
                    org_id, tokens_json, remove_branding)
