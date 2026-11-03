"""Two-step verification enforcement. The second factor is Supabase's TOTP: a token with `aal2` proves it, and its `amr` claim says when the
authenticator code was last entered. Nothing here stores or checks codes."""
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

from fastapi import HTTPException

from app.app.audit import audit
from app.app.revocation import session_uuid
from app.app.settings import stepup_max_age
from app.core.ports import AuthError, AuthUnavailable, Principal
from app.db import tenant_tx
from app.db.repos import auth_sessions as sessions_repo
from app.db.repos import memberships as memberships_repo
from app.db.repos import orgs as orgs_repo
from app.db.repos import security_policy as policy_repo
from app.db.repos import users as users_repo

# Roles that must use two-step verification in every organisation (an organisation may add roles, never remove these).
ALWAYS_MFA_ROLES = frozenset({"client_admin", "super_admin", "consultant"})
MFA_REQUIRED = {"code": "mfa_required", "action": "enrol_or_verify"}


def totp_age(p: Principal, now: float | None = None) -> float | None:
    """Seconds since the authenticator code was last entered in this session, or None when the token has no TOTP entry."""
    stamps = [t for m, t in p.amr if m == "totp" and t is not None]
    return (now if now is not None else time.time()) - max(stamps) if stamps else None


def require_aal2(p: Principal) -> None:
    if p.aal != "aal2":
        raise HTTPException(403, dict(MFA_REQUIRED))


async def role_requires_mfa(c, role: str) -> bool:
    """Does this role need two-step verification in the organisation the transaction is set to? The fixed roles always do; an organisation can add roles."""
    return role in ALWAYS_MFA_ROLES or role in (await policy_repo.required_roles(c) or ())


@dataclass
class TwoStep:
    """Where one person stands on two-step verification in one organisation."""
    required: bool                          # their role needs it
    enrolled: bool                          # they have an authenticator (this token is aal2, or the API has seen a verified code from them)
    grace_until: datetime | None = None     # not enrolled, role needs it: when the grace ends (None otherwise)
    blocked: bool = False                   # requests at the first sign-in level are refused with 403 `mfa_required`


def _pool(ctx):
    return getattr(ctx, "pool", None) or ctx.request.app.state.pool


def defer_audit(ctx, action: str, detail: dict | None = None, *, once: bool = False) -> None:
    """Audit rows about the person's two-step state are written after the request's own transaction ends (`flush_audit`): the audit trail is a hash chain with one lock per
    organisation, and a refusal of a sensitive action writes its own row on another connection while this transaction is still open."""
    if not hasattr(ctx, "pending_audit"):
        ctx.pending_audit = []
    ctx.pending_audit.append((action, detail, once))


async def flush_audit(pool, ctx) -> None:
    events, ctx.pending_audit = getattr(ctx, "pending_audit", []), []
    if not events or not getattr(ctx, "org_id", ""):
        return
    async with tenant_tx(pool, ctx.user_id, ctx.org_id) as c:
        for action, detail, once in events:
            if once and not await memberships_repo.grace_expired(c, uuid.UUID(ctx.org_id)):      # the mark that says the end of the grace has been written: only the first caller gets True
                continue
            await audit(c, SimpleNamespace(user_id=ctx.user_id, org_id=ctx.org_id, impersonator=""), action, None, detail)


async def two_step_state(c, ctx, role: str) -> TwoStep:
    """The rule, in one place. A required role at aal2 is fine. Enrolled but still at aal1: always challenged, never given a grace. Not enrolled: allowed at aal1 during the grace
    (started the first time the API sees the requirement, `mfa_grace_days` long), refused once it is over. The first request to see the start or the end of a grace
    also queues the audit row for it (written when the transaction is over, once each). `ctx` carries `principal`, `user_id` and `org_id`."""
    p = ctx.principal
    verified, _ = await users_repo.mfa_state(c, uuid.UUID(ctx.user_id))
    enrolled = p.aal == "aal2" or verified is not None
    if not await role_requires_mfa(c, role):
        return TwoStep(False, enrolled)
    if p.aal == "aal2":
        return TwoStep(True, True)
    if enrolled:
        return TwoStep(True, True, None, True)
    org, user = uuid.UUID(ctx.org_id), uuid.UUID(ctx.user_id)
    until, expired = await memberships_repo.grace_until(c, org, user)
    if until is None:                                              # first sight of the requirement: the grace starts now, and stays started even if this request is refused
        days = await policy_repo.grace_days(c)
        async with tenant_tx(_pool(ctx), ctx.user_id, ctx.org_id) as own:
            await memberships_repo.grace_start(own, org, days)
        until, expired = await memberships_repo.grace_until(c, org, user)
        if until is not None:
            defer_audit(ctx, "mfa.grace_started", {"ends": until.isoformat()})
    if expired:
        defer_audit(ctx, "mfa.grace_expired", {"ended": until.isoformat()}, once=True)
    return TwoStep(True, False, until, expired)


async def enforce_role_policy(c, o, role: str) -> None:
    """Administrators, consultants and the roles the organisation lists must present an aal2 token, unless they are still inside their grace. Support sessions are enforced where they start."""
    if (await two_step_state(c, o, role)).blocked:
        raise HTTPException(403, dict(MFA_REQUIRED))


