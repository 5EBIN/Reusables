"""Logout and "sign out everywhere" for tokens that are otherwise valid: a revoked session or user stops working on the next request."""
import time
import types
import uuid

import asyncpg
import pytest

from app.app import revocation
from app.app.revocation import Revocations
from app.app.scheduler import tick_all
from app.core.ports import AuthError, Principal
from app.db import tenant_tx
from tests.dsn import OWNER as OWNER_DSN
from tests.integration.test_distribution_flow import invite_member

UA = {"User-Agent": "Mozilla/5.0 (iPhone) Safari"}


def session(u, **kw):
    return u.headers(session_id=str(uuid.uuid4()), **kw)


async def owner(sql, *args):
    c = await asyncpg.connect(OWNER_DSN)
    try:
        return await c.fetch(sql, *args)
    finally:
        await c.close()


@pytest.mark.security
async def test_logout_ends_that_session_only(make_user, client):
    u = make_user(); await u.create_org()
    a, b = session(u), session(u)
    assert (await client.get("/v1/me", headers=a)).status_code == 200 and (await client.get("/v1/me", headers=b)).status_code == 200
    assert (await client.post("/v1/auth/revoke", headers=a)).status_code == 204
    assert (await client.get("/v1/me", headers=a)).status_code == 401                         # the same access token, reused after logout
    assert (await client.get("/v1/me", headers=b)).status_code == 200                         # a second session of the same user survives


@pytest.mark.security
async def test_sign_out_everywhere_refuses_every_older_token(make_user, client, app):
    u = make_user(); await u.create_org()
    now = int(time.time())
    old1, old2 = session(u, iat=now - 120), session(u, iat=now - 60)
    assert (await client.get("/v1/me", headers=old1)).status_code == 200
    assert (await client.post("/v1/auth/revoke-all", headers=old2)).status_code == 204       # e.g. after a password change
    assert (await client.get("/v1/me", headers=old1)).status_code == 401 and (await client.get("/v1/me", headers=old2)).status_code == 401
    cut = int((await owner("select extract(epoch from not_before) e from auth_revocations where kind='user' and id=$1", u.sub))[0]["e"])
    assert (await client.get("/v1/me", headers=session(u, iat=cut))).status_code == 401       # issued in the same second as the cut-off: refused, the safe side
    await owner("update auth_revocations set not_before = now() - interval '60 seconds' where kind='user'")   # one minute later
    app.state.container.revocations.forget_all()
    assert (await client.get("/v1/me", headers=session(u))).status_code == 200                # a token issued after the cut-off works
    assert (await client.get("/v1/me", headers=session(u, iat=now - 120))).status_code == 401


@pytest.mark.security
async def test_a_user_recorded_as_revoked_is_refused(make_user, client, app):
    """What an administrator's "disable" would record (no such action exists in the product yet): any token issued before the cut-off stops working."""
    u = make_user(); await u.create_org()
    tok = session(u, iat=int(time.time()) - 30)
    assert (await client.get("/v1/me", headers=tok)).status_code == 200
    uid = (await client.get("/v1/me", headers=tok)).json()["user_id"]
    async with tenant_tx(app.state.pool, uid, None) as c:
        assert await c.fetchval("select app.revoke_user($1)", uuid.UUID(uid)) is True
    app.state.container.revocations.forget_all()
    assert (await client.get("/v1/me", headers=tok)).status_code == 401


@pytest.mark.security
async def test_removal_from_the_last_organisation_ends_every_token(make_user, client):
    admin, gone, stays = make_user(), make_user(), make_user()
    org = await admin.create_org(); other = await stays.create_org()
    await invite_member(client, admin, org, gone, role="viewer")
    await invite_member(client, admin, org, stays, role="viewer")
    ig = (await client.get("/v1/me", headers=gone.headers())).json()["user_id"]
    ist = (await client.get("/v1/me", headers=stays.headers())).json()["user_id"]
    tok_gone, tok_stays = session(gone, iat=int(time.time()) - 30), session(stays, iat=int(time.time()) - 30)
    assert (await client.get("/v1/me", headers=tok_gone)).status_code == 200
    assert (await client.delete(f"/v1/members/{ig}", headers=admin.headers(org))).status_code == 204
    assert (await client.get("/v1/me", headers=tok_gone)).status_code == 401                  # in no organisation any more: signed out everywhere
    assert (await client.delete(f"/v1/members/{ist}", headers=admin.headers(org))).status_code == 204
    assert (await client.get("/v1/me", headers=tok_stays)).status_code == 200                 # still in another organisation: not signed out
    assert other


