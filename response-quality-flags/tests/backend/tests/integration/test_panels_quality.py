import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db import tenant_tx
from tests.integration.test_distribution_flow import invite_member
from tests.integration.test_studio import survey_with

DEF = {"pages": [{"elements": [{"type": "rating", "name": "q1", "rateMin": 1, "rateMax": 5}, {"type": "rating", "name": "q2", "rateMin": 1, "rateMax": 5},
                               {"type": "rating", "name": "q3", "rateMin": 1, "rateMax": 5}, {"type": "comment", "name": "c"}]}]}


# ---------------- quality ----------------
async def quality_world(make_user, client, app):
    u = make_user(); org = await u.create_org(); h = u.headers(org)
    sid, tok = await survey_with(client, h, DEF)
    now = datetime.now(UTC)
    ids = []
    for i in range(10):
        rid = str(uuid.uuid4()); ids.append(rid)
        sl = i == 0
        txt = "asdfghjkl" if i == 1 else "Parking is hard on weekends"
        await client.post(f"/public/v1/c/{tok}/responses", json={"id": rid, "started_at": (now - timedelta(seconds=(5 if i == 2 else 100))).isoformat(), "device_id": "dev-x" if i < 3 else f"d{i}",
                                                                 "answers": [{"q": "q1", "value": 4 if sl else 1 + i % 5}, {"q": "q2", "value": 4 if sl else 2}, {"q": "q3", "value": 4 if sl else 3}, {"q": "c", "value": txt}]})
    return u, org, h, sid, ids


async def test_quality_run_flags_excludes_and_reverses(make_user, client, app):
    u, org, h, sid, ids = await quality_world(make_user, client, app)
    assert (await client.put(f"/v1/surveys/{sid}/quality/rules", json={"straightline": {"min_rows": 3, "treatment": "flag"}, "duplicate_device": {"count": 3, "treatment": "exclude"}}, headers=h)).status_code == 200
    r = (await client.post(f"/v1/surveys/{sid}/quality/run", headers=h)).json()
    assert r["responses"] == 10 and r["flagged"] == 3 and r["excluded"] == 3
    s = (await client.get(f"/v1/surveys/{sid}/quality/summary", headers=h)).json()
    byrule = {x["rule"]: x["flagged"] for x in s["rules"]}
    assert byrule["straightline"] == 1 and byrule["gibberish"] == 1 and byrule["duplicate_device"] == 3 and byrule["speeder"] == 1 and s["method"] == "rule-based"
    assert await client.post(f"/v1/surveys/{sid}/quality/run", headers=h) and (await client.post(f"/v1/surveys/{sid}/quality/run", headers=h)).json() == r   # idempotent
    await client.put(f"/v1/surveys/{sid}/quality/rules", json={"duplicate_device": {"treatment": "off"}, "speeder": {"treatment": "off"}}, headers=h)
    r2 = (await client.post(f"/v1/surveys/{sid}/quality/run", headers=h)).json()
    assert r2["excluded"] == 0                                                                                          # auto-exclusions reversed when rules change


async def test_manual_exclusion_survives_rerun(make_user, client, app):
    u, org, h, sid, ids = await quality_world(make_user, client, app)
    await client.post(f"/v1/surveys/{sid}/responses/{ids[9]}/exclude", json={"excluded": True, "reason": "test respondent"}, headers=h)
    await client.post(f"/v1/surveys/{sid}/quality/run", headers=h)
    async with tenant_tx(app.state.pool, None, org) as c:
        assert await c.fetchval("select exclude_reason from responses where id=$1", uuid.UUID(ids[9])) == "test respondent"


@pytest.mark.security
async def test_quality_validation_and_isolation(make_user, client, app):
    u, org, h, sid, ids = await quality_world(make_user, client, app)
    for bad in ({"nope": {}}, {"speeder": {"pct": 1}}, {"speeder": {"treatment": "drop"}}, {"duplicate_device": {"count": 1}}):
        assert (await client.put(f"/v1/surveys/{sid}/quality/rules", json=bad, headers=h)).status_code == 422
    v = make_user(); org2 = await v.create_org(); h2 = v.headers(org2)
    for m, p in (("get", "rules"), ("post", "run"), ("get", "summary")):
        assert (await getattr(client, m)(f"/v1/surveys/{sid}/quality/{p}", headers=h2)).status_code == 404
    assert (await client.put(f"/v1/surveys/{sid}/quality/rules", json={}, headers=h2)).status_code == 404


