"""Tagging with the model (`TagRun.classifier = "llm"`): behind the organisation's switch and the daily caps, the same gate as the keyword classifier, one stored run per
(answers, themes, model), and never half done: any failure ends the run before a single tag is written."""
import httpx
import pytest

from app.adapters.llm_openai_compat import OpenAICompatLLM
from app.app.routers import text as text_router
from tests.integration import test_ai_budget as b
from tests.integration.test_text_pipeline import RANGE, base, freeze_themes, seeded_with

TEXTS = ["Staff were helpful and kind"] * 12 + ["Parking is impossible"] * 8 + ["The porter never smiles at anyone"] * 6              # the last six: no keyword of any theme
PICKS = {"staff were": "service_staff", "parking": "parking", "porter": "service_staff"}


async def ready(make_user, client, app):
    u, org, h, sid = await seeded_with(make_user, client, TEXTS)
    v = await freeze_themes(client, app, h, sid)
    b.POOL[:] = [app.state.pool]
    llm = app.state.container.llm
    llm.calls.clear()
    llm.classes = dict(PICKS)
    return org, h, sid, v, llm


def tag(client, h, sid, v, classifier="llm"):
    return client.post(base(sid) + f"/taxonomy/{v}/tag", json={"classifier": classifier}, headers=h)


async def stored(org):
    return (await b.owner("select count(*) n from answer_tags", org=org))[0]["n"]


def model_calls(llm):
    return [c["classify"] for c in llm.calls if "classify" in c]


async def test_the_model_tags_and_the_shares_follow_what_it_picked(make_user, client, app):
    org, h, sid, v, llm = await ready(make_user, client, app)
    r = await tag(client, h, sid, v)
    assert r.status_code == 200 and r.json()["tagged"] == 26 and r.json()["classifier_version"].startswith("llm-1:")
    sent = [c for c in llm.calls if "classify" in c]
    assert len(sent) == 1 and sorted(sent[0]["theme_ids"]) == ["maintenance", "parking", "service_staff"] and len(sent[0]["classify"]) == 26
    a = (await client.get(base(sid) + f"/analysis?start={RANGE['start']}&end={RANGE['end']}", headers=h)).json()
    rows = {x["theme"]: x["n"] for x in a["shares"]["rows"]}
    assert rows == {"service_staff": 18, "parking": 8}                                  # the six "porter" answers are staff only because the model said so
    g = a["classifier_gate"]                                                            # the readout measures the model's own tags, not what the keyword list would make of them
    assert g["status"] == "pass" and g["other_rate"] == 0.0 and g["answers"] == 26
    keyword = await tag(client, h, sid, v, "keyword")
    assert keyword.status_code == 409 and keyword.json()["detail"]["code"] == "classifier_gate_failed"          # the same answers fail the keyword gate (six in "other")


async def test_the_same_answers_themes_and_model_are_tagged_once(make_user, client, app):
    org, h, sid, v, llm = await ready(make_user, client, app)
    first, again = (await tag(client, h, sid, v)).json(), (await tag(client, h, sid, v)).json()
    assert first["cached"] is False and again["cached"] is True and len(model_calls(llm)) == 1


async def test_a_theme_the_model_invents_becomes_other_and_the_gate_still_applies(make_user, client, app):
    org, h, sid, v, llm = await ready(make_user, client, app)
    llm.classes = PICKS | {"porter": "rudeness"}                                          # not in the frozen list; six of 26 land in "other" (23%)
    r = await tag(client, h, sid, v)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "classifier_gate_failed" and r.json()["detail"]["gate"]["other_rate"] > 0.15
    assert await stored(org) == 0                                                         # a refused run writes nothing


