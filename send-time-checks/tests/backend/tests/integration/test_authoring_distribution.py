"""Group C additions: builder palette, discard, simulator trace, public runner states, distribution overview, interview participant resume."""
import uuid

import pytest

from app.db import tenant_tx
from tests.integration.test_distribution_flow import CSV, MAP, invite_member, make_invitation, propose, setup
from tests.integration.test_interviews import begin, live, say
from tests.integration.test_studio import mk, survey_with

DEF = {"title": {"default": "Pulse", "ar": "نبض"}, "pages": [
    {"elements": [{"type": "rating", "name": "q1", "title": {"default": "Recommend?", "ar": "هل توصي؟"}, "rateMin": 0, "rateMax": 10, "isRequired": True}]},
    {"elements": [{"type": "text", "name": "q2", "title": "Why?"}]}],
    "x-app": {"rules": [{"if": {"q": "q1", "op": "<=", "value": 6}, "then": {"action": "show", "target": "q2"}}]}}


# ---------- palette ----------
async def test_question_types_endpoint_matches_registry(make_user, client):
    u, org, h = await mk(make_user, client)
    r = (await client.get("/v1/question-types", headers=h)).json()
    from app.core.survey_schema import REGISTRY
    assert r["types"] == len(REGISTRY) and r["unlisted"] == []
    assert {t["type"] for g in r["groups"] for t in g["types"]} == set(REGISTRY)
    assert (await client.get("/v1/question-types")).status_code in (401, 403)


@pytest.mark.security
async def test_question_types_requires_membership(make_user, client):
    u = make_user()
    assert (await client.get("/v1/question-types", headers=u.headers())).status_code in (400, 401, 403)          # signed in but no organisation


# ---------- version detail + simulator trace ----------
async def test_version_detail_tells_the_builder_whether_publishing_needs_approval(make_user, client, app):
    u, org, h = await mk(make_user, client)
    sid, _ = await survey_with(client, h, DEF, publish=False)
    assert (await client.get(f"/v1/surveys/{sid}/versions/1", headers=h)).json()["publish_requires_approval"] is False
    app.state.container.require_approval_for_publish = True
    try:
        assert (await client.get(f"/v1/surveys/{sid}/versions/1", headers=h)).json()["publish_requires_approval"] is True
        r = await client.post(f"/v1/surveys/{sid}/versions/1/publish", headers=h)
        assert r.status_code == 409 and "approval" in r.text
        p = await client.post("/v1/approvals", json={"action_type": "publish_survey_version", "payload": {"survey_id": sid, "version": 1}, "idempotency_key": f"pub-{sid}"}, headers=h)
        assert p.status_code == 201 and p.json()["status"] == "pending"
    finally:
        app.state.container.require_approval_for_publish = False


async def test_simulate_returns_why_trace_and_rule_status(make_user, client):
    u, org, h = await mk(make_user, client)
    sid, _ = await survey_with(client, h, DEF, publish=False)
    hi = (await client.post(f"/v1/surveys/{sid}/versions/1/simulate", json={"answers": {"q1": 9}}, headers=h)).json()
    assert hi["questions_shown"] == ["q1"] and hi["rules"] == [{"rule": 1, "holds": False}]
    tr = next(t for t in hi["trace"] if t["target"] == "q2")
    assert tr["shown"] is False and tr["conditions"][0]["actual"] == 9 and tr["conditions"][0]["ok"] is False
    lo = (await client.post(f"/v1/surveys/{sid}/versions/1/simulate", json={"answers": {"q1": 2}}, headers=h)).json()
    assert lo["questions_shown"] == ["q1", "q2"] and lo["path"] == [0, 1]


