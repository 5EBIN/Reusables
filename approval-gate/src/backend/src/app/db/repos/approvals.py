"""SQL for approvals (human sign-off before a send or release) and their event trail. SQL text is unchanged from the router it was moved out of."""
import uuid
from datetime import datetime
from typing import Any

import asyncpg
from pydantic import BaseModel, ConfigDict


class Approval(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: uuid.UUID
    action_type: str
    risk: str
    status: str
    payload: Any                     # JSON text
    preview: Any                     # JSON text
    proposed_by: uuid.UUID | None
    decided_by: uuid.UUID | None = None
    scheduled_for: datetime | None
    created_at: datetime
    receipt: Any                     # JSON text or None
    error: str | None
    decision_comment: str | None
    decided_at: datetime | None
    executed_at: datetime | None


class Event(BaseModel):
    event: str
    actor: uuid.UUID | None
    at: datetime


async def by_idempotency_key(c: asyncpg.Connection, key: str) -> Approval | None:
    r = await c.fetchrow("select * from approvals where idempotency_key=$1", key)
    return Approval.model_validate(dict(r)) if r else None


async def get(c: asyncpg.Connection, approval_id: uuid.UUID) -> Approval | None:
    r = await c.fetchrow("select * from approvals where id=$1", approval_id)
    return Approval.model_validate(dict(r)) if r else None


async def get_for_update(c: asyncpg.Connection, approval_id: uuid.UUID) -> Approval | None:
    r = await c.fetchrow("select * from approvals where id=$1 for update", approval_id)
    return Approval.model_validate(dict(r)) if r else None


async def list_by_status(c: asyncpg.Connection, status: str) -> list[Approval]:
    """Newest 200; the status 'all' lists every status."""
    rows = await c.fetch("select * from approvals where $1='all' or status=$1 order by created_at desc limit 200", status)
    return [Approval.model_validate(dict(r)) for r in rows]


async def counts_by_status(c: asyncpg.Connection) -> dict[str, int]:
    rows = await c.fetch("select status, count(*) n from approvals group by 1")
    return {r["status"]: r["n"] for r in rows}


async def recent_executed(c: asyncpg.Connection) -> list[Approval]:
    rows = await c.fetch("select * from approvals where status='executed' order by executed_at desc nulls last limit 5")
    return [Approval.model_validate(dict(r)) for r in rows]


async def insert(c: asyncpg.Connection, org_id: uuid.UUID, approval_id: uuid.UUID, action_type: str, risk: str, payload_json: str, preview_json: str,
                 proposed_by: uuid.UUID, idempotency_key: str, scheduled_for: datetime | None) -> None:
    await c.execute("""insert into approvals(org_id,id,action_type,risk,payload,preview,proposed_by,idempotency_key,scheduled_for)
            values($1,$2,$3,$4,$5,$6,$7,$8,$9)""", org_id, approval_id, action_type, risk, payload_json, preview_json, proposed_by, idempotency_key, scheduled_for)


async def record_decision(c: asyncpg.Connection, approval_id: uuid.UUID, status: str, decided_by: uuid.UUID, comment: str | None) -> None:
    await c.execute("update approvals set status=$2, decided_by=$3, decision_comment=$4, decided_at=now() where id=$1", approval_id, status, decided_by, comment)


async def events(c: asyncpg.Connection, approval_id: uuid.UUID) -> list[Event]:
    rows = await c.fetch("select event, actor, at from approval_events where approval_id=$1 order by id", approval_id)
    return [Event.model_validate(dict(r)) for r in rows]


async def log_proposed(c: asyncpg.Connection, org_id: uuid.UUID, approval_id: uuid.UUID, actor: uuid.UUID) -> None:
    await c.execute("insert into approval_events(org_id,approval_id,actor,event) values($1,$2,$3,'proposed')", org_id, approval_id, actor)


async def log_decision(c: asyncpg.Connection, org_id: uuid.UUID, approval_id: uuid.UUID, actor: uuid.UUID, event: str, detail_json: str) -> None:
    await c.execute("insert into approval_events(org_id,approval_id,actor,event,detail) values($1,$2,$3,$4,$5)", org_id, approval_id, actor, event, detail_json)


async def mark_failed(c: asyncpg.Connection, approval_id: uuid.UUID, error: str) -> None:
    await c.execute("update approvals set status='failed', error=$2 where id=$1", approval_id, error)


async def mark_executed(c: asyncpg.Connection, approval_id: uuid.UUID, receipt_json: str) -> None:
    await c.execute("update approvals set status='executed', receipt=$2, executed_at=now(), error=null where id=$1", approval_id, receipt_json)


async def set_receipt(c: asyncpg.Connection, approval_id: uuid.UUID, receipt_json: str) -> None:
    await c.execute("update approvals set receipt=$2 where id=$1", approval_id, receipt_json)


async def log_system_event(c: asyncpg.Connection, org_id: Any, approval_id: uuid.UUID, event: str, detail_json: str) -> None:
    """An event with no human actor (execution succeeded or failed)."""
    await c.execute("insert into approval_events(org_id,approval_id,event,detail) values($1,$2,$3,$4)", org_id, approval_id, event, detail_json)
