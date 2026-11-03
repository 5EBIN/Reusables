"""Phase 4b: what comes back from a call (model, id, usage, cost, latency, attempt), the one re-ask, and how failures are handled. No network."""
import asyncio
import json
import logging

import httpx
import pytest

from app.adapters.llm_guard import AiGate, CircuitBreaker
from app.adapters.llm_openai_compat import OpenAICompatLLM
from app.adapters.llm_tasks import LLMBadOutput, LLMCircuitOpen, LLMOperatorAlert, LLMUnavailable, collect_results, served_model

BASE = "https://openrouter.ai/api/v1"
GOOD = {"results": [{"id": 0, "label": "positive", "confidence": 0.9}]}


def answer(content, model="vendor/served", id_="gen-123", usage=None):
    return {"id": id_, "model": model, "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(content)}}],
            "usage": usage or {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150, "cost": 0.0004}}


class Script:
    """A provider that answers from a list (an int is an HTTP status, a dict a 200 body, an Exception is raised) and records the pauses."""

    def __init__(self, steps):
        self.steps, self.requests, self.pauses = list(steps), [], []

    def handler(self, req: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(req.content))
        step = self.steps.pop(0) if self.steps else answer(GOOD)
        if isinstance(step, Exception):
            raise step
        if isinstance(step, int):
            return httpx.Response(step, json={"error": {"code": step, "message": "secret provider text"}}, headers=self.headers.get(step, {}) if hasattr(self, "headers") else {})
        return httpx.Response(200, json=step)

    async def sleep(self, s):
        self.pauses.append(s)

    def llm(self, **kw):
        return OpenAICompatLLM(BASE, "vendor/asked", api_key="<api-key>", transport=httpx.MockTransport(self.handler), sleep=self.sleep, jitter=lambda: 0.0, **kw)