@pytest.mark.security
async def test_simulate_and_versions_are_tenant_isolated(make_user, client):
    u, org, h = await mk(make_user, client)
    sid, _ = await survey_with(client, h, DEF, publish=False)
    v, org2, h2 = await mk(make_user, client)
    assert (await client.post(f"/v1/surveys/{sid}/versions/1/simulate", json={"answers": {}}, headers=h2)).status_code == 404
    assert (await client.get(f"/v1/surveys/{sid}/versions/1", headers=h2)).status_code == 404
    assert (await client.get(f"/v1/surveys/{sid}/collectors", headers=h2)).status_code == 404
    assert (await client.get(f"/v1/surveys/{sid}/channels", headers=h2)).status_code == 404


# ---------- discard ----------
async def test_discard_unpublished_draft_hides_it_and_is_idempotent(make_user, client):
    u, org, h = await mk(make_user, client)
    sid, _ = await survey_with(client, h, DEF, publish=False)
    assert any(s["id"] == sid for s in (await client.get("/v1/surveys", headers=h)).json()["items"])
    for _ in range(2):
        assert (await client.post(f"/v1/surveys/{sid}/discard", headers=h)).json() == {"discarded": True}
    assert not any(s["id"] == sid for s in (await client.get("/v1/surveys", headers=h)).json()["items"])
    assert (await client.post(f"/v1/surveys/{uuid.uuid4()}/discard", headers=h)).status_code == 404


async def test_published_or_answered_surveys_cannot_be_discarded(make_user, client):
    u, org, h = await mk(make_user, client)
    sid, tok = await survey_with(client, h, DEF)
    r = await client.post(f"/v1/surveys/{sid}/discard", headers=h)
    assert r.status_code == 409 and "close" in r.text


@pytest.mark.security
async def test_discard_needs_edit_rights_and_own_tenant(make_user, client):
    a, org, h = await mk(make_user, client)
    sid, _ = await survey_with(client, h, DEF, publish=False)
    viewer = make_user()
    await invite_member(client, a, org, viewer, role="viewer")
    assert (await client.post(f"/v1/surveys/{sid}/discard", headers=viewer.headers(org))).status_code == 403
    b, org2, h2 = await mk(make_user, client)
    assert (await client.post(f"/v1/surveys/{sid}/discard", headers=h2)).status_code == 404
    assert any(s["id"] == sid for s in (await client.get("/v1/surveys", headers=h)).json()["items"])


# ---------- public runner states ----------
async def test_public_survey_maps_closed_and_limit_to_410_codes(make_user, client):
    u, org, h = await mk(make_user, client)
    sid, tok = await survey_with(client, h, {"pages": [{"elements": [{"type": "text", "name": "a"}]}]})
    ok = await client.get(f"/public/v1/c/{tok}/survey")
    assert ok.status_code == 200 and ok.json()["settings"] == {"require_consent": False, "one_response_per_device": False}
    await client.put(f"/v1/surveys/{sid}/settings", json={"response_limit": 1}, headers=h)
    assert (await client.post(f"/public/v1/c/{tok}/responses", json={"id": str(uuid.uuid4()), "answers": [{"q": "a", "value": "x"}]})).status_code == 200
    lim = await client.get(f"/public/v1/c/{tok}/survey")
    assert lim.status_code == 410 and lim.json()["detail"] == {"code": "limit"}
    await client.put(f"/v1/surveys/{sid}/settings", json={}, headers=h)
    assert (await client.get(f"/public/v1/c/{tok}/survey")).status_code == 200
    await client.post(f"/v1/surveys/{sid}/close", headers=h)
    closed = await client.get(f"/public/v1/c/{tok}/survey")
    assert closed.status_code == 410 and closed.json()["detail"] == {"code": "closed"}
    # a retry of an already-stored response still succeeds after closing (offline-safe submit)
    rid = str(uuid.uuid4())
    sid2, tok2 = await survey_with(client, h, {"pages": [{"elements": [{"type": "text", "name": "a"}]}]})
    body = {"id": rid, "answers": [{"q": "a", "value": "x"}]}
    assert (await client.post(f"/public/v1/c/{tok2}/responses", json=body)).json()["status"] == "created"
    await client.post(f"/v1/surveys/{sid2}/close", headers=h)
    assert (await client.post(f"/public/v1/c/{tok2}/responses", json=body)).json()["status"] == "duplicate"
    assert (await client.post(f"/public/v1/c/{tok2}/responses", json={"id": str(uuid.uuid4()), "answers": []})).status_code == 410


