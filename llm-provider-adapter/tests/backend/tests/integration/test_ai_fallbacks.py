"""Every route that calls a model: when the model's reply stays empty or invalid after the one re-ask, the user gets the route's existing fallback result and never a 5xx;
when the provider answers 402 (no credits) the same fallback comes back with `X-AI-Status: unavailable`, which the pages show as "AI temporarily unavailable".
The model is the real OpenAI-compatible adapter over a scripted transport, so the re-ask, the retries and the error mapping are the production ones."""

import httpx
import pytest

from app.adapters.llm_openai_compat import OpenAICompatLLM
from app.app.worker import run_pending
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

FLAG = "x-ai-status"


def provider(kind: str) -> OpenAICompatLLM:
    """What the model provider does for every request. invalid: valid JSON that matches no schema (asked twice); empty: no text; credits: HTTP 402."""
    def handler(req: httpx.Request) -> httpx.Response:
        if kind == "credits":
            return httpx.Response(402, json={"error": {"code": 402, "message": "insufficient credits"}})
        content = "{}" if kind == "invalid" else ""
        return httpx.Response(200, json={"id": "gen-1", "model": "vendor/m", "choices": [{"finish_reason": "stop", "message": {"content": content}}], "usage": {}})

    async def no_sleep(_):
        return None

    return OpenAICompatLLM("https://openrouter.ai/api/v1", "vendor/m", api_key="k", transport=httpx.MockTransport(handler), sleep=no_sleep)


@pytest.fixture
def swap(app):
    cont, old = app.state.container, app.state.container.llm

    def put(kind):
        cont.llm = provider(kind)
    yield put
    cont.llm = old


KINDS = [("invalid", False), ("empty", False), ("credits", True)]       # (what the provider does, whether the response carries the "unavailable" flag)


def check_flag(r, flagged):
    assert (r.headers.get(FLAG) == "unavailable") is flagged, (r.status_code, dict(r.headers))


# ---- the plan builder ("Ask your data") --------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("kind,flagged", KINDS)
async def test_ask_your_data_cannot_yet_instead_of_an_error(make_user, client, swap, kind, flagged):
    u = make_user(); org = await u.create_org()
    swap(kind)
    r = await client.post("/v1/analytics/ask", json={"text": "NPS by month last quarter"}, headers=u.headers(org))
    assert r.status_code == 200 and r.json()["outcome"] == "CANT_YET" and r.json()["reason"]
    check_flag(r, flagged)


# ---- "Ask your survey" ------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("kind,flagged", KINDS)
async def test_ask_your_survey_shows_the_quotes_unverified(make_user, client, app, swap, kind, flagged):
    for w, c in rag_t.SYN.items():
        app.state.container.embedder.add_synonym(w, c)                       # the retrieval test setup (the fake embedder's vocabulary)
    u, org, h, sid = await rag_t.prepared(make_user, client)
    swap(kind)
    r = await rag_t.ask(client, h, sid)
    j = r.json()
    assert r.status_code == 201 and j["status"] == "unverified" and j["answer"] == [] and j["quotes"] and j["reason"]          # "not enough evidence": the retrieved quotes only
    check_flag(r, flagged)


# ---- sentiment ------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("kind,flagged", KINDS)
async def test_a_sentiment_run_is_labelled_by_the_word_list(make_user, client, swap, kind, flagged):
    u, org, h, sid = await sem.seed(make_user, client, sem.NEG + sem.POS + sem.OTHER)
    swap(kind)
    r = await client.post(sent.base(sid) + "/run", json={}, headers=h)
    assert r.status_code == 200 and r.json()["fallback_batches"] >= 1 and r.json()["labelled"] > 0
    check_flag(r, flagged)


# ---- cluster names ----------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("kind,flagged", KINDS)
async def test_clusters_stay_unnamed(make_user, client, swap, kind, flagged):
    u, org, h, sid = await sem.embedded(make_user, client)
    swap(kind)
    r = await client.post(sem.base(sid) + "/cluster", json={"k": 2}, headers=h)
    assert r.status_code == 201 and r.json()["labelled"] == 0
    assert all(c["unlabelled"] for c in (await client.get(sem.base(sid) + "/clusters", headers=h)).json()["clusters"])
    check_flag(r, flagged)


# ---- theme proposals --------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("kind,flagged", KINDS)
async def test_theme_proposal_says_so_and_stores_nothing(make_user, client, swap, kind, flagged):
    u, org, h, sid = await txt.seed(make_user, client)
    swap(kind)
    r = await client.post(txt.base(sid) + "/taxonomy/propose", headers=h)
    assert r.status_code == 409                                                                  # the existing "no themes" outcome, never a 5xx
    assert (r.json()["detail"]["code"] == "ai_unavailable") if flagged else (r.json()["detail"] == "no valid theme proposals")
    assert (await client.get(txt.base(sid) + "/taxonomy", headers=h)).json()["versions"] == []
    check_flag(r, flagged)


# ---- narratives: computed-only text -----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("kind,flagged", KINDS)
async def test_the_text_summary_is_computed_only(make_user, client, app, swap, kind, flagged):
    u, org, h, sid = await txt.seed(make_user, client)
    v = await txt.full_flow(app, client, h, sid)
    await client.post(txt.base(sid) + f"/taxonomy/{v}/tag", headers=h)
    swap(kind)
    r = await client.post(txt.base(sid) + f"/summary?start={txt.RANGE['start']}&end={txt.RANGE['end']}", headers=h)
    assert r.status_code == 201 and r.json()["provenance"] == "computed" and r.json()["text"]
    check_flag(r, flagged)


