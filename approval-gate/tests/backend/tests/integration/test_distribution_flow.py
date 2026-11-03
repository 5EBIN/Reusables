import time
import json
import uuid
from datetime import datetime, UTC

import pytest

from app.app.run_approved import release_deferred, run_approved
from app.app.worker import run_pending
from app.core.approvals import NotApprovedError
from app.db import tenant_tx

DEF = {"pages": [{"elements": [{"type": "rating", "name": "nps", "rateMin": 0, "rateMax": 10, "isRequired": True}]}]}
CSV = "name,email,phone,lang\nJordan Lee,user@example.com,0501110001,ar\nOmar,user@example.com,0501110002,ur\nIrina,user@example.com,,ru\nJoseph,user@example.com,0501110004,fil\nSara,user@example.com,0501110005,en\n"
MAP = {"name": "name", "email": "email", "phone": "phone", "lang": "language"}


async def invite_member(client, admin, org, user, role="client_admin"):
    tok = (await client.post("/v1/members/invite", json={"email": user.email, "role": role}, headers=admin.headers(org))).json()["token"]
    r = await client.post("/v1/invitations/accept", json={"token": tok}, headers=user.headers())
    assert r.status_code == 200, r.text


async def setup(make_user, client, quiet=None):
    client._transport.app.state.container.notifier.sent.clear()
    a, b = make_user(), make_user()
    org = await a.create_org()
    await invite_member(client, a, org, b)
    h = a.headers(org)
    if quiet is not None:
        r = await client.put("/v1/org-settings", json=quiet, headers=h)
        assert r.status_code == 200
    sid = str(uuid.uuid4())
    await client.post("/v1/surveys", json={"id": sid, "title": {"default": "S"}}, headers=h)
    await client.put(f"/v1/surveys/{sid}/versions/1", json={"definition": DEF}, headers=h)
    await client.post(f"/v1/surveys/{sid}/versions/1/publish", headers=h)
    await client.post(f"/v1/surveys/{sid}/collectors", json={}, headers=h)
    lid = str(uuid.uuid4())
    await client.post("/v1/contact-lists", json={"id": lid, "name": "Residents"}, headers=h)
    r = await client.post(f"/v1/contact-lists/{lid}/import", json={"csv": CSV, "mapping": MAP, "dry_run": False, "consent_channel": "email"}, headers=h)
    assert r.json()["created"] == 5, r.text
    return a, b, org, h, sid, lid


async def make_invitation(client, h, sid, lid, channels=("email",)):
    iid = str(uuid.uuid4())
    r = await client.post("/v1/invitations", json={"id": iid, "survey_id": sid, "channels": list(channels), "list_ids": [lid],
                                                   "body": {"en": "Hello {first_name}, {link}", "ar": "مرحباً {first_name} {link}"}}, headers=h)
    assert r.status_code == 201, r.text
    return iid, r.json()


async def propose(client, h, iid, key=None):
    return await client.post("/v1/approvals", json={"action_type": "send_survey_invites", "payload": {"invitation_id": iid},
                                                    "idempotency_key": key or f"k-{uuid.uuid4()}"}, headers=h)


async def test_import_report_and_dry_run(make_user, client):
    u = make_user(); org = await u.create_org(); h = u.headers(org)
    lid = str(uuid.uuid4())
    await client.post("/v1/contact-lists", json={"id": lid, "name": "L"}, headers=h)
    dry = (await client.post(f"/v1/contact-lists/{lid}/import", json={"csv": CSV, "mapping": MAP}, headers=h)).json()
    assert dry["dry_run"] and dry["rows"] == 5 and dry["sample"][0]["phone"].startswith("+971 50 •••")
    assert (await client.get("/v1/contacts", headers=h)).json()["total"] == 0                       # nothing written on dry run
    for _ in range(2):                                                                              # replay-safe import
        r = (await client.post(f"/v1/contact-lists/{lid}/import", json={"csv": CSV, "mapping": MAP, "dry_run": False}, headers=h)).json()
    assert r["updated"] == 5 and r["created"] == 0
    assert (await client.get(f"/v1/contacts?list_id={lid}", headers=h)).json()["total"] == 5
    assert (await client.post(f"/v1/contact-lists/{lid}/import", json={"csv": CSV, "mapping": {"nope": "email"}}, headers=h)).status_code == 422


