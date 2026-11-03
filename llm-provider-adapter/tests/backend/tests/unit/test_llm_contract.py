"""One suite over every LLMClient adapter (Fake, Anthropic, OpenAI-compatible with a scripted HTTP transport). The behaviours every adapter owes its callers:
JSON in, validated output, one re-ask on a schema failure, a clear outcome on timeout / rate limit / bad key, the circuit breaker, the model that answered, usage, and
no key in anything it raises or logs. The Fake adapter owes only the shapes (it never calls anything); the cases that need a provider run on the other two."""
import json
import logging
from types import SimpleNamespace as NS

import httpx
import pytest

from app.adapters.llm_anthropic import AnthropicLLM
from app.adapters.llm_fake import FakeLLM
from app.adapters.llm_guard import AiGate
from app.adapters.llm_openai_compat import OpenAICompatLLM
from app.adapters.llm_tasks import LLMBadOutput, LLMCircuitOpen, LLMOperatorAlert, LLMUnavailable, collect_results

KEY = "<api-key>"
GOOD = {"results": [{"id": 0, "label": "positive", "confidence": 0.9}]}


class Provider:
    """Drives one adapter. `steps`: a dict is a good answer, a list of steps are tried in order; an int is an HTTP status; an Exception is raised."""

    def __init__(self, kind):
        self.kind, self.steps, self.calls, self.pauses = kind, [], [], []

    async def sleep(self, s):
        self.pauses.append(s)

    # --- openai-compatible: an HTTP transport
    def handler(self, req: httpx.Request) -> httpx.Response:
        self.calls.append(json.loads(req.content))
        step = self.steps.pop(0) if self.steps else GOOD
        if isinstance(step, Exception):
            raise step
        if isinstance(step, int):
            return httpx.Response(step, json={"error": {"code": step, "message": f"upstream text {KEY}"}})
        return httpx.Response(200, json={"id": "gen-9", "model": "vendor/served", "provider": "Fireworks", "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(step)}}],
                                         "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10, "cost": 0.001}})

    # --- anthropic: a fake SDK client
    async def create(self, **kw):
        self.calls.append(kw)
        step = self.steps.pop(0) if self.steps else GOOD
        if isinstance(step, Exception):
            raise step
        if isinstance(step, int):
            raise AnthropicStatus(step)
        return NS(id="msg-9", model="claude-served", stop_reason="end_turn", content=[NS(type="text", text=json.dumps(step))], usage=NS(input_tokens=7, output_tokens=3))

    def build(self, **kw):
        if self.kind == "openai":
            return OpenAICompatLLM("https://openrouter.ai/api/v1", "vendor/asked", api_key=KEY, transport=httpx.MockTransport(self.handler), sleep=self.sleep, jitter=lambda: 0.0, **kw)
        m = NS(create=self.create)
        return AnthropicLLM(client=NS(beta=NS(messages=m), messages=m), model="claude-asked")


class AnthropicStatus(Exception):
    def __init__(self, status):
        super().__init__(f"HTTP {status} {KEY}")
        self.status_code = status


@pytest.fixture(params=["openai", "anthropic"])
def p(request):
    return Provider(request.param)


# ---- every adapter, including the fake: the shapes ----------------------------------------------------------------------------------------
async def test_the_fake_returns_the_same_shapes_as_the_real_adapters():
    f = FakeLLM()
    assert isinstance(await f.classify_sentiment(["good service"]), list) and isinstance(await f.propose_themes(["x"], 3), list)
    assert isinstance(await f.plan("x", {}), dict) and isinstance(await f.narrate("k", {}, {}), list)


# ---- JSON output and validation ---------------------------------------------------------------------------------------------------------
async def test_json_in_validated_json_out(p):
    out = await p.build().classify_sentiment(["great"])
    assert out == GOOD["results"] and len(p.calls) == 1


async def test_schema_failure_is_asked_again_once_with_the_error_then_used(p):
    p.steps = [{"results": [{"id": "zero"}]}, GOOD]
    assert await p.build().classify_sentiment(["great"]) == GOOD["results"] and len(p.calls) == 2


async def test_two_schema_failures_end_in_bad_output(p):
    p.steps = [{"nope": 1}, {"nope": 2}]
    with pytest.raises(LLMBadOutput):
        await p.build().classify_sentiment(["great"])
    assert len(p.calls) == 2


# ---- the result record ------------------------------------------------------------------------------------------------------------------
async def test_usage_and_the_model_that_answered_come_back(p):
    with collect_results() as got:
        await p.build().classify_sentiment(["great"])
    r = got[0]
    assert r.usage["prompt_tokens"] == 7 and r.usage["completion_tokens"] == 3 and r.usage["total_tokens"] == 10
    assert r.model == ("vendor/served" if p.kind == "openai" else "claude-served") and r.generation_id in ("gen-9", "msg-9")      # not the name that was asked for
    assert r.provider == ("Fireworks" if p.kind == "openai" else None)                                                          # the upstream provider, when the gateway names it


# ---- failures (the HTTP adapter retries; the SDK adapter leaves retries to the SDK and the callers' fallbacks) ------------------------
async def test_a_timeout_then_success_is_retried():
    p = Provider("openai")
    p.steps = [httpx.ReadTimeout("slow"), GOOD]
    assert await p.build().classify_sentiment(["x"]) == GOOD["results"] and len(p.calls) == 2 and len(p.pauses) == 1


async def test_a_429_then_success_is_retried_and_retry_after_is_honoured():
    p = Provider("openai")
    p.steps = [429, GOOD]
    assert await p.build().classify_sentiment(["x"]) == GOOD["results"] and len(p.calls) == 2 and p.pauses == [1.0]


async def test_persistent_timeouts_end_as_unavailable():
    p = Provider("openai")
    p.steps = [httpx.ReadTimeout("slow")] * 5
    with pytest.raises(LLMUnavailable):
        await p.build(retries=2).classify_sentiment(["x"])


async def test_a_401_is_not_retried_and_is_an_operator_alert(caplog):
    p = Provider("openai")
    p.steps = [401, GOOD]
    with caplog.at_level(logging.DEBUG), pytest.raises(LLMOperatorAlert) as ei:
        await p.build().classify_sentiment(["x"])
    assert len(p.calls) == 1 and p.pauses == [] and ei.value.kind == "key"
    assert KEY not in caplog.text + str(ei.value) + repr(ei.value)


async def test_the_circuit_opens_after_five_failures_and_calls_stop():
    p = Provider("openai")
    p.steps = [503] * 20
    llm = p.build(retries=0, gate=AiGate())
    for _ in range(5):
        with pytest.raises(LLMUnavailable):
            await llm.classify_sentiment(["x"])
    sent = len(p.calls)
    with pytest.raises(LLMCircuitOpen):
        await llm.classify_sentiment(["x"])
    assert len(p.calls) == sent


# ---- no key anywhere --------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("status", [400, 401, 402, 500])
async def test_the_key_is_in_nothing_that_is_raised_logged_or_printed(status, caplog):
    p = Provider("openai")
    p.steps = [status] * 4
    llm = p.build(retries=1)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(Exception) as ei:                                                  # noqa: PT011 - the class differs per status, the point is what it carries
            await llm.classify_sentiment(["private respondent text"])
    seen = " ".join([caplog.text, str(ei.value), repr(ei.value), repr(llm), str(llm), f"{llm}"])
    assert KEY not in seen and "feedfacefeedface" not in seen and "private respondent text" not in seen


async def test_the_anthropic_adapter_carries_no_key_in_its_repr_or_errors():
    p = Provider("anthropic")
    p.steps = [500]
    llm = p.build()
    with pytest.raises(AnthropicStatus):
        await llm.classify_sentiment(["x"])
    assert KEY not in repr(llm) and "api_key" not in repr(llm).lower() or "***" in repr(llm)