# ---------------- panels ----------------
async def panel_world(make_user, client, n=12):
    a, b = make_user(), make_user()
    org = await a.create_org(); await invite_member(client, a, org, b)
    h = a.headers(org)
    sid, _ = await survey_with(client, h, DEF)
    pids = []
    for i in range(n):
        r = await client.post("/v1/panel/panellists", json={"email": f"p{i}-{uuid.uuid4().hex[:6]}@example.ae", "attributes": {"age_band": "18-29" if i % 2 else "45+", "gender": "f", "emirate": "dubai"}, "email_confirmed": True, "consent_version": 4}, headers=h)
        assert r.status_code == 201, r.text
        pids.append(r.json()["id"])
    proj = (await client.post("/v1/panel/projects", json={"name": "Brand wave 2", "survey_id": sid, "target": 6, "quotas": [{"attr": "age_band", "value": "18-29", "target": 3}]}, headers=h)).json()["id"]
    return a, b, org, h, sid, pids, proj


async def test_batch_seeded_deterministic_and_two_person(make_user, client, app):
    a, b, org, h, sid, pids, proj = await panel_world(make_user, client)
    r1 = (await client.post(f"/v1/panel/projects/{proj}/batches", json={"size": 4, "seed": 7}, headers=h)).json()
    assert r1["sampled"] == 4 and r1["seed"] == 7
    assert (await client.post(f"/v1/panel/batches/{r1['id']}/approve", headers=h)).status_code == 403
    ok = await client.post(f"/v1/panel/batches/{r1['id']}/approve", headers=b.headers(org))
    assert ok.json() == {"status": "approved", "invited": 4}
    assert (await client.post(f"/v1/panel/batches/{r1['id']}/approve", headers=b.headers(org))).status_code == 409


async def test_fatigue_limit_stops_over_invitation(make_user, client, app):
    a, b, org, h, sid, pids, proj = await panel_world(make_user, client, n=6)
    for _ in range(3):
        bt = (await client.post(f"/v1/panel/projects/{proj}/batches", json={"size": 6}, headers=h)).json()
        await client.post(f"/v1/panel/batches/{bt['id']}/approve", headers=b.headers(org))
    nxt = (await client.post(f"/v1/panel/projects/{proj}/batches", json={"size": 6}, headers=h)).json()
    assert nxt["sampled"] == 0                                                                  # everyone has 3 invitations in 30 days or quota logic left nobody


async def test_incentive_ledger_two_approvers_append_only(make_user, client, app):
    a, b, org, h, sid, pids, proj = await panel_world(make_user, client)
    bt = (await client.post(f"/v1/panel/projects/{proj}/batches", json={"size": 6, "seed": 1}, headers=h)).json()
    await client.post(f"/v1/panel/batches/{bt['id']}/approve", headers=b.headers(org))
    async with tenant_tx(app.state.pool, None, org) as c:
        pl = str(await c.fetchval("select panellist_id from panel_invites where project_id=$1 limit 1", uuid.UUID(proj)))
    assert (await client.post("/v1/panel/incentives", json={"panellist_id": pl, "project_id": proj, "amount_aed": 25}, headers=h)).status_code == 409   # not completed
    await client.post(f"/v1/panel/projects/{proj}/complete", json={"panellist_id": pl}, headers=h)
    big = (await client.post("/v1/panel/incentives", json={"panellist_id": pl, "project_id": proj, "amount_aed": 75}, headers=h)).json()
    assert (await client.post(f"/v1/panel/incentives/{big['id']}/advance", json={"event": "paid"}, headers=h)).status_code == 409                    # must be approved first
    assert (await client.post(f"/v1/panel/incentives/{big['id']}/advance", json={"event": "approved"}, headers=h)).status_code == 403                  # creator cannot approve >50
    assert (await client.post(f"/v1/panel/incentives/{big['id']}/advance", json={"event": "approved"}, headers=b.headers(org))).status_code == 200
    assert (await client.post(f"/v1/panel/incentives/{big['id']}/advance", json={"event": "paid"}, headers=h)).json()["status"] == "paid"
    small = (await client.post("/v1/panel/incentives", json={"panellist_id": pl, "project_id": proj, "amount_aed": 10}, headers=h)).json()
    assert (await client.post(f"/v1/panel/incentives/{small['id']}/advance", json={"event": "approved"}, headers=h)).status_code == 200
    items = {i["id"]: i["status"] for i in (await client.get("/v1/panel/incentives", headers=h)).json()["items"]}
    assert items[big["id"]] == "paid" and items[small["id"]] == "approved"
    async with tenant_tx(app.state.pool, None, org) as c:
        import asyncpg
        for sql in ("update incentive_entries set amount_aed=1", "delete from incentive_entries", "update incentive_events set event='paid'", "delete from incentive_events"):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with c.transaction():
                    await c.execute(sql)