async def test_consent_notice_is_served_for_collector_and_invitation_links(make_user, client):
    a, b, org, h, sid, lid = await setup(make_user, client)
    assert (await client.put(f"/v1/surveys/{sid}/settings", json={"require_consent": True}, headers=h)).status_code == 200
    await client.post("/v1/consent-notices", json={"texts": {"en": "We store your answers.", "ar": "نخزن إجاباتك."}}, headers=h)
    tok = (await client.post(f"/v1/surveys/{sid}/collectors", json={}, headers=h)).json()["token"]
    th = (await client.get(f"/public/v1/c/{tok}/theme")).json()
    assert th["consent"]["version"] == 1 and th["consent"]["texts"]["ar"] == "نخزن إجاباتك."
    r = await client.post(f"/public/v1/c/{tok}/responses", json={"id": str(uuid.uuid4()), "answers": [{"q": "nps", "value": 8}]})
    assert r.status_code == 422 and r.json()["detail"] == {"code": "consent_required", "version": 1}
    ok = await client.post(f"/public/v1/c/{tok}/responses", json={"id": str(uuid.uuid4()), "answers": [{"q": "nps", "value": 8}], "consent_version": 1})
    assert ok.status_code == 200
    # unique invitation link: theme endpoint exists and 404s for unknown tokens
    assert (await client.get("/public/v1/i/unknown-token-xyz/theme")).status_code == 404


# ---------- distribution overview ----------
async def test_channels_collectors_and_invitation_list_for_the_distribute_screen(make_user, client, app):
    app.state.container.notifier.sent.clear()
    a, b, org, h, sid, lid = await setup(make_user, client)
    ch = {c["key"]: c for c in (await client.get(f"/v1/surveys/{sid}/channels", headers=h)).json()["channels"]}
    assert ch["link"] == {"key": "link", "state": "active", "count": 1} and ch["qr"]["state"] == "active" and ch["email"]["state"] == "ready" and ch["email"]["count"] == 0
    cols = (await client.get(f"/v1/surveys/{sid}/collectors", headers=h)).json()
    assert len(cols) == 1 and cols[0]["status"] == "active" and cols[0]["responses"] == 0 and "token" not in cols[0] and "token_hash" not in str(cols[0])
    iid, pre = await make_invitation(client, h, sid, lid)
    assert pre["audience"]["will_receive"] == 5
    inv = (await client.get(f"/v1/invitations?survey_id={sid}", headers=h)).json()
    assert [(i["id"], i["status"], i["channels"], i["approval_status"]) for i in inv] == [(iid, "draft", ["email"], None)]
    p = await propose(client, h, iid)
    assert p.status_code == 201
    inv = (await client.get(f"/v1/invitations?survey_id={sid}", headers=h)).json()
    assert inv[0]["status"] == "pending_approval" and inv[0]["approval_status"] == "pending"
    ch = {c["key"]: c for c in (await client.get(f"/v1/surveys/{sid}/channels", headers=h)).json()["channels"]}
    assert ch["email"]["state"] == "active"
    await client.post(f"/v1/collectors/{cols[0]['id']}/revoke", headers=h)
    assert (await client.get(f"/v1/surveys/{sid}/collectors", headers=h)).json()[0]["status"] == "revoked"
    assert {c["key"]: c["state"] for c in (await client.get(f"/v1/surveys/{sid}/channels", headers=h)).json()["channels"]}["link"] == "not_set_up"