async def test_contact_pii_masked_and_isolated(make_user, client):
    a, b, org, h, sid, lid = await setup(make_user, client)
    rows = (await client.get("/v1/contacts?q=omar", headers=h)).json()["rows"]
    assert rows[0]["name"] == "Omar" and "•••" in rows[0]["phone"] and "0501110002" not in json.dumps(rows)
    other = make_user(); o2 = await other.create_org()
    assert (await client.get("/v1/contacts", headers=other.headers(o2))).json()["total"] == 0


async def test_audience_exclusions_then_full_send_flow(make_user, client, app):
    a, b, org, h, sid, lid = await setup(make_user, client, quiet={"quiet_start": "00:00:00", "quiet_end": "00:00:01", "tz": "Asia/Dubai", "daily_quota": 100})
    contacts = (await client.get(f"/v1/contacts?list_id={lid}", headers=h)).json()["rows"]
    by = {c["name"]: c["id"] for c in contacts}
    await client.put(f"/v1/contacts/{by['Joseph']}/consent", json={"channel": "email", "status": "opt_out", "source": "reply STOP"}, headers=h)
    await client.post("/v1/suppressions", json={"channel": "email", "address": "user@example.com", "reason": "hard_bounce"}, headers=h)
    iid, inv = await make_invitation(client, h, sid, lid)
    aud = inv["audience"]
    assert aud["selected"] == 5 and aud["will_receive"] == 3 and aud["exclusions"] == {"no_consent": 1, "suppressed": 1, "recently_contacted": 0}
    r = await propose(client, h, iid, "same-key-1")
    assert r.status_code == 201 and r.json()["risk"] == "high" and r.json()["status"] == "pending"
    again = await propose(client, h, iid, "same-key-1")                                              # replay returns the same approval
    assert again.json()["id"] == r.json()["id"]
    aid = r.json()["id"]
    assert (await client.post(f"/v1/approvals/{aid}/decide", json={"approve": True}, headers=h)).status_code == 403   # two-person rule (same user)
    assert (await client.get("/v1/approvals?status=pending", headers=h)).json()["counts"]["pending"] == 1
    d = await client.post(f"/v1/approvals/{aid}/decide", json={"approve": True, "comment": "ok"}, headers=b.headers(org))
    assert d.status_code == 200 and d.json()["job_id"]
    assert (await client.post(f"/v1/approvals/{aid}/decide", json={"approve": True}, headers=b.headers(org))).status_code == 409  # already decided
    n = app.state.container.notifier
    assert n.sent == []                                                                              # nothing sent before the worker runs
    stats = await run_pending(app.state.pool, app.state.container)
    assert stats["done"] >= 1 and len(n.sent) == 3
    assert {m.to for m in n.sent} == {"user@example.com", "user@example.com", "user@example.com"}
    assert all("/i/" in m.vars["text"] for m in n.sent) and any("مرحباً" in m.vars["text"] for m in n.sent)   # per-language body
    det = (await client.get(f"/v1/approvals/{aid}", headers=h)).json()
    assert det["status"] == "executed" and det["receipt"]["sent"] == 3 and det["confirmation"].startswith("3 sent")
    assert [e["event"] for e in det["events"]] == ["proposed", "approved", "executed"]
    await run_pending(app.state.pool, app.state.container)                                           # replay: no double send
    assert len(n.sent) == 3
    f = (await client.get(f"/v1/invitations/{iid}/funnel", headers=h)).json()
    assert {x["status"]: x["n"] for x in f}["sent"] == 3