@pytest.mark.parametrize("kind,flagged", KINDS)
async def test_the_360_summary_is_computed_only(make_user, client, app, swap, kind, flagged):
    a, b, org, h, cid, sid, emps = await f360.setup(make_user, client, app)
    await client.post(f"/v1/feedback/cycles/{cid}/approve-raters", json={"subject_id": sid}, headers=h)
    await f360.launch(client, app, a, b, org, h, cid)
    toks = f360.tokens(app)
    await f360.fill(client, toks, [f"peer{i}@example.ae" for i in range(1, 6)], 4)
    await f360.fill(client, toks, ["user@example.com", "user@example.com"], 4)
    swap(kind)
    r = await client.post(f"/v1/feedback/cycles/{cid}/subjects/{sid}/summary", headers=h)
    assert r.status_code == 201 and r.json()["status"] == "draft" and r.json()["provenance"] == "computed"
    check_flag(r, flagged)


@pytest.mark.parametrize("kind,flagged", KINDS)
async def test_the_interview_summary_is_computed_only(make_user, client, swap, kind, flagged):
    u, org, h, sid, link = await intv.live(make_user, client)
    swap(kind)
    r = await client.get(f"/v1/interviews/{sid}/analysis", headers=h)
    assert r.status_code == 200 and r.json()["summary"]["provenance"] == "computed"
    check_flag(r, flagged)


@pytest.mark.parametrize("kind,flagged", KINDS)
async def test_the_executive_analysis_is_computed_only(make_user, client, swap, kind, flagged):
    a, cons, org, ha, hc = await oi.setup(make_user, client)
    iid = (await client.post("/v1/orgintel/instruments/demo", headers=hc)).json()["id"]
    pid = (await client.post("/v1/orgintel/programs", json={"name": "P", "instrument_id": iid, "pilot": True}, headers=hc)).json()["id"]
    await client.post(f"/v1/orgintel/programs/{pid}/rounds", json={"label": "baseline", "survey_id": await oi.make_survey(client, ha, 4)}, headers=hc)
    swap(kind)
    r = await client.post(f"/v1/orgintel/programs/{pid}/analysis", headers=hc)
    assert r.status_code == 201 and r.json()["provenance"] == "computed" and r.json()["status"] == "draft"
    check_flag(r, flagged)


# ---- the interviewer: the scripted question ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("kind,flagged", KINDS)
async def test_the_interview_continues_with_the_scripted_question(make_user, client, swap, kind, flagged):
    u, org, h, sid, link = await intv.live(make_user, client)
    tok, first = await intv.begin(client, link)
    swap(kind)
    r = await client.post(f"/public/v1/interview/session/{tok}/turn", json={"text": "I chose it because the commute is short and the price is fair."})
    assert r.status_code == 200 and r.json()["state"] == "active" and r.json()["question"]
    check_flag(r, flagged)


# ---- the survey drafter ---------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("kind,flagged", KINDS)
async def test_the_survey_drafter_cannot_yet(make_user, client, swap, kind, flagged):
    u = make_user(); org = await u.create_org()
    swap(kind)
    r = await client.post("/v1/surveys/draft", json={"brief": "A quarterly satisfaction survey for the residents of a community in Abu Dhabi"}, headers=u.headers(org))
    assert r.status_code == 409 and r.json()["detail"]["outcome"] == "CANT_YET"
    check_flag(r, flagged)


# ---- benchmark proposals -------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("kind,flagged", KINDS)
async def test_benchmark_proposals_are_reported_as_unavailable_not_failed(make_user, client, app, swap, kind, flagged):
    a, cons, org, ha, hc = await ba.world(make_user, client)
    swap(kind)
    r = await client.post("/v1/orgintel/benchmarks/agent", json=ba.body(), headers=hc)
    assert r.status_code == 201 and r.json()["saved"] == []
    check_flag(r, flagged)


# ---- research (a background run) -------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("kind,flagged", KINDS)
async def test_a_research_run_finishes_with_a_computed_draft(make_user, client, app, swap, kind, flagged):
    rs.wire(app)
    a, b = make_user(), make_user()
    org = await a.create_org(); await invite_member(client, a, org, b, role="consultant")
    h = a.headers(org)
    r = await client.post("/v1/research", json={"title": "Feasibility", "brief": "Mid-market residential demand in Abu Dhabi", "questions": ["What is the market size?"]}, headers=h)
    pid = r.json()["id"]
    swap(kind)
    assert (await client.post(f"/v1/research/{pid}/run", headers=h)).status_code == 202
    for _ in range(5):
        await run_pending(app.state.pool, app.state.container)
    p = (await client.get(f"/v1/research/{pid}", headers=h)).json()
    assert p["report"] and p["report"]["provenance"] == "computed" and p["status"] != "error"
    assert bool(p["report"].get("ai_unavailable")) is flagged                                     # a background run has no response header: the flag is in the saved report


# ---- no AI route without a test above ------------------------------------------------------------------------------------------------
def test_every_router_that_calls_the_model_is_covered_here():
    """A route that calls the model must have a fallback test in this file. Adding one without a test fails here, so the list below is edited on purpose."""
    import pathlib
    routers = pathlib.Path(__file__).resolve().parents[2] / "src" / "app" / "app" / "routers"
    import re
    users = {p.stem for p in routers.glob("*.py") if "llm" in re.findall(r"[A-Za-z_]+", p.read_text(encoding="utf-8")) or "narrate_or_none" in p.read_text(encoding="utf-8")}
    covered = {"analytics", "ask_text", "feedback360", "interviews", "orgintel", "research", "semantic", "sentiment", "studio", "text"}
    users -= {"privacy"}                                              # only reads the processor switch; it never calls a model
    assert users == covered, f"routers that call the model: {sorted(users)}; covered: {sorted(covered)}"