async def test_the_result_names_the_model_that_answered_the_id_the_usage_the_cost_and_the_attempt():
    s = Script([503, answer(GOOD)])
    with collect_results() as got:
        await s.llm().classify_sentiment(["great"])
    r = got[0]
    assert r.model == "vendor/served" and r.model != "vendor/asked" and r.generation_id == "gen-123" and r.attempt == 2 and r.reasked is False
    assert {k: r.usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens", "cost")} == {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150, "cost": 0.0004} and r.latency_ms >= 0 and r.data == GOOD
    assert served_model(got, s.llm()) == "vendor/served"
    assert served_model([], s.llm()) == "vendor/asked"                                             # no call yet: the configured name


async def test_a_reply_that_breaks_the_schema_is_asked_again_with_the_error_then_used():
    s = Script([answer({"results": [{"id": "zero", "label": "positive", "confidence": 0.9}]}), answer(GOOD)])
    with collect_results() as got:
        out = await s.llm().classify_sentiment(["great"])
    assert out == GOOD["results"] and len(s.requests) == 2
    assert "did not match the required format" in s.requests[1]["messages"][1]["content"] and "results.0.id" in s.requests[1]["messages"][1]["content"]
    assert [r.reasked for r in got] == [False, True] and got[0].data is None and got[1].data == GOOD          # both answers' usage is recorded


async def test_a_second_bad_reply_ends_in_bad_output_so_the_caller_falls_back():
    s = Script([answer({"nope": 1}), answer({"nope": 2})])
    with pytest.raises(LLMBadOutput):
        await s.llm().classify_sentiment(["great"])
    assert len(s.requests) == 2                                                                    # one re-ask, never more


async def test_text_that_is_not_json_is_asked_again_once():
    bad = {"id": "g", "model": "m", "choices": [{"finish_reason": "stop", "message": {"content": "Sure! here you go"}}], "usage": {}}
    s = Script([bad, answer(GOOD)])
    assert await s.llm().classify_sentiment(["x"]) == GOOD["results"]
    assert "not valid JSON" in s.requests[1]["messages"][1]["content"]


async def test_a_truncated_reply_is_not_asked_again():
    cut = {"id": "g", "model": "m", "choices": [{"finish_reason": "length", "message": {"content": "{"}}], "usage": {}}
    s = Script([cut])
    with pytest.raises(LLMBadOutput):
        await s.llm().classify_sentiment(["x"])
    assert len(s.requests) == 1


@pytest.mark.parametrize("status,kind", [(401, "key"), (402, "credits")])
async def test_key_and_credit_problems_are_an_operator_alert_never_the_provider_text(status, kind, caplog):
    s = Script([status])
    with caplog.at_level(logging.ERROR, logger="app.alert"):
        with pytest.raises(LLMOperatorAlert) as ei:
            await s.llm().classify_sentiment(["x"])
    assert ei.value.kind == kind and len(s.requests) == 1 and s.pauses == []                       # not retried
    text = caplog.text + str(ei.value)
    assert "operator alert" in text and "<api-key>" not in text and "secret provider text" not in text


async def test_a_402_with_retry_after_is_the_in_flight_budget_and_is_retried_once():
    s = Script([402, answer(GOOD)])
    s.headers = {402: {"retry-after": "3"}}
    assert await s.llm().classify_sentiment(["x"]) == GOOD["results"] and s.pauses == [3.0]


async def test_a_request_timeout_408_is_retried_and_other_client_errors_are_not():
    s = Script([408, answer(GOOD)])
    assert await s.llm().classify_sentiment(["x"]) == GOOD["results"] and len(s.requests) == 2
    s2 = Script([422])
    with pytest.raises(LLMBadOutput):
        await s2.llm().classify_sentiment(["x"])
    assert len(s2.requests) == 1


async def test_pauses_grow_and_jitter_adds_up_to_a_quarter():
    s = Script([503, 503, answer(GOOD)])
    c = OpenAICompatLLM(BASE, "m", transport=httpx.MockTransport(s.handler), sleep=s.sleep, jitter=lambda: 1.0)
    await c.classify_sentiment(["x"])
    assert s.pauses == [1.25, 2.5]


async def test_an_error_inside_a_200_is_treated_like_the_status_it_carries():
    s = Script([{"error": {"code": 503, "message": "x"}}, answer(GOOD)])
    assert await s.llm().classify_sentiment(["x"]) == GOOD["results"] and len(s.requests) == 2
    s2 = Script([{"error": {"code": 402, "message": "x"}}])
    with pytest.raises(LLMOperatorAlert):
        await s2.llm().classify_sentiment(["x"])


# ---- the breaker ---------------------------------------------------------------------------------------------------------------------------
def test_the_breaker_opens_after_five_failures_pauses_a_minute_then_lets_one_probe_through():
    t = [0.0]
    b = CircuitBreaker(clock=lambda: t[0])
    for _ in range(4):
        b.failure()
    assert b.allow() and b.state == "closed"
    b.failure()
    assert b.state == "open" and not b.allow()
    t[0] = 59.0
    assert not b.allow()
    t[0] = 61.0
    assert b.state == "half_open" and b.allow() and not b.allow()                                 # one probe only
    b.failure()
    assert b.state == "open"                                                                       # the probe failed: another minute
    t[0] = 125.0
    assert b.allow()
    b.success()
    assert b.state == "closed" and b.allow()


async def test_after_five_failures_calls_go_straight_to_the_fallback_without_a_request():
    s = Script([503] * 15)
    t = [0.0]
    c = s.llm(retries=0, gate=AiGate(clock=lambda: t[0]))
    for _ in range(5):
        with pytest.raises(LLMUnavailable):
            await c.classify_sentiment(["x"])
    sent = len(s.requests)
    with pytest.raises(LLMCircuitOpen):
        await c.classify_sentiment(["x"])
    assert len(s.requests) == sent                                                                 # no request while open
    t[0] = 61.0
    s.steps = [answer(GOOD)]
    assert await c.classify_sentiment(["x"]) == GOOD["results"]                                    # the probe succeeds and closes it


async def test_the_breaker_is_per_model_and_bad_output_does_not_count():
    s = Script([503, 503, 503, 503, 503])
    c = s.llm(retries=0, task_models={"classify": "vendor/other"})
    for _ in range(5):
        with pytest.raises(LLMUnavailable):
            await c.classify_sentiment(["x"])
    assert c.gate.breaker("vendor/asked").state == "open" and c.gate.breaker("vendor/other").state == "closed"
    bad = Script([answer({"nope": 1}), answer({"nope": 1})] * 3)
    c2 = bad.llm(retries=0)
    for _ in range(3):
        with pytest.raises(LLMBadOutput):
            await c2.classify_sentiment(["x"])
    assert c2.gate.breaker("vendor/asked").state == "closed"


# ---- concurrency -----------------------------------------------------------------------------------------------------------------------------
async def test_no_more_calls_are_in_flight_than_the_configured_limit():
    live, peak = [0], [0]

    async def handler(req: httpx.Request) -> httpx.Response:
        live[0] += 1
        peak[0] = max(peak[0], live[0])
        await asyncio.sleep(0.02)
        live[0] -= 1
        return httpx.Response(200, json=answer(GOOD))

    c = OpenAICompatLLM(BASE, "m", transport=httpx.MockTransport(handler), gate=AiGate(max_concurrency=2))
    await asyncio.gather(*(c.classify_sentiment([f"t{i}"]) for i in range(8)))
    assert peak[0] == 2


def test_the_timeouts_are_five_seconds_to_connect_and_the_configured_time_to_read():
    c = OpenAICompatLLM(BASE, "m", timeout=42.0)
    t = c.client.timeout
    assert t.connect == 5.0 and t.read == 42.0


@pytest.mark.parametrize("finish,content,reason", [("length", "{", "truncated"), ("stop", "", "no text"), ("stop", "Sure!", "not json")])
async def test_an_unusable_answer_is_still_billed_so_it_is_still_recorded(finish, content, reason, caplog):
    bad = {"id": "gen-bad", "model": "vendor/served", "choices": [{"finish_reason": finish, "message": {"content": content}}],
           "usage": {"prompt_tokens": 100, "completion_tokens": 900, "total_tokens": 1000, "cost": 0.002, "completion_tokens_details": {"reasoning_tokens": 850}}}
    s = Script([bad, bad])
    with collect_results() as got, caplog.at_level(logging.WARNING, logger="app.llm"), pytest.raises(LLMBadOutput):
        await s.llm().classify_sentiment(["x"])
    assert got and all(r.generation_id == "gen-bad" and r.usage["total_tokens"] == 1000 and r.data is None for r in got)       # the provider charged for it
    assert f"reason={reason}" in caplog.text and "reasoning_tokens=850" in caplog.text and "x" not in caplog.text.split("reasoning_tokens=850")[1][:3]
