import uuid

import pytest

from app.db import tenant_tx
from tests.integration.test_distribution_flow import invite_member
from tests.integration.test_semantic import NEG, OTHER, POS, seed
from tests.integration.test_semantic_erasure import erase

pytestmark = pytest.mark.asyncio
TEXTS = NEG + POS + OTHER                                  # 8 negative, 8 positive, 1 neither


def base(sid):
    return f"/v1/surveys/{sid}/questions/why/sentiment"


def canned(texts):
    return [{"label": "negative" if t in NEG else "positive" if t in POS else "neutral", "confidence": 0.9} for t in texts]


@pytest.fixture(autouse=True)
def _llm(app):
    llm = app.state.container.llm
    llm.sentiment_results = canned
    yield llm
    llm.sentiment_results = None


async def test_run_then_read_summary(make_user, client):
    u, org, h, sid = await seed(make_user, client, TEXTS)
    r = (await client.post(base(sid) + "/run", json={}, headers=h)).json()
    assert r["labelled"] == len(TEXTS) and r["remaining"] == 0 and r["fallback_batches"] == 0
    s = (await client.get(base(sid), headers=h)).json()
    assert s["answers"] == len(TEXTS) and s["unlabelled"] == 0 and s["fallback_used"] is False
    assert s["overall"]["counts"] == {"positive": 8, "neutral": 1, "negative": 8, "low_confidence": 0}
    assert s["overall"]["net"] == 0.0 and s["by_language"]["en"]["n"] == len(TEXTS)


async def test_second_run_skips_labelled_answers_and_force_relabels(make_user, client, app):
    u, org, h, sid = await seed(make_user, client, TEXTS)
    await client.post(base(sid) + "/run", json={}, headers=h)
    r = (await client.post(base(sid) + "/run", json={}, headers=h)).json()
    assert r["labelled"] == 0 and r["already_labelled"] == len(TEXTS)
    app.state.container.llm.sentiment_results = lambda texts: [{"label": "positive", "confidence": 0.9}] * len(texts)
    r = (await client.post(base(sid) + "/run", json={"force": True}, headers=h)).json()
    assert r["labelled"] == len(TEXTS)
    assert (await client.get(base(sid), headers=h)).json()["overall"]["counts"]["positive"] == len(TEXTS)


@pytest.mark.parametrize("bad", [
    lambda texts: [],                                                                              # wrong count
    lambda texts: [{"label": "joyful", "confidence": 0.9}] * len(texts),                           # unknown label
    lambda texts: (_ for _ in ()).throw(RuntimeError("provider outage")),                          # outage
])
async def test_bad_model_output_falls_back_to_the_word_list(make_user, client, app, bad):
    u, org, h, sid = await seed(make_user, client, ["terrible", "great", "slow", "excellent", "rude", "helpful"])
    app.state.container.llm.sentiment_results = bad
    r = (await client.post(base(sid) + "/run", json={}, headers=h)).json()
    assert r["labelled"] == 6 and r["fallback_batches"] == 1
    s = (await client.get(base(sid), headers=h)).json()
    assert s["fallback_used"] is True and s["models"] == ["lexicon-1"]
    assert s["overall"]["counts"]["negative"] == 3 and s["overall"]["counts"]["positive"] == 3


async def test_small_groups_are_not_broken_down(make_user, client):
    u, org, h, sid = await seed(make_user, client, ["terrible", "great", "awful"])
    await client.post(base(sid) + "/run", json={}, headers=h)
    s = (await client.get(base(sid), headers=h)).json()
    assert s["overall"]["suppressed"] is True and "counts" not in s["overall"] and s["overall"]["n"] == 3


async def test_unlabelled_answers_are_reported(make_user, client):
    u, org, h, sid = await seed(make_user, client, TEXTS)
    s = (await client.get(base(sid), headers=h)).json()
    assert s["answers"] == len(TEXTS) and s["unlabelled"] == len(TEXTS) and s["overall"]["n"] == 0


async def test_run_needs_a_writer_role_and_a_valid_question(make_user, client):
    u, org, h, sid = await seed(make_user, client, TEXTS)
    v = make_user(); await invite_member(client, u, org, v, role="viewer")
    assert (await client.post(base(sid) + "/run", json={}, headers=v.headers(org))).status_code == 403
    assert (await client.get(base(sid), headers=v.headers(org))).status_code == 200            # reading is allowed
    assert (await client.post(f"/v1/surveys/{sid}/questions/1bad/sentiment/run", json={}, headers=h)).status_code == 422
    assert (await client.post(f"/v1/surveys/{sid}/questions/nope/sentiment/run", json={}, headers=h)).status_code == 409     # no text answers


@pytest.mark.security
async def test_another_organisation_cannot_see_the_labels(make_user, client, app):
    u, org, h, sid = await seed(make_user, client, TEXTS)
    await client.post(base(sid) + "/run", json={}, headers=h)
    w = make_user(); org2 = await w.create_org()
    s = (await client.get(base(sid), headers=w.headers(org2))).json()
    assert s["answers"] == 0 and s["overall"]["n"] == 0
    assert (await client.post(base(sid) + "/run", json={}, headers=w.headers(org2))).status_code == 409
    async with tenant_tx(app.state.pool, None, org2) as c:
        assert await c.fetchval("select count(*) from answer_sentiment") == 0
    async with tenant_tx(app.state.pool, None, org) as c:
        assert await c.fetchval("select count(*) from answer_sentiment") == len(TEXTS)
    async with tenant_tx(app.state.pool, None, None) as c:                                      # no tenant context fails closed
        assert await c.fetchval("select count(*) from answer_sentiment") == 0


