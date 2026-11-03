"""Build step 4: the two-step grace period.
Not enrolled and inside the grace -> the first sign-in level (aal1) works on ordinary routes, sensitive actions still need a code (`step_up_required`, `enrolled: false`).
Not enrolled and grace over -> 403 `mfa_required`. Enrolled -> always a challenge at aal1, no grace. Times are moved with the owner connection, not by waiting."""
import json
import time
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from tests.dsn import OWNER as OWNER_DSN
from tests.integration import test_ai_budget as b


async def owner_exec(sql: str, *args):
    c = await asyncpg.connect(OWNER_DSN)
    try:
        return await c.fetch(sql, *args)
    finally:
        await c.close()


async def audit_actions(org: str) -> list[str]:
    rows = await owner_exec("select action from audit_log where org_id=$1::uuid order by id", org)
    return [r["action"] for r in rows]


async def new_admin(make_user, client, name="Grace org"):
    """An administrator who has never presented an authenticator code: the organisation was created with a first-level token."""
    u = make_user(); org = await u.create_org(name, mfa=False)
    return u, org


async def end_grace(org: str, user: "object"):
    await owner_exec("update memberships set mfa_grace_until = now() - interval '1 day' where org_id=$1::uuid and user_id=(select user_id from identities where subject=$2)", org, user.sub)


async def test_a_new_administrator_works_at_the_first_level_during_the_grace_and_it_is_audited_once(make_user, client):
    u, org = await new_admin(make_user, client)
    h = u.headers(org, mfa=False)
    assert (await client.get("/v1/surveys", headers=h)).status_code == 200
    assert (await client.get("/v1/surveys", headers=h)).status_code == 200
    me = (await client.get("/v1/me", headers=h)).json()
    assert me["mfa_required"] is False and me["enrolled"] is False and me["badges"] is not None
    ends = datetime.fromisoformat(me["grace_ends_at"])
    assert timedelta(days=13, hours=23) < ends - datetime.now(UTC) < timedelta(days=14, hours=1)
    assert (await audit_actions(org)).count("mfa.grace_started") == 1


async def test_a_sensitive_action_in_the_grace_still_needs_a_code_and_says_there_is_none(make_user, client):
    u, org = await new_admin(make_user, client)
    r = await client.post("/v1/api-keys", json={"name": "k", "scopes": ["responses:read"]}, headers=u.headers(org, mfa=False))
    assert r.status_code == 403 and r.json()["detail"]["code"] == "step_up_required" and r.json()["detail"]["enrolled"] is False


async def test_when_the_grace_is_over_the_first_level_is_refused_and_the_expiry_is_audited_once(make_user, client):
    u, org = await new_admin(make_user, client)
    h = u.headers(org, mfa=False)
    assert (await client.get("/v1/surveys", headers=h)).status_code == 200
    await end_grace(org, u)
    for _ in range(2):
        r = await client.get("/v1/surveys", headers=h)
        assert r.status_code == 403 and r.json()["detail"]["code"] == "mfa_required"
    me = (await client.get("/v1/me", headers=h)).json()
    assert me["mfa_required"] is True and me["grace_ends_at"] is None and me["badges"] is None and me["enrolled"] is False
    assert (await audit_actions(org)).count("mfa.grace_expired") == 1
    assert (await client.get("/v1/surveys", headers=u.headers(org))).status_code == 200            # a code (aal2) is accepted again at once


async def test_an_organisation_with_no_grace_refuses_the_first_level_straight_away(make_user, client, app):
    u, org = await new_admin(make_user, client)
    b.POOL[:] = [app.state.pool]
    await b.owner("insert into security_policy(org_id, require_mfa_roles, reverify_sensitive, mfa_grace_days) values($1::uuid, '{}', false, 0)", org, org=org)
    r = await client.get("/v1/surveys", headers=u.headers(org, mfa=False))
    assert r.status_code == 403 and r.json()["detail"]["code"] == "mfa_required"


async def test_an_enrolled_administrator_at_the_first_level_is_challenged_and_never_gets_a_grace(make_user, client):
    u = make_user(); org = await u.create_org()                                                   # created with an aal2 token: the API has seen their code
    assert (await client.get("/v1/surveys", headers=u.headers(org))).status_code == 200
    r = await client.get("/v1/surveys", headers=u.headers(org, mfa=False))
    assert r.status_code == 403 and r.json()["detail"]["code"] == "mfa_required"
    me = (await client.get("/v1/me", headers=u.headers(org, mfa=False))).json()
    assert me["enrolled"] is True and me["mfa_required"] is True and me["grace_ends_at"] is None and me["mfa_last_verified_at"]
    assert "mfa.grace_started" not in await audit_actions(org)


async def test_enrolling_is_audited_once_in_every_organisation(make_user, client):
    u = make_user(); one = await u.create_org("One", mfa=False); two = await u.create_org("Two", mfa=False)
    assert "mfa.enrolled" not in await audit_actions(one)
    assert (await client.get("/v1/surveys", headers=u.headers(one))).status_code == 200            # the first token with a verified code
    assert (await client.get("/v1/surveys", headers=u.headers(one))).status_code == 200
    for org in (one, two):
        assert (await audit_actions(org)).count("mfa.enrolled") == 1


