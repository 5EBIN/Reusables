"""SQL for org_settings (per-org send windows, quotas and anonymity floor). SQL text is unchanged from the router it was moved out of."""
import uuid
from datetime import time

import asyncpg
from pydantic import BaseModel, ConfigDict


class OrgSettings(BaseModel):
    """The org's settings row (columns not listed are kept as extra fields)."""
    model_config = ConfigDict(extra="allow")
    quiet_start: time
    quiet_end: time
    tz: str
    daily_quota: int


async def get(c: asyncpg.Connection) -> OrgSettings | None:
    r = await c.fetchrow("select * from org_settings")
    return OrgSettings.model_validate(dict(r)) if r else None


async def upsert(c: asyncpg.Connection, org_id: uuid.UUID, quiet_start: time, quiet_end: time, tz: str, daily_quota: int, min_group_size: int, contact_cooldown_days: int) -> None:
    await c.execute("""insert into org_settings(org_id,quiet_start,quiet_end,tz,daily_quota,min_group_size,contact_cooldown_days) values($1,$2,$3,$4,$5,$6,$7)
            on conflict (org_id) do update set quiet_start=excluded.quiet_start, quiet_end=excluded.quiet_end, tz=excluded.tz, daily_quota=excluded.daily_quota,
            min_group_size=excluded.min_group_size, contact_cooldown_days=excluded.contact_cooldown_days, updated_at=now()""",
                    org_id, quiet_start, quiet_end, tz, daily_quota, min_group_size, contact_cooldown_days)


async def cooldown_days(c: asyncpg.Connection) -> int | None:
    """Days a contact is left alone after a message, or None when the org has no settings row."""
    return await c.fetchval("select contact_cooldown_days from org_settings")
