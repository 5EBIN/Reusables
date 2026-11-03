"""The per-minute limit on every route that starts model work: per user and per organisation, 429 with `retry_after`, nothing sent to the model when it refuses."""
import json
import logging
import time

import pytest

from app.adapters.ratelimit import MemoryRateLimiter
from app.core.obs import hash_ref
from tests.integration.test_analytics import nps_plan, seed
from tests.integration.test_distribution_flow import invite_member


@pytest.fixture
def limits(app):
    cont = app.state.container
    old = cont.ai_limiter, cont.ai_org_limiter

    def set_(user=1000, org=5000):
        cont.ai_limiter, cont.ai_org_limiter = MemoryRateLimiter(user, 60.0), MemoryRateLimiter(org, 60.0)
    yield set_
    cont.ai_limiter, cont.ai_org_limiter = old


def ask(client, h, text="How likely to recommend?"):
    return client.post("/v1/analytics/ask", json={"text": text}, headers=h)


async def test_a_user_over_the_limit_gets_429_with_retry_after_and_the_model_is_not_called(make_user, client, app, limits):
    u, org, h, sid, _ = await seed(make_user, client)
    llm = app.state.container.llm
    llm.plans["recommend"] = nps_plan(sid)
    limits(user=3)
    llm.calls.clear()
    try:
        for i in range(3):
            assert (await ask(client, h, f"How likely to recommend? {i}")).status_code == 200
        r = await ask(client, h, "How likely to recommend? again")
    finally:
        llm.plans.pop("recommend")
    assert r.status_code == 429 and r.json()["detail"] == {"code": "ai_rate_limited", "retry_after": 60} and r.headers["retry-after"] == "60"
    assert len([c for c in llm.calls if "text" in c]) == 3                               # the refused request never reached the model


async def test_one_users_limit_is_not_another_users(make_user, client, app, limits):
    a, m = make_user(), make_user()
    org = await a.create_org()
    await invite_member(client, a, org, m)
    limits(user=2)
    assert [(await ask(client, a.headers(org), f"q{i}")).status_code for i in range(3)] == [200, 200, 429]
    assert (await ask(client, m.headers(org), "mine")).status_code == 200


async def test_an_organisation_cannot_use_everything_whoever_asks(make_user, client, app, limits):
    a, m = make_user(), make_user()
    org = await a.create_org()
    await invite_member(client, a, org, m)
    limits(user=100, org=4)
    codes = [(await ask(client, (a if i % 2 else m).headers(org), f"q{i}")).status_code for i in range(6)]
    assert codes == [200, 200, 200, 200, 429, 429]                                       # four between them, then every member of that organisation waits
    other = make_user()
    org2 = await other.create_org()
    assert (await ask(client, other.headers(org2), "elsewhere")).status_code == 200      # another organisation is not affected


async def test_the_limit_applies_to_the_other_model_routes_too(make_user, client, app, limits):
    u, org, h, sid, _ = await seed(make_user, client)
    limits(user=1)
    path = f"/v1/surveys/{sid}/questions/kind/taxonomy/propose"
    first = await client.post(path, headers=h)                                           # any route that calls the gate counts
    second = await client.post(path, headers=h)
    assert first.status_code != 429 and second.status_code == 429 and second.json()["detail"]["code"] == "ai_rate_limited"


async def test_the_limit_resets_with_the_window(make_user, client, app, limits, monkeypatch):
    u, org, h, sid, _ = await seed(make_user, client)
    limits(user=1)
    assert (await ask(client, h, "a")).status_code == 200 and (await ask(client, h, "b")).status_code == 429
    real = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: real() + 61)
    assert (await ask(client, h, "c")).status_code == 200


async def test_the_answer_is_logged_with_the_request_id_and_the_organisation(make_user, client, app, limits, caplog):
    u, org, h, sid, _ = await seed(make_user, client)
    llm = app.state.container.llm
    llm.plans["recommend"] = nps_plan(sid)
    try:
        with caplog.at_level(logging.INFO, logger="app.ai"):
            r = await client.post("/v1/analytics/ask", json={"text": "How likely to recommend? (log)"}, headers={**h, "X-Request-ID": "trace0001abcd"})
    finally:
        llm.plans.pop("recommend")
    assert r.status_code == 200 and r.headers["x-request-id"] == "trace0001abcd"
    lines = [json.loads(x.getMessage()) for x in caplog.records if x.name == "app.ai"]
    mine = [x for x in lines if x["rid"] == "trace0001abcd"]
    assert len(mine) == 1 and mine[0]["org"] == hash_ref(org) and mine[0]["task"] == "plan" and mine[0]["model"] == "FakeLLM"
    assert mine[0]["prompt_tokens"] == 40 and mine[0]["completion_tokens"] == 10 and "How likely" not in json.dumps(mine[0])