async def test_unique_link_is_single_use(make_user, client, app):
    a, b, org, h, sid, lid = await setup(make_user, client, quiet={"quiet_start": "00:00:00", "quiet_end": "00:00:01", "tz": "Asia/Dubai", "daily_quota": 100})
    iid, _ = await make_invitation(client, h, sid, lid)
    aid = (await propose(client, h, iid)).json()["id"]
    await client.post(f"/v1/approvals/{aid}/decide", json={"approve": True}, headers=b.headers(org))
    await run_pending(app.state.pool, app.state.container)
    msg = next(m for m in app.state.container.notifier.sent if m.to == "user@example.com")
    tok = msg.vars["text"].split("/i/")[1].split()[0]
    assert (await client.get(f"/public/v1/i/{tok}/survey")).status_code == 200
    rid = str(uuid.uuid4())
    ok = await client.post(f"/public/v1/i/{tok}/responses", json={"id": rid, "answers": [{"q": "nps", "value": 9}]})
    assert ok.json()["status"] == "created"
    assert (await client.post(f"/public/v1/i/{tok}/responses", json={"id": rid, "answers": [{"q": "nps", "value": 9}]})).json()["status"] == "duplicate"   # replay
    assert (await client.post(f"/public/v1/i/{tok}/responses", json={"id": str(uuid.uuid4()), "answers": [{"q": "nps", "value": 3}]})).status_code == 404   # consumed
    assert (await client.get(f"/public/v1/i/{tok}/survey")).status_code == 404
    assert (await client.get("/public/v1/i/unknown-token-xyz/survey")).status_code == 404
    st = await client.get(f"/v1/invitations/{iid}/funnel", headers=h)
    assert sum(x["completed"] for x in st.json()) == 1


async def test_quiet_hours_defer_not_drop_and_release(make_user, client, app):
    a, b, org, h, sid, lid = await setup(make_user, client)          # default 21:00-08:00 Dubai
    iid, _ = await make_invitation(client, h, sid, lid)
    aid = (await propose(client, h, iid)).json()["id"]
    await client.post(f"/v1/approvals/{aid}/decide", json={"approve": True}, headers=b.headers(org))
    night = datetime(2026, 10, 7, 18, 30, tzinfo=UTC)       # 22:30 Dubai
    async with tenant_tx(app.state.pool, None, org) as c:
        rec = await run_approved(c, uuid.UUID(aid), app.state.container.notifier, now=night)
    assert rec["sent"] == 0 and rec["deferred"] == 5 and rec["next_release"].startswith("2026-10-08T04:00")      # 08:00 Dubai
    assert app.state.container.notifier.sent == []
    morning = datetime(2026, 10, 8, 5, 0, tzinfo=UTC)       # 09:00 Dubai
    async with tenant_tx(app.state.pool, None, org) as c:
        rec2 = await release_deferred(c, uuid.UUID(aid), app.state.container.notifier, "http://x", now=morning)
        rec3 = await release_deferred(c, uuid.UUID(aid), app.state.container.notifier, "http://x", now=morning)   # replay
    assert rec2["sent"] == 5 and rec2["deferred"] == 0 and rec3["sent"] == 5 and len(app.state.container.notifier.sent) == 5


async def test_quota_enforced_at_send_time(make_user, client, app):
    a, b, org, h, sid, lid = await setup(make_user, client, quiet={"quiet_start": "00:00:00", "quiet_end": "00:00:01", "tz": "Asia/Dubai", "daily_quota": 2})
    await client.post(f"/v1/contact-lists/{lid}/import", json={"csv": CSV, "mapping": MAP, "dry_run": False, "consent_channel": "whatsapp"}, headers=h)
    iid, _ = await make_invitation(client, h, sid, lid, channels=("whatsapp",))
    aid = (await propose(client, h, iid)).json()["id"]
    await client.post(f"/v1/approvals/{aid}/decide", json={"approve": True}, headers=b.headers(org))
    await run_pending(app.state.pool, app.state.container)
    rec = (await client.get(f"/v1/approvals/{aid}", headers=h)).json()["receipt"]
    assert rec["sent"] == 2 and rec["skipped"] >= 2