# The actions that always need a live session and a fresh authenticator code, in every organisation. An organisation can ask for more (ORG_SENSITIVE), never for fewer.
FIXED_SENSITIVE = frozenset({"billing.change_plan", "billing.payment_method", "apikey.create", "apikey.revoke", "impersonation.start",
                             "member.role_changed", "member.removed", "erasure", "export.respondent_data",
                             "webhook.create", "webhook.delete", "retention.change", "processor.change",
                             "password.change", "email.change", "mfa.factor_removed", "session.revoke_all",
                             "invitation.elevated", "security.policy_change", "mfa.grace_change"})
# Extra actions an organisation can ask to be protected as well (never fewer than the fixed list). None are offered today: the four that used to depend on the organisation's
# "re-verify" switch are fixed since build step 3, so the `security_policy.reverify_sensitive` column is kept but no longer read for them.
ORG_SENSITIVE: frozenset[str] = frozenset()
LOWEST_ROLE = "employee"                              # an invitation for any other role is an elevated one
log = logging.getLogger("app.security")


async def account_audit(ctx, action: str, target: str | None, detail: dict | None = None) -> None:
    """An account-level event (no organisation of its own) is written to the audit trail of every organisation the user belongs to, so each administrator can see it."""
    pool = ctx.request.app.state.pool
    async with tenant_tx(pool, ctx.user_id, None) as c:
        orgs = [o.id for o in await orgs_repo.list_for_user(c)]
    for oid in orgs:
        async with tenant_tx(pool, ctx.user_id, str(oid)) as c:
            await audit(c, SimpleNamespace(user_id=ctx.user_id, org_id=str(oid), impersonator=""), action, target, detail)


async def _refuse(ctx, action: str, reason: str, org_id: str | None) -> None:
    """Every refusal is recorded (repeated refusals are what monitoring looks for): a warning line, an audit row in its own transaction (the request's is rolled back),
    and, for a session the provider no longer accepts, our own revocation so the token stops working on every route at once."""
    org = org_id or getattr(ctx, "org_id", "")
    log.warning("sensitive action refused: action=%s reason=%s user=%s org=%s", action, reason, ctx.user_id, org)
    pool, p = ctx.request.app.state.pool, ctx.principal
    try:
        if action == "impersonation.start":                                                  # staff are not members of the customer's organisation: the platform audit takes it
            async with tenant_tx(pool, ctx.user_id, None) as c:
                await c.execute("select app.platform_audit_note('sensitive.refused', $1, $2::jsonb)", action, json.dumps({"reason": reason, "org": org}))
        elif org:
            async with tenant_tx(pool, ctx.user_id, org) as c:
                await audit(c, SimpleNamespace(user_id=ctx.user_id, org_id=org, impersonator=""), "sensitive.refused", action, {"reason": reason})
        else:
            await account_audit(ctx, "sensitive.refused", action, {"reason": reason})
        if reason == "session_revoked" and (sid := session_uuid(p)) is not None:
            async with pool.acquire() as c:
                await sessions_repo.revoke(c, sid, p.issuer, p.subject)
            ctx.request.app.state.container.revocations.forget(p.subject)
    except Exception:
        log.exception("could not record a refused sensitive action")                       # never hides the refusal itself


async def _has_enrolled(ctx) -> bool:
    """Does this person have an authenticator at all? Decides whether the screen asks for a code or tells them to set one up (a person inside their grace has none)."""
    if ctx.principal.aal == "aal2":
        return True
    async with tenant_tx(ctx.request.app.state.pool, ctx.user_id, None) as c:
        verified, _ = await users_repo.mfa_state(c, uuid.UUID(ctx.user_id))
    return verified is not None


async def require_sensitive(ctx, action: str, c=None, *, org_id: str | None = None, check_code: bool = True) -> None:
    """Called by a route after the token (offline) and the role are accepted. Then, in this order: (1) the identity provider is asked, uncached, whether the session is still
    good (401 `session_revoked`: the app signs out instead of asking for a code; 503 `auth_unavailable` when it cannot be reached: fail closed); (2) the authenticator code
    must be newer than AUTH_STEPUP_MAX_AGE_SECONDS, read from the token's `amr` entry for `totp` (403 `step_up_required`, with the window so the screen can say it).
    `c` is only needed for an ORG_SENSITIVE action, which applies when the organisation turned its switch on. The route writes the audit row of an allowed action."""
    if action in ORG_SENSITIVE:
        if not await policy_repo.reverify_sensitive(c):
            return
    elif action not in FIXED_SENSITIVE:
        raise ValueError(f"not a sensitive action: {action}")
    bearer = ctx.request.headers.get("authorization", "")[7:].strip()
    try:
        await ctx.request.app.state.container.auth.alive(bearer)
    except AuthUnavailable:
        await _refuse(ctx, action, "auth_unavailable", org_id)
        raise HTTPException(503, {"code": "auth_unavailable"}, headers={"Retry-After": "5"}) from None
    except AuthError:
        await _refuse(ctx, action, "session_revoked", org_id)
        raise HTTPException(401, {"code": "session_revoked"}) from None
    age = totp_age(ctx.principal)
    if check_code and (ctx.principal.aal != "aal2" or age is None or age > stepup_max_age()):
        await _refuse(ctx, action, "step_up_required", org_id)
        raise HTTPException(403, {"code": "step_up_required", "enrolled": await _has_enrolled(ctx), "max_age_seconds": stepup_max_age()})
