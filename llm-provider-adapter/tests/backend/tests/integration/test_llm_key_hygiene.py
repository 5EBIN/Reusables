"""A failing model call must leave neither the API key nor respondent text in logs, error messages or API responses."""
import json
import logging

import httpx
import pytest

from app.adapters.llm_openai_compat import OpenAICompatLLM
from app.adapters.llm_tasks import LLMOperatorAlert
from app.core.secret import Secret
from tests.integration.test_semantic import NEG, OTHER, POS, seed
from tests.integration.test_sentiment_api import base

KEY = "<api-key>"
TEXTS = NEG + POS + OTHER


def failing(status: int, echo: bool = True) -> OpenAICompatLLM:
    def handler(request: httpx.Request) -> httpx.Response:
        # a hostile or careless upstream that echoes the request back in its error body
        body = {"error": {"message": f"bad request {request.headers.get('authorization')} {request.content.decode()[:400]}" if echo else "nope"}}
        return httpx.Response(status, json=body)

    async def no_sleep(_s):
        return None

    return OpenAICompatLLM("https://openrouter.ai/api/v1", "vendor/model", Secret(KEY), transport=httpx.MockTransport(handler), sleep=no_sleep)


@pytest.fixture
def swap_llm(app):
    cont = app.state.container
    old = cont.llm
    yield lambda llm: setattr(cont, "llm", llm)
    cont.llm = old


async def test_adapter_errors_carry_neither_key_nor_text(caplog):
    caplog.set_level(logging.DEBUG)
    llm = failing(401)
    with pytest.raises(LLMOperatorAlert) as ei:
        await llm.classify_sentiment(["my private respondent comment"])
    for text in (str(ei.value), repr(ei.value), repr(llm), caplog.text):
        assert KEY not in text and "feedfacefeedface" not in text
    assert "my private respondent comment" not in str(ei.value) + repr(ei.value) + caplog.text


@pytest.mark.parametrize("status", [401, 402, 429, 500, 503])
async def test_a_failing_provider_during_a_sentiment_run_leaks_nothing(make_user, client, swap_llm, caplog, status):
    u, org, h, sid = await seed(make_user, client, TEXTS)
    swap_llm(failing(status))
    caplog.set_level(logging.DEBUG)
    r = await client.post(base(sid) + "/run", json={}, headers=h)
    assert r.status_code == 200 and r.json()["fallback_batches"] >= 1             # the word list took over, the request itself did not fail
    everything = caplog.text + r.text + json.dumps(dict(r.headers))
    assert KEY not in everything and "feedfacefeedface" not in everything
    for t in TEXTS:
        assert t not in caplog.text                                                # the log lines name the exception type and a count, never the answers
