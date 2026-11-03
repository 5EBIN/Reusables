"""Regression: findings from docs/STRESS_FINDINGS.md that only show behind PgBouncer."""
import socket
import uuid

import asyncpg
import pytest

PGB = "postgresql://<user>:<password>@127.0.0.1:6432/app"


def _up():
    try:
        socket.create_connection(("127.0.0.1", 6432), 0.5).close()
        return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not _up(), reason="PgBouncer not running")


async def test_pgbouncer_default_cache_works_with_max_prepared_statements():
    c = await asyncpg.connect(PGB)  # default statement cache; works due to max_prepared_statements
    try:
        assert await c.fetchval("select $1::int", 7) == 7
    finally:
        await c.close()


@pytest.mark.security
async def test_session_set_behind_pgbouncer_leaks_harness_detects_it():
    """Deliberate session-level SET leaks across clients on a pooled server connection (the bug we avoid)."""
    org = str(uuid.uuid4())
    leaked = False
    for _ in range(30):
        a = await asyncpg.connect(PGB, statement_cache_size=0)
        await a.execute(f"set app.tenant_id = '{org}'")  # BAD: session scope
        await a.close()
        b = await asyncpg.connect(PGB, statement_cache_size=0)
        v = await b.fetchval("select current_setting('app.tenant_id', true)")
        await b.close()
        if v == org:
            leaked = True
            break
    assert leaked, "expected session SET to leak behind transaction pooling"


@pytest.mark.security
async def test_tenant_tx_does_not_leak_behind_pgbouncer():
    from app.db import create_pool, tenant_tx
    pool = await create_pool(PGB, max_size=3)
    try:
        org = str(uuid.uuid4())
        async with tenant_tx(pool, None, org):
            pass
        for _ in range(20):
            async with pool.acquire() as c:
                assert await c.fetchval("select nullif(current_setting('app.tenant_id', true),'')") is None
    finally:
        await pool.close()
