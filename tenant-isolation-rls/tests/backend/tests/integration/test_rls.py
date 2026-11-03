from tests.dsn import API as API_DSN, OWNER as OWNER_DSN
import os
import uuid

import asyncpg
import pytest

from app.db import create_pool, tenant_tx

A, B = str(uuid.uuid4()), str(uuid.uuid4())
OWNER = OWNER_DSN
os.environ.setdefault("DATABASE_URL", API_DSN)


@pytest.fixture(scope="session")
async def pool():
    p = await create_pool(max_size=4)
    yield p
    await p.close()


@pytest.mark.security
async def test_runtime_role_attributes(pool):
    async with pool.acquire() as c:
        r = await c.fetchrow("select rolsuper, rolbypassrls from pg_roles where rolname=current_user")
        assert not r["rolsuper"] and not r["rolbypassrls"]
        owned = await c.fetchval("select count(*) from pg_tables where tableowner=current_user")
        assert owned == 0
        bad = await c.fetch("""select c.relname from pg_class c join pg_attribute a on a.attrelid=c.oid
            where c.relkind='r' and c.relnamespace='public'::regnamespace and a.attname='org_id' and not a.attisdropped
            and not c.relforcerowsecurity""")
        assert bad == []


async def _ins(pool, org, body):
    async with tenant_tx(pool, None, org) as c:
        await c.execute("insert into org_notes(org_id,id,body) values($1,$2,$3)", uuid.UUID(org), uuid.uuid4(), body)


@pytest.mark.security
async def test_two_tenants_isolated_and_check(pool):
    await _ins(pool, A, "a"); await _ins(pool, B, "b")
    async with tenant_tx(pool, None, A) as c:
        assert set(await c.fetchval("select array_agg(distinct org_id) from org_notes")) == {uuid.UUID(A)}
    with pytest.raises(asyncpg.PostgresError):
        async with tenant_tx(pool, None, A) as c:
            await c.execute("insert into org_notes(org_id,id) values($1,$2)", uuid.UUID(B), uuid.uuid4())


@pytest.mark.security
async def test_missing_tenant_fails_closed(pool):
    async with tenant_tx(pool, None, None) as c:
        assert await c.fetchval("select count(*) from org_notes") == 0
    async with pool.acquire() as c:  # no tx helper at all, after pooled reuse
        assert await c.fetchval("select count(*) from org_notes") == 0


async def test_set_local_outside_txn_has_no_effect(pool):
    async with pool.acquire() as c:
        await c.execute(f"set local app.tenant_id='{A}'")
        assert await c.fetchval("select count(*) from org_notes") == 0


@pytest.mark.security
async def test_pooled_reuse_no_leak(pool):
    import asyncio
    async def one(o):
        async with tenant_tx(pool, None, o) as c:
            return {r["org_id"] for r in await c.fetch("select org_id from org_notes")}
    res = await asyncio.gather(*[one(A if i % 2 else B) for i in range(40)])
    for i, s in enumerate(res):
        assert s <= {uuid.UUID(A if i % 2 else B)}


async def test_db_locale_supports_arabic_trigrams(pool):
    async with pool.acquire() as c:
        assert await c.fetchval("select show_trgm('الخدمة')") != []
