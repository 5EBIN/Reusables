"""Job worker: claims across tenants via definer function, runs each job inside its own tenant transaction."""
import json

from app.adapters.queue_pg import PgQueue
from app.app.run_approved import release_deferred, run_approved, send_360_reminders
from app.db import tenant_tx

Q = PgQueue()


async def handle(conn, container, job) -> None:
    payload = json.loads(job["payload"])
    if job["kind"] == "run_approved":
        import uuid
        await run_approved(conn, uuid.UUID(payload["approval_id"]), container.notifier, container.base_url)
    elif job["kind"] == "release_deferred":
        import uuid
        await release_deferred(conn, uuid.UUID(payload["approval_id"]), container.notifier, container.base_url)
    elif job["kind"] == "pulse_tick":
        from datetime import date
        from app.app.routers.engagement import tick
        await tick(conn, str(job["org_id"]), date.today())
    elif job["kind"] == "reminders_360":
        import uuid
        await send_360_reminders(conn, uuid.UUID(payload["cycle_id"]), int(payload["day_offset"]), container.notifier, container.base_url)
    elif job["kind"] == "export":
        import uuid
        from app.app.routers.exports import run_export
        await run_export(conn, container, uuid.UUID(payload["export_id"]))
    elif job["kind"] == "webhook_deliver":
        import uuid
        from app.app.webhooks import deliver
        await deliver(conn, container, uuid.UUID(payload["delivery_id"]))
    elif job["kind"] == "research_run":
        import uuid
        from app.app.routers.research import run_pipeline
        await run_pipeline(conn, container, uuid.UUID(payload["project_id"]))
    elif job["kind"] == "retention_tick":
        from app.app.routers.privacy import purge
        await purge(conn, container.store)
    elif job["kind"] == "alert_tick":
        from app.app.cx_rules import run_scheduled
        await run_scheduled(conn, container.notifier)
    else:
        raise ValueError(f"unknown job kind {job['kind']}")


async def run_pending(pool, container, limit: int = 10) -> dict:
    stats = {"done": 0, "retry": 0, "dead": 0}
    async with pool.acquire() as c:
        async with c.transaction():
            jobs = await Q.claim(c, limit)
    for j in jobs:
        try:
            async with tenant_tx(pool, None, str(j["org_id"])) as conn:
                await handle(conn, container, j)
        except Exception as e:
            async with pool.acquire() as c:
                st = await Q.fail(c, j["org_id"], j["id"], f"{type(e).__name__}: {e}")
            stats["dead" if st == "dead" else "retry"] += 1
            continue
        async with pool.acquire() as c:
            await Q.finish(c, j["org_id"], j["id"])
        stats["done"] += 1
    return stats


async def enqueue_pulse_ticks(pool, today=None) -> int:
    """Called by the scheduler (cron/Routine): one pulse_tick job per org with due schedules. Creates drafts + approvals only."""
    from datetime import date
    n = 0
    async with pool.acquire() as c:
        orgs = [r[0] for r in await c.fetch("select * from app.orgs_with_due_pulses($1)", today or date.today())]
    for org in orgs:
        async with tenant_tx(pool, None, str(org)) as conn:
            await Q.enqueue(conn, "pulse_tick", {})
            n += 1
    return n


async def enqueue_alert_ticks(pool) -> int:
    """Scheduler entry: one alert_tick job per org that has enabled alert rules."""
    n = 0
    async with pool.acquire() as c:
        orgs = [r[0] for r in await c.fetch("select * from app.orgs_with_alert_rules()")]
    for org in orgs:
        async with tenant_tx(pool, None, str(org)) as conn:
            await Q.enqueue(conn, "alert_tick", {})
            n += 1
    return n
