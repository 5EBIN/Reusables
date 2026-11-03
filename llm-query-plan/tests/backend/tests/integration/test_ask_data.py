"""The "Ask your data" route with the model's plan in its own terms: a named period, opaque survey ids, the selected survey, the follow-up context."""
import json
import re
import uuid

from tests.integration.test_analytics import seed

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def model_plan(**kw):
    """What the model returns for 'NPS of the survey over the last 30 days': survey s1 by its opaque id, the period by name."""
    return {"outcome": "ANSWER", "metric": "NPS", "dimensions": [], "period": "last_30_days", "filters": [
        {"dim": "SURVEY", "op": "eq", "value": ["s1"]}, {"dim": "QUESTION", "op": "eq", "value": ["nps"]}], **kw}


async def ask(client, h, text, **body):
    r = await client.post("/v1/analytics/ask", json={"text": text, **body}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def test_a_named_period_and_an_opaque_survey_id_become_a_real_query(make_user, client, app):
    u, org, h, sid, _ = await seed(make_user, client)
    llm = app.state.container.llm
    llm.calls.clear()
    llm.plans["recommend"] = model_plan()
    try:
        r = await ask(client, h, "How likely are people to recommend us in the last 30 days?")
    finally:
        llm.plans.pop("recommend")
    assert r["outcome"] == "ANSWER" and r["rows"][0]["value"] == 40 and r["n"] == 10
    assert r["plan"]["filters"][0]["value"] == sid and r["plan"]["date_range"]["end"] == r["plan"]["date_range"]["end"]    # stored with the real id and real dates
    cat = llm.calls[0]["catalog"]
    assert cat["surveys"][0]["id"] == "s1" and [q["id"] for q in cat["surveys"][0]["questions"]] == ["nps", "kind"]
    assert not UUID.search(json.dumps(cat)) and cat["time_zone"] == "Asia/Dubai" and re.fullmatch(r"\d{4}-\d\d-\d\d", cat["today"])


async def test_no_period_in_the_question_asks_which_range(make_user, client, app):
    u, org, h, sid, _ = await seed(make_user, client)
    llm = app.state.container.llm
    llm.plans["recommend"] = model_plan(period=None)
    try:
        r = await ask(client, h, "How likely are people to recommend us?")
    finally:
        llm.plans.pop("recommend")
    assert r["outcome"] == "CLARIFY" and "date range" in r["clarify_question"].lower()


async def test_the_selected_survey_reaches_the_model_and_an_unknown_one_is_404(make_user, client, app):
    u, org, h, sid, _ = await seed(make_user, client)
    llm = app.state.container.llm
    llm.calls.clear()
    await ask(client, h, "anything", survey_id=sid)
    assert llm.calls[0]["catalog"]["selected_survey"] == "s1" and not UUID.search(json.dumps(llm.calls[0]["catalog"]))
    r = await client.post("/v1/analytics/ask", json={"text": "anything", "survey_id": str(uuid.uuid4())}, headers=h)
    assert r.status_code == 404


async def test_another_organisations_survey_cannot_be_selected(make_user, client, app):
    u, org, h, sid, _ = await seed(make_user, client)
    other = make_user()
    oorg = await other.create_org()
    r = await client.post("/v1/analytics/ask", json={"text": "anything", "survey_id": sid}, headers=other.headers(oorg))
    assert r.status_code == 404


async def test_a_follow_up_gets_the_previous_plan_without_database_ids(make_user, client, app):
    u, org, h, sid, _ = await seed(make_user, client)
    llm = app.state.container.llm
    llm.plans["recommend"] = model_plan()
    try:
        first = await ask(client, h, "How likely are people to recommend us in the last 30 days?")
    finally:
        llm.plans.pop("recommend")
    llm.calls.clear()
    await ask(client, h, "and by month?", follow_up_of=first["id"])
    prev = llm.calls[0]["catalog"]["previous_plan"]
    assert not UUID.search(json.dumps(llm.calls[0]["catalog"])) and prev["period"] == "custom" and "date_range" not in prev
    assert {f["dim"]: f["value"] for f in prev["filters"]} == {"SURVEY": "s1", "QUESTION": "nps"}


# ---- the plan cache: the same question gives the same plan, without asking the model again ---------------------------------------------------
from app.adapters.llm_tasks import CallResult  # noqa: E402
from app.app.ai_guard import spend_on  # noqa: E402
from app.db import tenant_tx  # noqa: E402
from tests.integration import test_ai_budget as b  # noqa: E402


async def cached_rows(app, org):
    b.POOL[:] = [app.state.pool]
    return await b.owner("select key, plan from ask_plan_cache", org=org)


async def test_the_same_question_is_planned_once(make_user, client, app):
    u, org, h, sid, _ = await seed(make_user, client)
    llm = app.state.container.llm
    llm.calls.clear()
    llm.plans["recommend"] = model_plan()
    try:
        first = await ask(client, h, "How likely are people to recommend us in the last 30 days?")
        again = await ask(client, h, "  how likely are people to RECOMMEND us in the last 30 days  ")      # spacing and case are not a different question
        third = await ask(client, h, "How likely are people to recommend us in the last 30 days؟")
    finally:
        llm.plans.pop("recommend")
    assert len(llm.calls) == 1 and first["plan_cached"] is False and again["plan_cached"] is True and third["plan_cached"] is True
    assert again["rows"] == first["rows"] and again["plan"] == first["plan"] and again["outcome"] == "ANSWER"
    assert len(await cached_rows(app, org)) == 1


async def test_a_new_survey_a_new_question_or_a_failed_plan_is_not_served_from_the_cache(make_user, client, app):
    u, org, h, sid, _ = await seed(make_user, client)
    llm = app.state.container.llm
    llm.calls.clear()
    llm.plans["recommend"] = model_plan()
    try:
        await ask(client, h, "How likely are people to recommend us in the last 30 days?")
        await ask(client, h, "How likely are people to recommend us in the last 7 days?")                  # another question
        assert len(llm.calls) == 2
        await client.post("/v1/surveys", json={"id": str(uuid.uuid4()), "title": {"default": "Another"}}, headers=h)
        r = await ask(client, h, "How likely are people to recommend us in the last 30 days?")             # the catalogue changed
        assert r["plan_cached"] is False and len(llm.calls) == 3
    finally:
        llm.plans.pop("recommend")
    llm.plans["zzz"] = "select 1"                                                                          # not a plan: never stored
    try:
        for _ in range(2):
            assert (await ask(client, h, "zzz"))["outcome"] == "CLARIFY"
        assert sum(1 for c in llm.calls if c["text"] == "zzz") == 2
    finally:
        llm.plans.pop("zzz")
    assert len(await cached_rows(app, org)) == 3


async def test_a_stored_plan_is_free_when_the_cap_is_used_but_not_when_the_switch_is_off(make_user, client, app):
    u, org, h, sid, _ = await seed(make_user, client)
    b.POOL[:] = [app.state.pool]
    llm = app.state.container.llm
    llm.plans["recommend"] = model_plan()
    try:
        await ask(client, h, "How likely are people to recommend us in the last 30 days?")
        llm.calls.clear()
        await b.set_cap(org, tokens=10)
        await b.set_used(org, tokens=10)
        again = await ask(client, h, "How likely are people to recommend us in the last 30 days?")           # cached: no model, no cap needed
        assert again["plan_cached"] is True and not llm.calls
        other = await client.post("/v1/analytics/ask", json={"text": "and in the last 7 days?"}, headers=h)   # not cached: the cap applies
        assert other.status_code == 429 and not llm.calls
        await b.switch_off(org)
        off = await client.post("/v1/analytics/ask", json={"text": "How likely are people to recommend us in the last 30 days?"}, headers=h)
        assert off.status_code == 403                                                                          # the switch applies to a stored plan too
    finally:
        llm.plans.pop("recommend")


async def test_the_provider_that_served_an_answer_is_recorded(make_user, client, app):
    u = make_user()
    org = await u.create_org()
    r = CallResult(model="vendor/m", task="plan", generation_id="gen-1", provider="Fireworks", usage={"prompt_tokens": 5, "completion_tokens": 3, "cost": 0.001})
    r2 = CallResult(model="vendor/m", task="plan", generation_id="gen-2", usage={"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.0})            # a gateway that says nothing
    async with tenant_tx(app.state.pool, None, org) as c:
        await spend_on(c, org, [r, r2])
    b.POOL[:] = [app.state.pool]
    rows = await b.owner("select generation_id, provider from ai_calls order by generation_id", org=org)
    assert [(x["generation_id"], x["provider"]) for x in rows] == [("gen-1", "Fireworks"), ("gen-2", None)]