@pytest.mark.security
async def test_approval_bypass_enumeration(make_user, client, app):
    """No route may execute side effects; run_approved raises unless status == approved; roles gate approvals."""
    a, b, org, h, sid, lid = await setup(make_user, client)
    iid, _ = await make_invitation(client, h, sid, lid)
    aid = (await propose(client, h, iid)).json()["id"]
    async with tenant_tx(app.state.pool, None, org) as c:
        with pytest.raises(NotApprovedError):
            await run_approved(c, uuid.UUID(aid), app.state.container.notifier)                       # pending
    await client.post(f"/v1/approvals/{aid}/decide", json={"approve": False, "comment": "no"}, headers=b.headers(org))
    async with tenant_tx(app.state.pool, None, org) as c:
        with pytest.raises(NotApprovedError):
            await run_approved(c, uuid.UUID(aid), app.state.container.notifier)                       # rejected
    assert app.state.container.notifier.sent == []
    assert (await client.get(f"/v1/invitations/{iid}/audience", headers=h)).status_code == 200      # draft again after rejection
    routes = {(m, r.path) for r in app.routes if hasattr(r, "methods") for m in r.methods if m in ("POST", "PUT", "DELETE")}
    sending = [p for m, p in routes if "send" in p or "execute" in p or "run" in p]
    assert sending == []                                                                              # no direct send/execute/run endpoint exists


@pytest.mark.security
async def test_analyst_cannot_approve_and_isolation(make_user, client, app):
    a, b, org, h, sid, lid = await setup(make_user, client)
    c3 = make_user()
    await invite_member(client, a, org, c3, role="analyst")
    iid, _ = await make_invitation(client, h, sid, lid)
    aid = (await propose(client, h, iid)).json()["id"]
    assert (await client.post(f"/v1/approvals/{aid}/decide", json={"approve": True}, headers=c3.headers(org))).status_code == 403
    x = make_user(); ox = await x.create_org()
    assert (await client.get(f"/v1/approvals/{aid}", headers=x.headers(ox))).status_code == 404
    assert (await client.post(f"/v1/approvals/{aid}/decide", json={"approve": True}, headers=x.headers(ox))).status_code == 404


@pytest.mark.parametrize("bad", [
    {"action_type": "wire_money", "payload": {}, "idempotency_key": "abcdefgh"}, {"action_type": "send_survey_invites", "payload": {}, "idempotency_key": "short"},
    {"action_type": "send_survey_invites", "payload": {"invitation_id": "nope"}, "idempotency_key": "abcdefgh1"}, {"idempotency_key": "abcdefgh"},
    {"action_type": "publish_survey_version", "payload": {}, "idempotency_key": "abcdefgh2"},
])
async def test_propose_rejections(make_user, client, bad):
    u = make_user(); org = await u.create_org()
    assert (await client.post("/v1/approvals", json=bad, headers=u.headers(org))).status_code in (422, 404)


async def test_empty_audience_cannot_be_proposed(make_user, client):
    a, b, org, h, sid, lid = await setup(make_user, client)
    iid, _ = await make_invitation(client, h, sid, lid, channels=("whatsapp",))       # nobody consented to whatsapp
    assert (await propose(client, h, iid)).status_code == 409


async def test_publish_through_the_gate(make_user, client, app):
    a, b, org, h, sid, lid = await setup(make_user, client)
    await client.put(f"/v1/surveys/{sid}/versions/2", json={"definition": DEF}, headers=h)
    r = await client.post("/v1/approvals", json={"action_type": "publish_survey_version", "payload": {"survey_id": sid, "version": 2}, "idempotency_key": "pub-v2-key"}, headers=h)
    assert r.status_code == 201 and r.json()["risk"] == "low"
    d = await client.post(f"/v1/approvals/{r.json()['id']}/decide", json={"approve": True}, headers=h)    # low risk: self-approve allowed
    assert d.status_code == 200
    await run_pending(app.state.pool, app.state.container)
    v = (await client.get(f"/v1/surveys/{sid}", headers=h)).json()["versions"]
    assert v[1]["published"] is True