async def test_the_model_never_runs_with_the_switch_off_or_the_cap_used(make_user, client, app):
    org, h, sid, v, llm = await ready(make_user, client, app)
    await b.set_cap(org, tokens=10)
    await b.set_used(org, tokens=10)
    assert (await tag(client, h, sid, v)).status_code == 429
    await b.switch_off(org)
    assert (await tag(client, h, sid, v)).status_code == 403
    assert not model_calls(llm) and await stored(org) == 0
    assert (await tag(client, h, sid, v, "keyword")).status_code == 409                   # the keyword path does not use the processor: it answers (here its own gate refuses)


async def test_a_cap_reached_between_batches_stops_the_run_and_keeps_nothing(make_user, client, app, monkeypatch):
    org, h, sid, v, llm = await ready(make_user, client, app)
    monkeypatch.setattr(text_router, "TAG_BATCH", 10)                                     # three requests for 26 answers
    before = (await b.usage_row(org))[0]                                                  # the set-up (proposing the themes) already used some of the day
    await b.set_cap(org, tokens=before + 40)                                              # the fake reports 50 tokens per request: the cap is reached after the first
    r = await tag(client, h, sid, v)
    assert r.status_code == 429 and len(model_calls(llm)) == 1 and await stored(org) == 0
    assert (await b.usage_row(org))[0] == before + 50                                     # what was spent is recorded


async def test_batches_cover_every_answer_once(make_user, client, app, monkeypatch):
    org, h, sid, v, llm = await ready(make_user, client, app)
    monkeypatch.setattr(text_router, "TAG_BATCH", 10)
    assert (await tag(client, h, sid, v)).status_code == 200
    sent = model_calls(llm)
    assert [len(x) for x in sent] == [10, 10, 6] and sorted(x for batch in sent for x in batch) == sorted(TEXTS) and await stored(org) == 26


async def test_too_many_answers_for_one_run_is_refused_before_any_call(make_user, client, app, monkeypatch):
    org, h, sid, v, llm = await ready(make_user, client, app)
    monkeypatch.setattr(text_router, "TAG_MAX", 20)
    r = await tag(client, h, sid, v)
    assert r.status_code == 409 and r.json()["detail"] == {"code": "too_many_answers", "answers": 26, "max": 20}
    assert not model_calls(llm) and await stored(org) == 0


@pytest.mark.parametrize("kind, flagged", [("invalid", False), ("empty", False), ("credits", True)])
async def test_a_model_that_fails_is_a_409_with_nothing_stored_never_a_5xx(make_user, client, app, kind, flagged):
    org, h, sid, v, llm = await ready(make_user, client, app)

    def handler(req: httpx.Request) -> httpx.Response:
        if kind == "credits":
            return httpx.Response(402, json={"error": {"code": 402, "message": "insufficient credits"}})
        return httpx.Response(200, json={"id": "g", "model": "vendor/m", "choices": [{"finish_reason": "stop", "message": {"content": "{}" if kind == "invalid" else ""}}], "usage": {}})

    async def no_sleep(_):
        return None
    app.state.container.llm = OpenAICompatLLM("https://openrouter.ai/api/v1", "vendor/m", api_key="k", transport=httpx.MockTransport(handler), sleep=no_sleep)
    try:
        r = await tag(client, h, sid, v)
    finally:
        app.state.container.llm = llm
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ai_unavailable" and await stored(org) == 0
    assert (r.headers.get("x-ai-status") == "unavailable") is flagged


async def test_the_model_is_given_only_the_answers_that_say_something(make_user, client, app):
    texts = ["Staff were helpful and kind"] * 20 + ["???", "ok", "!!"]
    u, org, h, sid = await seeded_with(make_user, client, texts)
    v = await freeze_themes(client, app, h, sid)
    b.POOL[:] = [app.state.pool]
    llm = app.state.container.llm
    llm.calls.clear()
    llm.classes = {"staff": "service_staff"}
    assert (await tag(client, h, sid, v)).status_code == 200
    sent = model_calls(llm)
    assert len(sent) == 1 and set(sent[0]) == {"Staff were helpful and kind"} and len(sent[0]) == 20
