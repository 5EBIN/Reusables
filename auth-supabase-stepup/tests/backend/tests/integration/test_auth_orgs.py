import uuid
import pytest

pytestmark = pytest.mark.asyncio


async def test_healthz(client):
    assert (await client.get("/healthz")).json() == {"ok": True}


async def test_a_verified_token_provisions_the_user_on_first_call(make_user, client):
    u = make_user()
    r = await client.get("/v1/me", headers=u.headers())
    assert r.status_code == 200 and r.json()["email"] == u.email
    assert (await client.get("/v1/me", headers=u.headers())).json()["user_id"] == r.json()["user_id"]        # second call links to the same row (the session differs per token)


async def test_unauthenticated_rejected(client):
    for h in ({}, {"Authorization": "Bearer junk"}, {"Authorization": "Basic x"}):
        assert (await client.get("/v1/me", headers=h)).status_code == 401


@pytest.mark.security
async def test_membership_and_switch(make_user, client):
    c, other = make_user(), make_user()
    o1, o2 = await c.create_org("هيئة الاختبار"), await c.create_org("Two")
    o3 = await other.create_org("Three")
    names = {o["name"] for o in (await client.get("/v1/orgs", headers=c.headers())).json()}
    assert names == {"هيئة الاختبار", "Two"}  # Arabic names round-trip
    assert (await client.get("/v1/ctx", headers=c.headers(o1))).status_code == 200
    assert (await client.get("/v1/ctx", headers=c.headers(o2))).status_code == 200
    assert (await client.get("/v1/ctx", headers=c.headers(o3))).status_code == 403   # header alone not trusted
    assert (await client.get(f"/v1/orgs/{o3}", headers=c.headers())).status_code == 404
    assert (await client.get("/v1/ctx", headers=c.headers())).status_code == 400
    assert (await client.get("/v1/ctx", headers=c.headers("not-a-uuid"))).status_code == 400


async def test_autoprovision_no_membership(make_user, client):
    u = make_user()
    assert (await client.get("/v1/orgs", headers=u.headers())).json() == []
    assert (await client.get("/v1/ctx", headers=u.headers(uuid.uuid4()))).status_code == 403


async def test_org_create_replay_and_conflict(make_user, client):
    u, v = make_user(), make_user()
    oid = uuid.uuid4()
    r1 = await client.post("/v1/orgs", json={"id": str(oid), "name": "X"}, headers=u.headers())
    r2 = await client.post("/v1/orgs", json={"id": str(oid), "name": "X"}, headers=u.headers())
    assert r1.status_code == r2.status_code == 201
    assert (await client.post("/v1/orgs", json={"id": str(oid), "name": "X"}, headers=v.headers())).status_code == 409
    for bad in ({"name": ""}, {"name": "x" * 201}, {"id": "nope", "name": "x"}, {}, {"name": 5}, {"name": None}):
        assert (await client.post("/v1/orgs", json=bad, headers=u.headers())).status_code == 422


async def test_org_tenant_isolation(make_user, client):
    u, v = make_user(), make_user()
    o = await u.create_org("Mine")
    assert (await client.get("/v1/orgs", headers=v.headers())).json() == []
    assert (await client.get(f"/v1/orgs/{o}", headers=v.headers())).status_code == 404


async def test_rate_limit_blocks(app, client):
    app.state.container.limiter.limit = 3
    body = {"name": "Ann", "email": "user@example.com", "message": "hello there friend", "consent": True}
    try:
        codes = [(await client.post("/public/v1/site/contact", json=body)).status_code for _ in range(6)]
        assert 429 in codes
    finally:
        app.state.container.limiter.limit = 1000
        app.state.container.limiter.hits.clear()


@pytest.mark.security
async def test_an_invitation_is_accepted_only_by_the_invited_email(make_user, client):
    admin, invited, other = make_user(), make_user(), make_user()
    org = await admin.create_org()
    tok = (await client.post("/v1/members/invite", json={"email": invited.email, "role": "analyst"}, headers=admin.headers(org))).json()["token"]
    wrong = await client.post("/v1/invitations/accept", json={"token": tok}, headers=other.headers())
    assert wrong.status_code == 404                                                       # a forwarded link does not let someone else in
    assert (await client.get("/v1/orgs", headers=other.headers())).json() == []
    ok = await client.post("/v1/invitations/accept", json={"token": tok}, headers=invited.headers())
    assert ok.status_code == 200 and ok.json()["org_id"] == org
    assert [o["id"] for o in (await client.get("/v1/orgs", headers=invited.headers())).json()] == [org]
