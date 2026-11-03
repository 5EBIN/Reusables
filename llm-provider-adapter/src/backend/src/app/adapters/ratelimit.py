"""Rate limiters. Call sites use `await limiter.hit(key)`.

MemoryRateLimiter: per process (tests/dev); evicts empty keys and bounds the key count so random keys cannot grow memory without limit.
PgRateLimiter: shared across processes, fixed window per key via the atomic SQL function app.rate_limit_hit (UNLOGGED table).
"""
import hashlib
import time
from collections import deque


class MemoryRateLimiter:
    def __init__(self, limit: int = 10, window: float = 60.0, max_keys: int = 50_000):
        self.limit, self.window, self.max_keys = limit, window, max_keys
        self.hits: dict[str, deque] = {}
        self._sweep_at = 0.0

    def _sweep(self, now: float) -> None:
        for k in [k for k, q in self.hits.items() if not q or now - q[-1] > self.window]:
            del self.hits[k]
        self._sweep_at = now

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        q = self.hits.get(key)
        if q is not None:
            while q and now - q[0] > self.window:
                q.popleft()
            if not q:
                del self.hits[key]
                q = None
        if now - self._sweep_at > self.window:
            self._sweep(now)
        if q is None:
            if len(self.hits) >= self.max_keys:
                self._sweep(now)
                while len(self.hits) >= self.max_keys:
                    del self.hits[next(iter(self.hits))]               # oldest key first
            q = self.hits[key] = deque()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True

    async def hit(self, key: str) -> bool:
        return self.allow(key)


class PgRateLimiter:
    def __init__(self, limit: int, window: float, scope: str, pool=None):
        self.limit, self.window, self.scope, self.pool = limit, window, scope, pool

    def bind(self, pool) -> None:
        self.pool = pool

    async def hit(self, key: str) -> bool:
        if self.pool is None:
            raise RuntimeError("PgRateLimiter used before bind(pool)")
        k = f"{self.scope}:{hashlib.sha256(key.encode()).hexdigest()}"          # fixed-size key whatever the caller passes
        async with self.pool.acquire() as c:
            return bool(await c.fetchval("select app.rate_limit_hit($1,$2,$3)", k, self.limit, float(self.window)))
