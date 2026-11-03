"""Postgres job queue: SKIP LOCKED claim via definer function; exponential backoff; dead-letter after max_attempts."""
import json
import uuid
from datetime import datetime


class PgQueue:
    async def enqueue(self, conn, kind: str, payload: dict, *, run_after: datetime | None = None, org_id: str | None = None) -> str:
        jid = uuid.uuid4()
        await conn.execute("insert into jobs(org_id,id,kind,payload,run_after) values(nullif(current_setting('app.tenant_id', true),'')::uuid,$1,$2,$3,coalesce($4, now()))",
                           jid, kind, json.dumps(payload), run_after)
        return str(jid)

    async def claim(self, conn, limit: int = 10):
        return await conn.fetch("select * from app.claim_jobs($1)", limit)

    async def finish(self, conn, org_id, job_id):
        await conn.execute("select app.finish_job($1,$2)", org_id, job_id)

    async def fail(self, conn, org_id, job_id, error: str) -> str:
        return await conn.fetchval("select app.fail_job($1,$2,$3)", org_id, job_id, error)
