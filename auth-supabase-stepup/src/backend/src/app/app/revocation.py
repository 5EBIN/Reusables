"""Refuses tokens that are valid but revoked: a session signed out, or every token a user held before "sign out everywhere" / a password change / removal from every
organisation. The answer is cached per (user, session) for AUTH_REVOCATION_CACHE_SECONDS; a revocation made by this process clears the cache at once."""
import hashlib
import time
import uuid
from collections.abc import Callable

from fastapi import Request

from app.app.clientip import client_ip
from app.core.ports import AuthError, Principal
from app.db.repos import auth_sessions as repo

MAX_ENTRIES = 20_000


def device_label(user_agent: str) -> str:
    ua = user_agent[:200]
    browser = next((b for b in ("Edg", "Chrome", "Firefox", "Safari") if b in ua), "Browser")
    os_ = next((o for o in ("iPhone", "Android", "Windows", "Mac OS", "Linux") if o in ua), "device")
    return f"{browser.replace('Edg', 'Edge')} · {os_.replace('Mac OS', 'macOS')}"


def session_uuid(p: Principal) -> uuid.UUID | None:
    try:
        return uuid.UUID(p.session_id) if p.session_id else None
    except ValueError:
        return None


async def purge_revocations(pool) -> int:
    """Scheduler step: rows past their expiry (the tokens they covered have expired too) are deleted."""
    async with pool.acquire() as c:
        return await repo.purge(c)


class Revocations:
    def __init__(self, ttl: float, clock: Callable[[], float] = time.monotonic):
        self.ttl, self.clock = ttl, clock
        self._ok: dict[tuple[str, str | None], float] = {}                 # (subject, session) -> remembered until

    def forget_all(self) -> None:
        self._ok.clear()

    def forget(self, subject: str) -> None:
        for k in [k for k in self._ok if k[0] == subject]:
            del self._ok[k]

    async def check(self, request: Request, p: Principal) -> None:
        key = (p.subject, p.session_id)
        if self._ok.get(key, 0.0) > self.clock():
            return
        ua = request.headers.get("user-agent", "")
        async with request.app.state.pool.acquire() as c:
            v = await repo.check(c, p.issuer, p.subject, session_uuid(p), device_label(ua), hashlib.sha256(client_ip(request).encode()).hexdigest())
        if v.session_revoked or (v.user_not_before is not None and (p.iat is None or p.iat <= int(v.user_not_before.timestamp()))):
            self.forget(p.subject)
            raise AuthError("revoked")
        if len(self._ok) >= MAX_ENTRIES:
            self._ok.clear()                                               # bounded; the next requests simply ask again
        self._ok[key] = self.clock() + self.ttl