@pytest.mark.security
async def test_nobody_can_revoke_another_users_sessions_or_tokens(make_user, client, app):
    a, b = make_user(), make_user()
    await a.create_org(); await b.create_org()
    ta = session(a)
    assert (await client.get("/v1/me", headers=ta)).status_code == 200
    ia = (await client.get("/v1/me", headers=a.headers())).json()["user_id"]
    sid = (await client.get("/v1/security/sessions", headers=ta)).json()["items"][0]["id"]
    assert (await client.delete(f"/v1/security/sessions/{sid}", headers=b.headers())).status_code == 404       # not theirs
    async with tenant_tx(app.state.pool, (await client.get("/v1/me", headers=b.headers())).json()["user_id"], None) as c:
        assert await c.fetchval("select app.revoke_user($1)", uuid.UUID(ia)) is False
    assert (await client.get("/v1/me", headers=ta)).status_code == 200
    async with app.state.pool.acquire() as c:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await c.fetch("select * from auth_revocations")                                  # only reachable through the functions


async def test_the_session_list_is_what_the_api_has_seen_and_revoking_one_signs_it_out(make_user, client):
    u = make_user(); await u.create_org()
    sa, sb = str(uuid.uuid4()), str(uuid.uuid4())
    a, b = u.headers(session_id=sa), u.headers(session_id=sb)
    await client.get("/v1/me", headers={**a, **UA}); await client.get("/v1/me", headers=b)
    items = {i["id"]: i for i in (await client.get("/v1/security/sessions", headers=a)).json()["items"]}
    assert {sa, sb} <= set(items) and items[sa]["device"] == "Safari · iPhone"
    assert (await client.delete(f"/v1/security/sessions/{sb}", headers=a)).status_code == 204
    assert (await client.get("/v1/me", headers=b)).status_code == 401
    assert sb not in {i["id"] for i in (await client.get("/v1/security/sessions", headers=a)).json()["items"]}


async def test_expired_revocations_are_deleted_by_the_scheduler(make_user, client, app):
    gone, live = f"gone-{uuid.uuid4().hex}", f"live-{uuid.uuid4().hex}"                       # unique per run: other tests also tick the scheduler
    await owner("insert into auth_revocations(kind,id,expires_at) values ('user',$1, now() - interval '1 minute'), ('session',$2, now() + interval '1 hour')", gone, live)
    out = await tick_all(app.state.pool, app.state.container, only={"revocation_purge"})
    assert out["revocation_purge"] != "error"
    ids = {r["id"] for r in await owner("select id from auth_revocations")}
    assert live in ids and gone not in ids


# ---- the cache -----------------------------------------------------------------------------------------------------------------------------
class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


async def test_the_answer_is_cached_for_the_configured_time_and_a_local_revocation_clears_it(monkeypatch):
    calls = []

    async def fake_check(c, issuer, subject, sid, device, ip):
        calls.append(subject)
        return revocation.repo.Verdict(session_revoked=subject == "bad", user_not_before=None)

    class Conn:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *a):
            return False

    req = types.SimpleNamespace(headers={}, client=types.SimpleNamespace(host="203.0.113.5"), app=types.SimpleNamespace(state=types.SimpleNamespace(pool=types.SimpleNamespace(acquire=Conn))))
    monkeypatch.setattr(revocation.repo, "check", fake_check)
    clock = Clock()
    r = Revocations(30, clock)
    p = Principal("sub1", "iss", session_id=str(uuid.uuid4()), iat=1)
    await r.check(req, p); await r.check(req, p)
    assert calls == ["sub1"]                                                                  # the second request did not ask the database
    clock.t += 31
    await r.check(req, p)
    assert calls == ["sub1", "sub1"]                                                          # asked again after the cache time
    r.forget("sub1")
    await r.check(req, p)
    assert len(calls) == 3                                                                    # a revocation made here is seen at once
    for _ in range(2):
        with pytest.raises(AuthError):
            await r.check(req, Principal("bad", "iss", session_id=str(uuid.uuid4()), iat=1))   # a refusal is never cached as ok
    assert calls.count("bad") == 2