async def test_disabled_processor_marks_the_channel_disabled(make_user, client):
    u, org, h = await mk(make_user, client)
    sid, _ = await survey_with(client, h, DEF)
    assert (await client.put("/v1/privacy/processors/whatsapp", json={"enabled": False}, headers=h)).status_code == 200
    ch = {c["key"]: c["state"] for c in (await client.get(f"/v1/surveys/{sid}/channels", headers=h)).json()["channels"]}
    assert ch["whatsapp"] == "disabled" and ch["email"] == "ready"


@pytest.mark.security
async def test_invitation_list_is_tenant_isolated(make_user, client):
    a, b, org, h, sid, lid = await setup(make_user, client)
    await make_invitation(client, h, sid, lid)
    c, org2, h2 = await mk(make_user, client)
    assert (await client.get(f"/v1/invitations?survey_id={sid}", headers=h2)).json() == []
    assert (await client.get("/v1/invitations", headers=h)).status_code == 422


async def test_contacts_report_last_invited_and_arabic_names_survive_import(make_user, client, app):
    a, b, org, h, sid, lid = await setup(make_user, client)
    csv = "name,email,lang\nعمر الصديقي,user@example.com,ur\n"
    r = await client.post(f"/v1/contact-lists/{lid}/import", json={"csv": csv, "mapping": {"name": "name", "email": "email", "lang": "language"}, "dry_run": False}, headers=h)
    assert r.json()["created"] == 1
    rows = (await client.get(f"/v1/contacts?list_id={lid}&q=omar2", headers=h)).json()["rows"]
    assert rows[0]["name"] == "عمر الصديقي" and rows[0]["last_invited"] is None
    async with tenant_tx(app.state.pool, None, org) as c:
        iid = uuid.uuid4()
        await c.execute("insert into invitations(org_id,id,survey_id,channels,list_ids,body) values($1,$2,$3,'{email}',$4,'{}')", uuid.UUID(org), iid, uuid.UUID(sid), [uuid.UUID(lid)])
        await c.execute("insert into deliveries(org_id,id,invitation_id,contact_id,channel,status,sent_at) values($1,$2,$3,$4,'email','sent',now())", uuid.UUID(org), uuid.uuid4(), iid, uuid.UUID(rows[0]["id"]))
    assert (await client.get(f"/v1/contacts?list_id={lid}&q=omar2", headers=h)).json()["rows"][0]["last_invited"] is not None
    assert CSV and MAP


# ---------- interview participant resume ----------
async def test_participant_can_resume_and_sees_only_their_session(make_user, client):
    u, org, h, sid, link = await live(make_user, client)
    info = (await client.get(f"/public/v1/interview/{link}")).json()
    assert info["languages"] == ["en", "ar"] and info["consent_version"] == 1 and info["name"] == "Resident decision interviews"
    assert info["consent"]["ar"].startswith("أنت تتحدث") and info["consent"]["en"].startswith("You are speaking")      # the notice is readable before a session exists
    start = (await client.post(f"/public/v1/interview/{link}/sessions", json={"language": "ar"})).json()
    tok = start["session_token"]
    s = (await client.get(f"/public/v1/interview/session/{tok}")).json()
    assert s["state"] == "consent" and s["turns"] == [] and s["consent_text"].startswith("أنت تتحدث") and s["topic"] == 1 and s["topics"] == 2
    tok2, first = await begin(client, link)
    await say(client, tok2, "I chose it because the commute to DIFC is short.")
    s = (await client.get(f"/public/v1/interview/session/{tok2}")).json()
    assert s["state"] == "active" and [t["role"] for t in s["turns"]] == ["interviewer", "participant", "interviewer"] and s["topic"] == 2 and s["consent_text"] is None
    assert (await client.get(f"/public/v1/interview/session/{tok2}x")).status_code == 404


@pytest.mark.security
async def test_interview_resume_hides_deleted_transcripts_and_requires_a_live_link(make_user, client):
    u, org, h, sid, link = await live(make_user, client)
    tok, _ = await begin(client, link)
    await say(client, tok, "price")
    w = await client.post(f"/public/v1/interview/session/{tok}/withdraw", json={"delete_transcript": True})
    assert w.json()["transcript_deleted"] is True
    s = (await client.get(f"/public/v1/interview/session/{tok}")).json()
    assert s["state"] == "withdrawn" and s["turns"] == []
    assert (await client.get("/public/v1/interview/not-a-real-link-token-1234")).status_code == 404
    assert (await client.get("/public/v1/interview/short")).status_code == 404


