"""SQL for system-written audit rows (webhooks with no signed-in user). User-driven events go through app.app.audit."""
import uuid
from datetime import datetime
from typing import Any

import asyncpg
from pydantic import BaseModel


async def insert_system_event(c: asyncpg.Connection, org_id: uuid.UUID, actor_label: str, action: str, target: str, detail_json: str) -> None:
    await c.execute("insert into audit_log(org_id,actor_label,action,target,detail) values($1,$2,$3,$4,$5)", org_id, actor_label, action, target, detail_json)


class AuditEntry(BaseModel):
    id: int
    at: datetime
    actor_label: str | None
    action: str
    target: str | None
    on_behalf_of: str | None
    detail: Any


class ChainStatus(BaseModel):
    ok: bool
    checked: int
    first_bad: int | None = None


async def search(c: asyncpg.Connection, days: int, actor: str | None, action: str | None) -> list[AuditEntry]:
    """Newest 200 entries of the last `days` days; actor and action are case-insensitive contains-filters."""
    rows = await c.fetch("""select id, at, actor_label, action, target, on_behalf_of, detail from audit_log where at > now() - make_interval(days => $1)
            and ($2::text is null or actor_label ilike '%' || $2 || '%') and ($3::text is null or action ilike '%' || $3 || '%') order by id desc limit 200""", days, actor, action)
    return [AuditEntry.model_validate(dict(r)) for r in rows]


async def verify_chain(c: asyncpg.Connection, org_id: uuid.UUID) -> ChainStatus:
    """Recomputes the tamper-evident hash chain for the org's audit log."""
    r = await c.fetchrow("select * from app.audit_verify($1)", org_id)
    return ChainStatus.model_validate(dict(r))
