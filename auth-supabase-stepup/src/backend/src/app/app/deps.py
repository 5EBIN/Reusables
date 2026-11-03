import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import Header, HTTPException, Request

from app.core import timing
from app.core.ports import AuthError, Principal
from app.db import tenant_tx
from app.db.repos import users as users_repo


def container(request: Request):
    return request.app.state.container


async def current_principal(request: Request, authorization: str = Header(default="")) -> Principal:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "unauthorized")
    try:
        with timing.timed("auth"):
            p = await container(request).auth.averify(authorization[7:].strip())
        with timing.timed("revocation"):
            await container(request).revocations.check(request, p)             # signed out, or "sign out everywhere" since this token was issued
        return p
    except AuthError:
        raise HTTPException(401, "unauthorized") from None


_NOTED: dict[str, float] = {}                      # user id -> when this process last recorded a verified authenticator code for them
_NOTE_EVERY = 3600.0


def forget_authenticator(uid: str) -> None:
    _NOTED.pop(uid, None)


async def _note_authenticator(request: Request, p: Principal, uid: str) -> None:
    """A token at aal2 with a `totp` entry in `amr` means the person has an authenticator: remember it (the database writes it at most once an hour; this skips even asking)."""
    if p.aal != "aal2" or not any(m == "totp" for m, _ in p.amr):
        return
    now = time.monotonic()
    if now - _NOTED.get(uid, -_NOTE_EVERY) < _NOTE_EVERY:
        return
    _NOTED[uid] = now
    async with tenant_tx(request.app.state.pool, uid, None) as c:
        first = await users_repo.note_mfa_verified(c)
    if first:
        from app.app.security import account_audit
        await account_audit(UserCtx(request, p, uid), "mfa.enrolled", None)


async def current_user_id(request: Request, p: Principal) -> str:
    """Map (issuer, subject) -> users.id, auto-provision on first login (no memberships)."""
    with timing.timed("provision"):
        async with request.app.state.pool.acquire() as c:
            uid = str(await users_repo.provision(c, p.issuer, p.subject, p.email))
    await _note_authenticator(request, p, uid)
    return uid


@dataclass
class UserCtx:
    request: Request
    principal: Principal
    user_id: str

    @asynccontextmanager
    async def user_tx(self):
        async with tenant_tx(self.request.app.state.pool, self.user_id, None) as c:
            yield c


@dataclass
class OrgCtx(UserCtx):
    org_id: str = ""
    role: str = ""
    impersonator: str = ""          # staff user id when a support session is viewing this org (read-only)

    @asynccontextmanager
    async def tx(self, roles: set[str] | None = None):
        """Tenant transaction; membership verified in the same transaction. Header alone is never trusted."""
        try:
            async with tenant_tx(self.request.app.state.pool, self.user_id, self.org_id) as c:
                if self.impersonator:
                    await c.execute("set local transaction_read_only = on")          # support sessions can never write
                    self.role = "support"
                    yield c
                    return
                role = await c.fetchval("select role from memberships where user_id=$1 and org_id=$2 and (expires_at is null or expires_at > now())",
                                        uuid.UUID(self.user_id), uuid.UUID(self.org_id))
                if role is None or (roles and role not in roles):
                    raise HTTPException(403, "forbidden")
                from app.app.security import enforce_role_policy
                await enforce_role_policy(c, self, role)
                self.role = role
                yield c
        finally:
            from app.app.security import flush_audit
            await flush_audit(self.request.app.state.pool, self)               # the start or end of a two-step grace seen by this request


async def user_ctx(request: Request, authorization: str = Header(default="")) -> UserCtx:
    p = await current_principal(request, authorization)
    return UserCtx(request, p, await current_user_id(request, p))


async def org_ctx(request: Request, authorization: str = Header(default=""),
                  x_org_id: str = Header(default=""), x_impersonation: str = Header(default="")) -> OrgCtx:
    p = await current_principal(request, authorization)
    try:
        org = str(uuid.UUID(x_org_id))
    except ValueError:
        raise HTTPException(400, "X-Org-Id required") from None
    uid = await current_user_id(request, p)
    ctx = OrgCtx(request, p, uid, org)
    if x_impersonation:
        if request.method not in ("GET", "HEAD"):
            raise HTTPException(403, "impersonation sessions are read-only")
        import hashlib
        async with tenant_tx(request.app.state.pool, uid, None) as c:
            row = await c.fetchrow("select * from app.resolve_impersonation($1)", hashlib.sha256(x_impersonation.encode()).hexdigest())
        if row is None or str(row["i_staff"]) != uid or str(row["i_org"]) != org:
            raise HTTPException(403, "invalid or expired support session")
        ctx.impersonator = uid
        request.state.impersonating = True
    return ctx
