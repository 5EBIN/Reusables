"""Background scheduler: one process (`python -m app.app.scheduler`) runs every due schedule and the job queue each minute.
A Postgres advisory lock makes extra replicas harmless: only the holder ticks. Each step is isolated so one failure never blocks the rest."""
import asyncio
import logging

from app.app.revocation import purge_revocations
from app.app.worker import enqueue_alert_ticks, enqueue_pulse_ticks, run_pending

log = logging.getLogger("app.scheduler")
LOCK_KEY = 7_204_001


async def tick_all(pool, container, now=None, only: set[str] | None = None) -> dict:
    from app.app.routers.dashboards import run_due_dashboard_schedules
    from app.app.routers.exports import run_due_schedules
    steps = {
        "report_schedules": lambda: run_due_schedules(pool, container, now),
        "dashboard_schedules": lambda: run_due_dashboard_schedules(pool, container, now),
        "pulse_ticks": lambda: enqueue_pulse_ticks(pool),
        "alert_ticks": lambda: enqueue_alert_ticks(pool),
        "jobs": lambda: run_pending(pool, container, 25),
        "revocation_purge": lambda: purge_revocations(pool),
    }
    out: dict = {}
    for name, fn in steps.items():
        if only is not None and name not in only:
            continue
        try:
            out[name] = await fn()
        except Exception:
            log.exception("scheduler step %s failed", name)
            out[name] = "error"
    return out


async def tick_locked(pool, container, now=None, only: set[str] | None = None) -> dict | None:
    """Run one tick only if this process wins the advisory lock; returns None when another replica holds it."""
    async with pool.acquire() as c:
        if not await c.fetchval("select pg_try_advisory_lock($1)", LOCK_KEY):
            return None
        try:
            return await tick_all(pool, container, now, only)
        finally:
            await c.execute("select pg_advisory_unlock($1)", LOCK_KEY)


async def main(interval: float = 60.0) -> None:
    from app.app.container import build_container
    from app.db import create_pool
    logging.basicConfig(level=logging.INFO)
    container, pool = build_container(), await create_pool()
    try:
        while True:
            res = await tick_locked(pool, container)
            if res is not None:
                log.info("tick %s", res)
            await asyncio.sleep(interval)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
