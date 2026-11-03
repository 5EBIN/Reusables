import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.app import scheduler
from tests.integration.test_dashboards import world

pytestmark = pytest.mark.asyncio


async def test_tick_runs_due_dashboard_schedule_once(make_user, client, app):
    u, org, h, sid, did = await world(make_user, client)
    await client.post(f"/v1/dashboards/{did}/schedules", json={"name": "S", "freq": "daily", "recipients": [u.email]}, headers=h)
    app.state.container.notifier.sent.clear()
    later = datetime.now(UTC) + timedelta(days=2)
    res = await scheduler.tick_locked(app.state.pool, app.state.container, later, {"dashboard_schedules"})
    assert res is not None and res["dashboard_schedules"] >= 1 and "error" not in res.values()
    assert any(m.to == u.email and m.template_id == "dashboard-ready" for m in app.state.container.notifier.sent)
    app.state.container.notifier.sent.clear()
    await scheduler.tick_locked(app.state.pool, app.state.container, later, {"dashboard_schedules"})                       # next_run moved forward: no duplicate
    assert not any(m.to == u.email and m.template_id == "dashboard-ready" for m in app.state.container.notifier.sent)


async def test_second_replica_is_locked_out(app):
    async with app.state.pool.acquire() as holder:
        assert await holder.fetchval("select pg_try_advisory_lock($1)", scheduler.LOCK_KEY)
        try:
            # a different pooled connection cannot take the lock while it is held
            assert await scheduler.tick_locked(app.state.pool, app.state.container, only=set()) is None
        finally:
            await holder.execute("select pg_advisory_unlock($1)", scheduler.LOCK_KEY)


async def test_a_failing_step_does_not_block_the_others(app, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr("app.app.routers.exports.run_due_schedules", boom)
    res = await scheduler.tick_all(app.state.pool, app.state.container, only={"report_schedules", "dashboard_schedules"})      # not the enqueue steps: they would flood the shared test queue
    assert res["report_schedules"] == "error" and isinstance(res["dashboard_schedules"], int)
    await asyncio.sleep(0)