async def test_removing_the_last_factor_clears_the_record_and_the_person_gets_a_new_grace_not_a_free_pass(make_user, client, app):
    u = make_user(); org = await u.create_org()
    assert (await client.get("/v1/surveys", headers=u.headers(org))).status_code == 200            # enrolled
    app.state.container.auth.factors[u.sub] = 0                                                     # the provider says: no factors left
    r = await client.post("/v1/me/mfa-sync", headers=u.headers(org, mfa=False))
    assert r.status_code == 200 and r.json() == {"enrolled": False}
    me = (await client.get("/v1/me", headers=u.headers(org, mfa=False))).json()
    assert me["enrolled"] is False and me["mfa_last_verified_at"] is None and me["mfa_required"] is False and me["grace_ends_at"]   # a grace starts now
    app.state.container.auth.factors[u.sub] = 1
    assert (await client.post("/v1/me/mfa-sync", headers=u.headers(org, mfa=False))).json() == {"enrolled": True}
    assert (await client.get("/v1/me", headers=u.headers(org, mfa=False))).json()["mfa_required"] is True      # enrolled again: challenged


async def test_sync_needs_a_live_session_and_a_provider_that_answers(make_user, client, app):
    u = make_user(); org = await u.create_org()
    auth = app.state.container.auth
    auth.down = True
    try:
        assert (await client.post("/v1/me/mfa-sync", headers=u.headers(org))).status_code == 503
    finally:
        auth.down = False
    assert (await client.post("/v1/me/mfa-sync")).status_code == 401


async def test_remind_me_later_snoozes_for_a_day(make_user, client):
    u, org = await new_admin(make_user, client)
    h = u.headers(org, mfa=False)
    assert (await client.get("/v1/me", headers=h)).json()["nudge_snoozed_until"] is None
    r = await client.post("/v1/me/mfa-nudge", headers=h)
    until = datetime.fromisoformat(r.json()["snoozed_until"])
    assert timedelta(hours=23) < until - datetime.now(UTC) < timedelta(hours=25)
    assert (await client.get("/v1/me", headers=h)).json()["nudge_snoozed_until"] == r.json()["snoozed_until"]


async def test_a_new_role_starts_a_new_grace(make_user, client):
    from tests.integration.test_distribution_flow import invite_member
    a, m = make_user(), make_user()
    org = await a.create_org()
    await invite_member(client, a, org, m, role="analyst")
    await owner_exec("update memberships set mfa_grace_until = now() + interval '2 days' where org_id=$1::uuid and user_id=(select user_id from identities where subject=$2)", org, m.sub)
    uid = next(x["user_id"] for x in (await client.get("/v1/members", headers=a.headers(org))).json()["members"] if x["email"] == m.email)
    assert (await client.put(f"/v1/members/{uid}", json={"role": "viewer"}, headers=a.headers(org))).status_code == 200
    rows = await owner_exec("select mfa_grace_until from memberships where org_id=$1::uuid and user_id=$2::uuid", org, uid)
    assert rows[0]["mfa_grace_until"] is None


async def test_the_organisation_chooses_the_grace_between_0_and_30_days_and_it_is_a_sensitive_change(make_user, client):
    u = make_user(); org = await u.create_org()
    h = u.headers(org)
    assert (await client.get("/v1/security/policy", headers=h)).json()["mfa_grace_days"] == 14
    for bad in (-1, 31):
        assert (await client.put("/v1/security/policy", json={"mfa_grace_days": bad}, headers=h)).status_code == 422
    r = await client.put("/v1/security/policy", json={"mfa_grace_days": 7}, headers=h)
    assert r.status_code == 200 and r.json()["mfa_grace_days"] == 7
    assert (await client.put("/v1/security/policy", json={"require_mfa_roles": ["analyst"]}, headers=h)).json()["mfa_grace_days"] == 7        # untouched by a partial update
    stale = await client.put("/v1/security/policy", json={"mfa_grace_days": 3}, headers=u.headers(org, totp_at=int(time.time()) - 3600))
    assert stale.status_code == 403 and stale.json()["detail"]["code"] == "step_up_required"
    assert json.loads(json.dumps((await client.get("/v1/security/policy", headers=h)).json()))["mfa_grace_days"] == 7


@pytest.mark.security
async def test_during_the_grace_the_whole_api_is_open_only_where_it_was_open_to_an_analyst_at_the_first_level(make_user, client, app):
    """The grace lets a not-yet-enrolled person work; it must not let a sensitive route through (the table in test_sensitive_actions covers each by name)."""
    u, org = await new_admin(make_user, client)
    h = u.headers(org, mfa=False)
    bad = []
    for path in ("/v1/api-keys", "/v1/webhooks"):
        r = await client.post(path, json={"name": "k", "scopes": ["responses:read"], "url": "https://hooks.example.com/x", "events": ["ping"]}, headers=h)
        if r.status_code in (200, 201):
            bad.append(path)
    assert not bad