async def test_job_retry_backoff_then_dead_letter(make_user, client, app, monkeypatch):
    from app.app import worker
    a, b, org, h, sid, lid = await setup(make_user, client)
    async with tenant_tx(app.state.pool, None, org) as c:
        await worker.Q.enqueue(c, "explode", {})
    async def boom(conn, container, job):
        if job["kind"] == "explode":
            raise RuntimeError("kaboom")
    monkeypatch.setattr(worker, "handle", boom)
    s1 = await run_pending(app.state.pool, app.state.container)
    assert s1["retry"] == 1 and s1["done"] == 0
    assert (await run_pending(app.state.pool, app.state.container))["retry"] == 0                       # backoff: not claimable yet
    async with tenant_tx(app.state.pool, None, org) as c:
        await c.execute("update jobs set run_after = now() - interval '1 second', attempts = max_attempts - 1 where kind='explode'")
    s2 = await run_pending(app.state.pool, app.state.container)
    assert s2["dead"] == 1
    async with tenant_tx(app.state.pool, None, org) as c:
        row = await c.fetchrow("select status, last_error from jobs where kind='explode'")
    assert row["status"] == "dead" and "kaboom" in row["last_error"]


async def test_two_workers_never_double_process(make_user, client, app):
    import asyncio
    a, b, org, h, sid, lid = await setup(make_user, client)
    async with tenant_tx(app.state.pool, None, org) as c:
        for _ in range(10):
            await app_enqueue(c)
    seen = []
    from app.app import worker
    orig = worker.handle
    async def rec(conn, container, job):
        if job["kind"] == "noop":
            seen.append(job["id"])
            return
        await orig(conn, container, job)
    worker.handle = rec
    try:
        r = await asyncio.gather(*[run_pending(app.state.pool, app.state.container, 10) for _ in range(4)])
    finally:
        worker.handle = orig
    assert len(seen) == len(set(seen)) == 10 and sum(x["done"] for x in r) >= 10


async def app_enqueue(c):
    from app.app.worker import Q
    await Q.enqueue(c, "noop", {})


async def test_team_roles_last_admin_and_expiry(make_user, client):
    a, b = make_user(), make_user()
    org = await a.create_org()
    h = a.headers(org)
    assert (await client.put(f"/v1/members/{(await client.get('/v1/me', headers=a.headers())).json()['user_id']}", json={"role": "viewer"}, headers=h)).status_code == 409
    await invite_member(client, a, org, b, role="analyst")
    mem = (await client.get("/v1/members", headers=h)).json()["members"]
    assert {m["email"]: m["role"] for m in mem}[b.email] == "analyst"
    uid = next(m["user_id"] for m in mem if m["email"] == b.email)
    assert (await client.put(f"/v1/members/{uid}", json={"role": "viewer"}, headers=b.headers(org))).status_code == 403          # non-admin
    assert (await client.put(f"/v1/members/{uid}", json={"role": "viewer"}, headers=h)).status_code == 200
    assert (await client.put(f"/v1/members/{uid}", json={"role": "boss"}, headers=h)).status_code == 422
    assert (await client.delete(f"/v1/members/{uid}", headers=h)).status_code == 204
    assert (await client.get("/v1/ctx", headers=b.headers(org, iat=int(time.time()) - 5))).status_code == 401      # in no organisation any more: signed out everywhere (3e)
    # expiring consultant access
    c3 = make_user()
    tok = (await client.post("/v1/members/invite", json={"email": c3.email, "role": "consultant", "access_expires_at": "2000-01-01T00:00:00Z"}, headers=h)).json()["token"]
    await client.post("/v1/invitations/accept", json={"token": tok}, headers=c3.headers())
    assert (await client.get("/v1/ctx", headers=c3.headers(org))).status_code == 403                                               # expired grant
    assert (await client.post("/v1/invitations/accept", json={"token": tok}, headers=c3.headers())).status_code == 404            # single-use
    assert (await client.post("/v1/invitations/accept", json={"token": "x" * 20}, headers=c3.headers())).status_code == 404
    assert (await client.get("/v1/permissions", headers=h)).json()["matrix"]["impersonate"]["super_admin"] is True