async def test_project_progress_orders_and_overview(make_user, client, app):
    a, b, org, h, sid, pids, proj = await panel_world(make_user, client)
    p = (await client.get(f"/v1/panel/projects/{proj}", headers=h)).json()
    assert p["quotas"][0]["fill_pct"] == 0 and p["target"] == 6
    ov = (await client.get("/v1/panel/overview", headers=h)).json()
    assert ov["verified"] == 12 and ov["verification"]["email_confirmed"] == 100 and ov["composition"]["age_band"]["18-29"] == 6 and "government ID" in ov["note"]
    o = (await client.post("/v1/panel/orders", json={"brief": "Concept test, UAE adults", "target": 1000}, headers=h)).json()["id"]
    assert (await client.post(f"/v1/panel/orders/{o}/move", json={"status": "quoted"}, headers=b.headers(org))).status_code == 422             # quote required
    assert (await client.post(f"/v1/panel/orders/{o}/move", json={"status": "quoted", "quote_aed": 41000}, headers=b.headers(org))).status_code == 200
    assert (await client.post(f"/v1/panel/orders/{o}/move", json={"status": "delivered"}, headers=b.headers(org))).status_code == 409
    for st in ("approved", "fielding", "quality_check", "delivered"):
        assert (await client.post(f"/v1/panel/orders/{o}/move", json={"status": st}, headers=b.headers(org))).status_code == 200
    assert (await client.get("/v1/panel/orders", headers=h)).json()["items"][0]["status"] == "delivered"


@pytest.mark.security
async def test_panel_privacy_validation_isolation(make_user, client, app):
    a, b, org, h, sid, pids, proj = await panel_world(make_user, client)
    for attrs in ({"emirates_id": "784-1990-1234567-1"}, {"age_band": "784-1990-1234567-1"}, {"passport": "A1234567"}, {"gender": "4111 1111 1111 1111"}):
        assert (await client.post("/v1/panel/panellists", json={"email": f"x{uuid.uuid4().hex[:5]}@example.ae", "attributes": attrs}, headers=h)).status_code == 422
    assert (await client.post("/v1/panel/panellists", json={"email": "not-an-email"}, headers=h)).status_code == 422
    assert (await client.post("/v1/panel/projects", json={"name": "x", "survey_id": sid, "target": 5, "quotas": [{"attr": "gender", "value": "f", "target": 0}]}, headers=h)).status_code == 422
    v = make_user(); org2 = await v.create_org(); h2 = v.headers(org2)
    assert (await client.get(f"/v1/panel/projects/{proj}", headers=h2)).status_code == 404
    assert (await client.post(f"/v1/panel/projects/{proj}/batches", json={"size": 3}, headers=h2)).status_code == 404
    assert (await client.get("/v1/panel/incentives", headers=h2)).json()["items"] == []
    assert (await client.get("/v1/panel/overview", headers=h2)).json()["verified"] == 0
    emp = make_user(); await invite_member(client, a, org, emp, role="employee")
    assert (await client.get("/v1/panel/overview", headers=emp.headers(org))).status_code == 403
