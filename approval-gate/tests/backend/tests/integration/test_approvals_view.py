import uuid

import pytest

from app.app.worker import run_pending
from tests.integration.test_distribution_flow import invite_member, make_invitation, propose, setup

QUIET = {"quiet_start": "00:00:00", "quiet_end": "00:00:01", "tz": "Asia/Dubai", "daily_quota": 100}


async def test_list_and_detail_carry_display_facts(make_user, client, app):
    a, b, org, h, sid, lid = await setup(make_user, client, quiet=QUIET)
    iid, inv = await make_invitation(client, h, sid, lid, channels=("email",))
    aid = (await propose(client, h, iid)).json()["id"]
    d = (await client.get("/v1/approvals?status=pending", headers=h)).json()
    it = d["items"][0]
    assert it["title"] == "Send invitations" and it["subtitle"] == "S · email" and it["recipients"] == 5 and it["risk"] == "high"
    assert it["proposed_by_email"] == a.email and it["decided_by_email"] is None and it["preview"]["exclusions"]["no_consent"] == 0
    assert "consent" in it["preview"]["checks"] and d["can_decide"] is True and d["receipts"] == []
    det = (await client.get(f"/v1/approvals/{aid}", headers=h)).json()
    assert det["title"] == "Send invitations" and det["preview"]["body"]["ar"].startswith("مرحباً")
    assert (await client.post(f"/v1/approvals/{aid}/decide", json={"approve": True}, headers=b.headers(org))).status_code == 200
    await run_pending(app.state.pool, app.state.container)
    d = (await client.get("/v1/approvals?status=executed", headers=h)).json()
    assert d["items"][0]["decided_by_email"] == b.email and d["items"][0]["executed_at"] and d["items"][0]["confirmation"].startswith("5 sent")
    assert d["receipts"][0]["id"] == aid and d["receipts"][0]["decided_by_email"] == b.email


async def test_rejection_keeps_comment_and_returns_invitation_to_draft(make_user, client):
    a, b, org, h, sid, lid = await setup(make_user, client, quiet=QUIET)
    iid, _ = await make_invitation(client, h, sid, lid)
    aid = (await propose(client, h, iid)).json()["id"]
    r = await client.post(f"/v1/approvals/{aid}/decide", json={"approve": False, "comment": "Wrong audience: عملاء"}, headers=b.headers(org))
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    it = (await client.get("/v1/approvals?status=rejected", headers=h)).json()["items"][0]
    assert it["decision_comment"] == "Wrong audience: عملاء" and it["decided_by_email"] == b.email and it["decided_at"]
    assert (await propose(client, h, iid)).status_code == 201                                      # can be proposed again after changes


async def test_publish_subtitle_names_survey_and_version(make_user, client):
    a, b, org, h, sid, lid = await setup(make_user, client)
    await client.put(f"/v1/surveys/{sid}/versions/2", json={"definition": {"pages": [{"elements": [{"type": "rating", "name": "q1", "rateMin": 1, "rateMax": 5}]}]}}, headers=h)
    r = await client.post("/v1/approvals", json={"action_type": "publish_survey_version", "payload": {"survey_id": sid, "version": 2}, "idempotency_key": "pub-" + uuid.uuid4().hex}, headers=h)
    assert r.status_code == 201, r.text
    it = (await client.get("/v1/approvals", headers=h)).json()["items"][0]
    assert it["title"] == "Publish survey version" and it["subtitle"] == "S v2" and it["recipients"] is None and it["risk"] == "low"


@pytest.mark.security
async def test_approvals_isolated_and_hidden_from_employees(make_user, client):
    a, b, org, h, sid, lid = await setup(make_user, client, quiet=QUIET)
    iid, _ = await make_invitation(client, h, sid, lid)
    aid = (await propose(client, h, iid)).json()["id"]
    e = make_user()
    await invite_member(client, a, org, e, role="employee")
    assert (await client.get("/v1/approvals", headers=e.headers(org))).status_code == 403
    assert (await client.get(f"/v1/approvals/{aid}", headers=e.headers(org))).status_code == 403
    v = make_user()
    await invite_member(client, a, org, v, role="viewer")
    assert (await client.get("/v1/approvals", headers=v.headers(org))).json()["can_decide"] is False
    assert (await client.post(f"/v1/approvals/{aid}/decide", json={"approve": True}, headers=v.headers(org))).status_code == 403
    other = make_user(); o2 = await other.create_org()
    assert (await client.get(f"/v1/approvals/{aid}", headers=other.headers(o2))).status_code == 404
    assert (await client.get("/v1/approvals?status=all", headers=other.headers(o2))).json()["items"] == []
    assert (await client.post(f"/v1/approvals/{aid}/decide", json={"approve": True}, headers=other.headers(o2))).status_code == 404
