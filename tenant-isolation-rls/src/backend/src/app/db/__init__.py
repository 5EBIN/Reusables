import os
import time
from contextlib import asynccontextmanager

import asyncpg

from app.core import timing


async def create_pool(dsn: str | None = None, **kw) -> asyncpg.Pool:
    cache = int(os.environ.get("DB_STATEMENT_CACHE_SIZE", "0"))
    return await asyncpg.create_pool(
        dsn or os.environ["DATABASE_URL"], min_size=kw.pop("min_size", 2),
        max_size=kw.pop("max_size", 10), statement_cache_size=cache, **kw)


@asynccontextmanager
async def tenant_tx(pool: asyncpg.Pool, user_id: str | None, org_id: str | None):
    """Transaction-local tenant context. Never session-level SET."""
    async with pool.acquire() as conn:
        t0 = time.perf_counter()                       # BEGIN to COMMIT; the wait for a free connection is not part of it
        try:
            async with conn.transaction():
                await conn.execute(
                    "select set_config('app.user_id',$1,true), set_config('app.tenant_id',$2,true)",
                    user_id or "", org_id or "")
                yield conn
        finally:
            timing.add("db_tx", time.perf_counter() - t0)