async def test_respondent_erasure_removes_the_label(make_user, client, app):
    u, org, h, sid = await seed(make_user, client, TEXTS)
    b = make_user(); await invite_member(client, u, org, b); second = b.headers(org)
    await client.post(base(sid) + "/run", json={}, headers=h)
    async with tenant_tx(app.state.pool, None, org) as c:
        rid = await c.fetchval("select response_id from answer_sentiment limit 1")
    await erase(client, h, rid, second)
    async with tenant_tx(app.state.pool, None, org) as c:
        assert await c.fetchval("select count(*) from answer_sentiment where response_id=$1", rid) == 0
        assert await c.fetchval("select count(*) from answer_sentiment") == len(TEXTS) - 1



async def test_a_rejected_answer_is_asked_again_once_with_the_reason(make_user, client, app):
    u, org, h, sid = await seed(make_user, client, TEXTS)
    llm = app.state.container.llm
    calls = []

    def flaky(texts):
        calls.append(len(texts))
        return [] if len(calls) == 1 else canned(texts)                  # first answer has the wrong count, the second is fine

    llm.sentiment_results = flaky
    r = (await client.post(base(sid) + "/run", json={}, headers=h)).json()
    assert r["fallback_batches"] == 0 and r["labelled"] == len(TEXTS) and len(calls) == 2
    hints = [c["hint"] for c in llm.calls if "classify_sentiment" in c][-2:]          # the fake keeps a log across tests: look at this run's two calls
    assert hints[0] is None and "wrong number" in hints[1]
    assert (await client.get(base(sid), headers=h)).json()["fallback_used"] is False


async def test_an_outage_is_not_asked_again(make_user, client, app):
    u, org, h, sid = await seed(make_user, client, TEXTS)
    llm = app.state.container.llm
    n = []

    def down(texts):
        n.append(1)
        raise RuntimeError("provider outage")

    llm.sentiment_results = down
    r = (await client.post(base(sid) + "/run", json={}, headers=h)).json()
    assert r["fallback_batches"] == 1 and len(n) == 1


async def test_run_respects_the_organisations_llm_switch(make_user, client, app):
    u, org, h, sid = await seed(make_user, client, TEXTS)
    llm = app.state.container.llm
    n = len(llm.calls)
    assert (await client.put("/v1/privacy/processors/llm", json={"enabled": False}, headers=h)).status_code == 200
    r = await client.post(base(sid) + "/run", json={}, headers=h)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "processor_disabled"
    assert len(llm.calls) == n                                         # nothing was sent to the model
    await client.put("/v1/privacy/processors/llm", json={"enabled": True}, headers=h)
    assert (await client.post(base(sid) + "/run", json={}, headers=h)).status_code == 200


async def test_run_records_token_usage_and_is_rate_limited(make_user, client, app):
    u, org, h, sid = await seed(make_user, client, TEXTS)
    async with tenant_tx(app.state.pool, None, org) as c:
        assert await c.fetchval("select coalesce(sum(tokens), 0) from ai_usage") == 0
    assert (await client.post(base(sid) + "/run", json={}, headers=h)).status_code == 200
    async with tenant_tx(app.state.pool, None, org) as c:
        assert await c.fetchval("select coalesce(sum(tokens), 0) from ai_usage") > 0
    codes = [(await client.post(base(sid) + "/run", json={}, headers=h)).status_code for _ in range(12)]
    assert 429 in codes                                                # the per-user limit (10 a minute) kicks in


@pytest.mark.parametrize("qs", ["start=2026-13-45&end=2026-14-01", "start=2026-01-01", "end=2026-01-01", "start=2026-02-01&end=2026-01-01"])
async def test_bad_dates_are_a_422_not_a_server_error(make_user, client, qs):
    u, org, h, sid = await seed(make_user, client, TEXTS)
    assert (await client.get(base(sid) + "?" + qs, headers=h)).status_code == 422


async def test_a_small_language_group_cannot_be_recovered_by_subtraction(make_user, client):
    u, org, h, sid = await seed(make_user, client, TEXTS)
    tok = (await client.post(f"/v1/surveys/{sid}/collectors", json={}, headers=h)).json()["token"]
    for t in ["ممتاز", "رائع", "سيء"]:                                  # three Arabic answers: below the minimum group of 5
        r = await client.post(f"/public/v1/c/{tok}/responses", json={"id": str(uuid.uuid4()), "locale": "ar", "answers": [{"q": "nps", "value": 5}, {"q": "why", "value": t}]})
        assert r.status_code == 200, r.text
    await client.post(base(sid) + "/run", json={}, headers=h)
    s = (await client.get(base(sid), headers=h)).json()
    assert s["overall"]["n"] == len(TEXTS) + 3 and s["by_language"]["suppressed"] is True and "en" not in s["by_language"]


async def test_theme_proposal_also_honours_the_llm_switch(make_user, client, app):
    u, org, h, sid = await seed(make_user, client, TEXTS)
    llm = app.state.container.llm
    n = len(llm.calls)
    await client.put("/v1/privacy/processors/llm", json={"enabled": False}, headers=h)
    r = await client.post(f"/v1/surveys/{sid}/questions/why/taxonomy/propose", headers=h)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "processor_disabled" and len(llm.calls) == n
