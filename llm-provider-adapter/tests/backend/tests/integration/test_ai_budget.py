"""Phase 5: the provider's real usage is stored; the daily token and USD caps and the organisation's `llm` switch are enforced BEFORE any model call on every AI route;
a run that reaches a cap stops cleanly with a consistent partial result. The model is the real OpenAI-compatible adapter over a scripted transport that counts requests."""
import json
import uuid

import httpx
import pytest

from app.adapters.llm_openai_compat import OpenAICompatLLM
from app.app.worker import run_pending
from app.db import tenant_tx
from tests.integration import test_ask_text as rag_t
from tests.integration import test_benchmark_agent as ba
from tests.integration import test_feedback360 as f360
from tests.integration import test_interviews as intv
from tests.integration import test_orgintel as oi
from tests.integration import test_research as rs
from tests.integration import test_semantic as sem
from tests.integration import test_sentiment_api as sent
from tests.integration import test_text_pipeline as txt
from tests.integration.test_distribution_flow import invite_member

USAGE = {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150, "cost": 0.0021}


class Counting:
    """A provider that answers every request (a valid sentiment result for sentiment, an empty object otherwise) and counts the requests."""

    def __init__(self):
        self.requests = 0

    def handler(self, req: httpx.Request) -> httpx.Response:
        self.requests += 1
        body = json.loads(req.content)
        n = len(json.loads(body["messages"][1]["content"].split("<data>")[1].split("</data>")[0])) if body["response_format"]["json_schema"]["name"] == "sentiment" else 0
        content = {"results": [{"id": i, "label": "positive", "confidence": 0.9} for i in range(n)]} if n else {}
        return httpx.Response(200, json={"id": f"gen-{self.requests}", "model": "vendor/served", "usage": USAGE,
                                         "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(content)}}]})

    def llm(self):
        return OpenAICompatLLM("https://openrouter.ai/api/v1", "vendor/asked", api_key="k", transport=httpx.MockTransport(self.handler))


@pytest.fixture
def prov(app):
    """The counting provider. Scenarios are set up with the fake model; `prov.on()` switches to the counting one for the call under test."""
    cont, old, p = app.state.container, app.state.container.llm, Counting()
    POOL[:] = [app.state.pool]
    p.on = lambda: setattr(cont, "llm", p.llm())
    yield p
    cont.llm = old


POOL = []


async def owner(sql, *args, org=None):
    """Runs a statement inside the organisation's tenant context (the API role: it holds the grants these tables need; row-level security is forced for everyone)."""
    async with tenant_tx(POOL[0], None, str(org) if org else None) as c:
        return await c.fetch(sql, *args)


async def usage_row(org):
    r = await owner("select coalesce(sum(tokens),0)::int t, coalesce(sum(cost_usd),0) c from ai_usage where day=current_date", org=org)
    return r[0]["t"], float(r[0]["c"])


async def set_used(org, tokens=0, usd=0.0):
    await owner("insert into ai_usage(org_id,day,tokens,cost_usd) values($1,current_date,$2,$3) on conflict (org_id,day) do update set tokens=$2, cost_usd=$3", uuid.UUID(org), tokens, usd, org=org)


async def set_cap(org, usd=None, tokens=None):
    await owner("insert into org_settings(org_id) values($1) on conflict (org_id) do nothing", uuid.UUID(org), org=org)
    if usd is not None:
        await owner("update org_settings set ai_daily_usd=$2 where org_id=$1", uuid.UUID(org), usd, org=org)
    if tokens is not None:
        await owner("update org_settings set ai_daily_tokens=$2 where org_id=$1", uuid.UUID(org), tokens, org=org)


async def switch_off(org):
    await owner("insert into org_processors(org_id,key,enabled) values($1,'llm',false) on conflict (org_id,key) do update set enabled=false", uuid.UUID(org), org=org)


# ---- one scenario per AI route: (org, headers, call) -------------------------------------------------------------------------------------
async def s_ask_data(make_user, client, app):
    u = make_user(); org = await u.create_org(); h = u.headers(org)
    return org, h, lambda: client.post("/v1/analytics/ask", json={"text": "NPS by month last quarter"}, headers=h)


async def s_ask_survey(make_user, client, app):
    for w, c in rag_t.SYN.items():
        app.state.container.embedder.add_synonym(w, c)
    u, org, h, sid = await rag_t.prepared(make_user, client)
    return org, h, lambda: rag_t.ask(client, h, sid)


async def s_sentiment(make_user, client, app):
    u, org, h, sid = await sem.seed(make_user, client, sem.NEG + sem.POS + sem.OTHER)
    return org, h, lambda: client.post(sent.base(sid) + "/run", json={}, headers=h)


async def s_embed(make_user, client, app):
    u, org, h, sid = await sem.seed(make_user, client)
    return org, h, lambda: client.post(sem.base(sid) + "/embed", json={}, headers=h)


async def s_cluster(make_user, client, app):
    u, org, h, sid = await sem.embedded(make_user, client)
    return org, h, lambda: client.post(sem.base(sid) + "/cluster", json={"k": 2}, headers=h)


async def s_propose(make_user, client, app):
    u, org, h, sid = await txt.seed(make_user, client)
    return org, h, lambda: client.post(txt.base(sid) + "/taxonomy/propose", headers=h)


async def s_text_summary(make_user, client, app):
    u, org, h, sid = await txt.seed(make_user, client)
    v = await txt.full_flow(app, client, h, sid)
    await client.post(txt.base(sid) + f"/taxonomy/{v}/tag", headers=h)
    return org, h, lambda: client.post(txt.base(sid) + f"/summary?start={txt.RANGE['start']}&end={txt.RANGE['end']}", headers=h)


async def s_360(make_user, client, app):
    a, b, org, h, cid, sid, emps = await f360.setup(make_user, client, app)
    await client.post(f"/v1/feedback/cycles/{cid}/approve-raters", json={"subject_id": sid}, headers=h)
    await f360.launch(client, app, a, b, org, h, cid)
    toks = f360.tokens(app)
    await f360.fill(client, toks, [f"peer{i}@example.ae" for i in range(1, 6)], 4)
    await f360.fill(client, toks, ["user@example.com", "user@example.com"], 4)
    return org, h, lambda: client.post(f"/v1/feedback/cycles/{cid}/subjects/{sid}/summary", headers=h)


async def s_exec(make_user, client, app):
    a, cons, org, ha, hc = await oi.setup(make_user, client)
    iid = (await client.post("/v1/orgintel/instruments/demo", headers=hc)).json()["id"]
    pid = (await client.post("/v1/orgintel/programs", json={"name": "P", "instrument_id": iid, "pilot": True}, headers=hc)).json()["id"]
    await client.post(f"/v1/orgintel/programs/{pid}/rounds", json={"label": "baseline", "survey_id": await oi.make_survey(client, ha, 4)}, headers=hc)
    return org, hc, lambda: client.post(f"/v1/orgintel/programs/{pid}/analysis", headers=hc)


async def s_benchmarks(make_user, client, app):
    a, cons, org, ha, hc = await ba.world(make_user, client)
    return org, hc, lambda: client.post("/v1/orgintel/benchmarks/agent", json=ba.body(), headers=hc)


async def s_drafter(make_user, client, app):
    u = make_user(); org = await u.create_org(); h = u.headers(org)
    return org, h, lambda: client.post("/v1/surveys/draft", json={"brief": "A quarterly satisfaction survey for the residents of a community in Abu Dhabi"}, headers=h)


async def s_research(make_user, client, app):
    rs.wire(app)
    a, b = make_user(), make_user()
    org = await a.create_org(); await invite_member(client, a, org, b, role="consultant")
    h = a.headers(org)
    pid = (await client.post("/v1/research", json={"title": "F", "brief": "Mid-market residential demand in Abu Dhabi", "questions": ["What is the market size?"]}, headers=h)).json()["id"]
    return org, h, lambda: client.post(f"/v1/research/{pid}/run", headers=h)


ROUTES = [s_ask_data, s_ask_survey, s_sentiment, s_embed, s_cluster, s_propose, s_text_summary, s_360, s_exec, s_benchmarks, s_drafter, s_research]
IDS = [r.__name__[2:] for r in ROUTES]


# ---- the switch --------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("scenario", ROUTES, ids=IDS)
async def test_switch_off_is_403_on_every_ai_route_and_nothing_is_sent(make_user, client, app, prov, scenario):
    org, h, call = await scenario(make_user, client, app)
    prov.on()
    await switch_off(org)
    before = prov.requests
    r = await call()
    assert r.status_code == 403 and r.json()["detail"]["code"] == "processor_disabled", (r.status_code, r.text)
    assert prov.requests == before


# ---- the caps ------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("scenario", ROUTES, ids=IDS)
async def test_the_token_cap_is_429_before_any_model_call(make_user, client, app, prov, scenario):
    org, h, call = await scenario(make_user, client, app)
    prov.on()
    await set_used(org, tokens=300_000)                                   # the default cap is 200,000
    before = prov.requests
    r = await call()
    assert r.status_code == 429 and "budget" in str(r.json()["detail"]) and "tokens" in str(r.json()["detail"]), (r.status_code, r.text)
    assert prov.requests == before


@pytest.mark.parametrize("scenario", ROUTES, ids=IDS)
async def test_the_usd_cap_is_429_before_any_model_call(make_user, client, app, prov, scenario):
    org, h, call = await scenario(make_user, client, app)
    prov.on()
    await set_cap(org, usd=0.01)
    await set_used(org, tokens=10, usd=0.01)
    before = prov.requests
    r = await call()
    assert r.status_code == 429 and "spend" in str(r.json()["detail"]), (r.status_code, r.text)
    assert prov.requests == before


async def test_the_environment_defaults_are_ceilings_and_a_cap_resets_each_day(make_user, client, app, prov, monkeypatch):
    org, h, call = await s_ask_data(make_user, client, app)
    prov.on()
    await set_used(org, tokens=500, usd=0.5)
    monkeypatch.setenv("AI_DAILY_TOKEN_CAP", "400")
    assert (await call()).status_code == 429                                 # lower than the organisation's own 200,000
    monkeypatch.delenv("AI_DAILY_TOKEN_CAP")
    monkeypatch.setenv("AI_DAILY_USD_CAP", "0.4")
    assert (await call()).status_code == 429 and prov.requests == 0
    monkeypatch.setenv("AI_DAILY_USD_CAP", "5")
    assert (await call()).status_code == 200                                 # under both
    await owner("update ai_usage set day = current_date - 1", org=org)
    monkeypatch.setenv("AI_DAILY_TOKEN_CAP", "400")
    assert (await call()).status_code == 200                                 # yesterday's usage does not count today


# ---- real usage is stored ------------------------------------------------------------------------------------------------------------------
async def test_a_sentiment_run_stores_the_providers_real_usage_cost_model_and_generation_id(make_user, client, app, prov):
    org, h, call = await s_sentiment(make_user, client, app)
    prov.on()
    r = await call()
    assert r.status_code == 200 and r.json()["labelled"] > 0 and prov.requests >= 1
    rows = await owner("select * from ai_calls order by at", org=org)
    assert len(rows) == prov.requests
    assert {x["task"] for x in rows} == {"sentiment"} and {x["model"] for x in rows} == {"vendor/served"}               # the model that answered, not the one asked for
    assert {x["generation_id"] for x in rows} == {f"gen-{i}" for i in range(1, prov.requests + 1)}
    assert all(x["prompt_tokens"] == 120 and x["completion_tokens"] == 30 and float(x["cost_usd"]) == 0.0021 and x["attempt"] == 1 for x in rows)
    assert await usage_row(org) == (150 * prov.requests, pytest.approx(0.0021 * prov.requests))                          # exactly what the provider said: no chars // 4


async def test_theme_proposal_now_records_its_usage(make_user, client, app, prov):
    org, h, call = await s_propose(make_user, client, app)
    prov.on()
    assert (await call()).status_code == 409                                                                             # the scripted reply holds no themes
    assert prov.requests == 2 and (await usage_row(org))[0] == 300                                                       # two answers (the invalid one was asked again), both counted
    assert [x["reasked"] for x in await owner("select reasked from ai_calls order by at", org=org)] == [False, True]


async def test_usage_of_a_failed_route_is_still_recorded(make_user, client, app, prov):
    org, h, call = await s_drafter(make_user, client, app)
    prov.on()
    r = await call()
    assert r.status_code == 409                                                                                          # the empty replies are no draft
    assert (await usage_row(org))[0] == 150 * prov.requests and prov.requests >= 1


async def test_the_organisations_are_metered_separately(make_user, client, app, prov):
    o1, h1, c1 = await s_ask_data(make_user, client, app)
    o2, h2, c2 = await s_ask_data(make_user, client, app)
    prov.on()
    await c1()
    assert (await usage_row(o1))[0] > 0 and await usage_row(o2) == (0, 0.0)


# ---- a run that reaches the cap stops cleanly ------------------------------------------------------------------------------------------
async def test_a_sentiment_run_stops_at_the_cap_keeping_what_it_labelled(make_user, client, app, prov, monkeypatch):
    from app.app.routers import sentiment as sr
    monkeypatch.setattr(sr, "MAX_BATCH", 6)
    org, h, call = await s_sentiment(make_user, client, app)
    prov.on()
    await set_cap(org, tokens=250)                                       # one batch costs 150 tokens: the second batch starts at 150 < 250, the third finds 300 >= 250
    r = await call()
    j = r.json()
    assert r.status_code == 200 and j["stopped"] == "cap" and prov.requests == 2
    assert j["labelled"] == 12 and j["remaining"] == len(sem.NEG + sem.POS + sem.OTHER) - 12
    stored = await owner("select count(*) n from answer_sentiment", org=org)
    assert stored[0]["n"] == 12 and j["fallback_batches"] == 0                                                           # a consistent partial result, no half-written batch
    again = await call()
    assert again.status_code == 429                                                                                      # today's budget is gone: the next run waits for tomorrow


async def test_a_research_run_at_the_cap_is_refused_and_one_that_reaches_it_keeps_its_findings(make_user, client, app, prov):
    org, h, call = await s_research(make_user, client, app)
    prov.on()
    await set_used(org, tokens=250_000)
    assert (await call()).status_code == 429
    await set_used(org, tokens=0)
    assert (await call()).status_code == 202
    for _ in range(5):
        await run_pending(app.state.pool, app.state.container)
    assert prov.requests >= 1 and (await usage_row(org))[0] == 150 * prov.requests


# ---- places that degrade instead of failing -------------------------------------------------------------------------------------------
async def test_the_interviewer_uses_the_scripted_question_when_the_cap_is_reached(make_user, client, app, prov):
    u, org, h, sid, link = await intv.live(make_user, client)
    tok, first = await intv.begin(client, link)
    prov.on()
    await set_used(org, tokens=300_000)
    r = await client.post(f"/public/v1/interview/session/{tok}/turn", json={"text": "I chose it because the commute is short and the price is fair."})
    assert r.status_code == 200 and r.json()["question"] and prov.requests == 0


async def test_the_interview_analysis_page_still_loads_with_the_computed_summary_when_ai_is_off_or_capped(make_user, client, app, prov):
    u, org, h, sid, link = await intv.live(make_user, client)
    prov.on()
    await set_used(org, tokens=300_000)
    r = await client.get(f"/v1/interviews/{sid}/analysis", headers=h)
    assert r.status_code == 200 and r.json()["summary"]["provenance"] == "computed" and prov.requests == 0
    await set_used(org, tokens=0)
    await switch_off(org)
    r = await client.get(f"/v1/interviews/{sid}/analysis", headers=h)
    assert r.status_code == 200 and r.json()["summary"]["provenance"] == "computed" and prov.requests == 0