async def test_consent_version_bump_forces_reconsent_on_resume(make_user, client):
    u, org, h, sid, link = await live(make_user, client)
    tok, _ = await begin(client, link)
    assert (await client.put(f"/v1/interviews/{sid}/consent", json={"consent": {"en": "Updated notice: your answers are stored and analysed.", "ar": "إشعار محدّث: يتم تخزين إجاباتك وتحليلها للبحث."}}, headers=h)).json()["consent_version"] == 2
    s = (await client.get(f"/public/v1/interview/session/{tok}")).json()
    assert s["state"] == "consent" and s["consent_version"] == 2 and s["consent_text"].startswith("Updated notice")
    r = await client.post(f"/public/v1/interview/session/{tok}/turn", json={"text": "hello"})
    assert r.json()["state"] == "consent"
    assert (await client.post(f"/public/v1/interview/session/{tok}/consent", json={"version": 1, "accept": True})).status_code == 409
    assert (await client.post(f"/public/v1/interview/session/{tok}/consent", json={"version": 2, "accept": True})).status_code == 200


# ---------- AI draft: "start from" a template ----------
async def test_ai_draft_can_start_from_a_template_and_unknown_templates_are_404(make_user, client, app):
    from app.seeds.templates import definition
    u, org, h = await mk(make_user, client)
    llm = app.state.container.llm
    seen: list[str] = []

    async def spy(brief, language, goal):
        seen.append(brief)
        return {"pages": [{"elements": [{"type": "text", "name": "a", "title": {"default": "A short question"}}]}]}
    llm.draft_survey = spy
    try:
        body = {"brief": "Quarterly satisfaction survey for residents of a community in Abu Dhabi.", "languages": ["en", "ar"]}
        first_title = definition("nps_core")["pages"][0]["elements"][0]["title"]["default"]
        r = await client.post("/v1/surveys/draft", json={**body, "template_key": "nps_core"}, headers=h)
        assert r.status_code == 201, r.text
        assert "template 'nps_core'" in seen[0] and first_title in seen[0]
        assert r.json()["provenance"]["inputs_hash"] != (await client.post("/v1/surveys/draft", json=body, headers=h)).json()["provenance"]["inputs_hash"]
        calls = len(seen)
        assert (await client.post("/v1/surveys/draft", json={**body, "template_key": "no_such_template"}, headers=h)).status_code == 404
        assert len(seen) == calls                                                             # the model is never called for an unknown template
    finally:
        del llm.draft_survey


async def test_consent_summary_exposes_every_sending_rule_so_the_screen_can_edit_them_without_clobbering(make_user, client):
    u, org, h = await mk(make_user, client)
    d = (await client.get("/v1/consent-summary", headers=h)).json()
    assert (d["quiet_start"], d["quiet_end"], d["cooldown_days"], d["min_group_size"], d["quota"]["limit"]) == ("21:00", "08:00", 30, 5, 5000)
    r = await client.put("/v1/org-settings", json={"quiet_start": "22:30:00", "quiet_end": "07:00:00", "tz": "Asia/Dubai", "daily_quota": 1200, "min_group_size": 8, "contact_cooldown_days": 10}, headers=h)
    assert r.status_code == 200
    d = (await client.get("/v1/consent-summary", headers=h)).json()
    assert (d["quiet_hours"], d["cooldown_days"], d["min_group_size"], d["quota"]["limit"]) == ("22:30-07:00", 10, 8, 1200)
    other = make_user(); org2 = await other.create_org()
    assert (await client.get("/v1/consent-summary", headers=other.headers(org2))).json()["quota"]["limit"] == 5000          # not the other tenant's
