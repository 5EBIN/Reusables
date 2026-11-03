"""The per-minute AI limits as settings, the rule that every route passes its request to the gate, and the per-answer AI log line."""
import ast
import json
import logging
import pathlib
from types import SimpleNamespace as NS

import httpx
import pytest

from app.adapters.llm_openai_compat import OpenAICompatLLM
from app.adapters.llm_tasks import collect_results, track_ai_status
from app.app import ai_guard
from app.app.settings import ConfigError, ai_settings
from app.core.obs import hash_ref

ROUTERS = pathlib.Path(__file__).resolve().parents[2] / "src" / "app" / "app" / "routers"


def test_the_limits_default_to_30_a_user_and_120_an_organisation_and_can_be_set():
    a = ai_settings({})
    assert (a.rate_per_minute, a.rate_per_minute_org) == (30, 120)
    b = ai_settings({"AI_RATE_PER_MINUTE": "5", "AI_RATE_PER_MINUTE_ORG": "50"})
    assert (b.rate_per_minute, b.rate_per_minute_org) == (5, 50)
    for bad in ("0", "-3", "many"):
        with pytest.raises(ConfigError):
            ai_settings({"AI_RATE_PER_MINUTE": bad})


def test_every_route_passes_its_request_to_the_gate():
    """gate(c, o, ...) / _guard(c, o, ...): without `o` a route would skip the per-minute limit. Background jobs (not routers) pass nothing, on purpose."""
    seen = 0
    for f in sorted(ROUTERS.glob("*.py")):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("gate", "_guard"):
                seen += 1
                assert len(node.args) >= 2 and isinstance(node.args[1], ast.Name) and node.args[1].id == "o", f"{f.name}:{node.lineno} {node.func.id}() without the request"
    assert seen >= 15                                                                   # the routes that start model work (the number only grows)


class Spy:
    window = 60.0

    def __init__(self, hits):
        self.hits = hits

    async def hit(self, key):
        self.hits.append(key)
        return True


async def test_a_request_is_counted_against_user_and_organisation_and_a_background_job_is_not(monkeypatch):
    hits: list[str] = []
    request = NS(app=NS(state=NS(container=NS(ai_limiter=Spy(hits), ai_org_limiter=Spy(hits)))))
    await ai_guard.rate_limit(NS(user_id="u", org_id="o", request=request))
    assert hits == ["ai-user:u", "ai-org:o"]
    hits.clear()

    async def no_processor_check(c, key):
        return None
    import app.app.routers.privacy as privacy
    monkeypatch.setattr(privacy, "processor_on", no_processor_check)
    await ai_guard.gate(NS(), None, caps=False)                                          # a job: no request, nothing counted
    assert hits == []


# ---- the AI log line -------------------------------------------------------------------------------------------------------------------------
def llm(handler):
    return OpenAICompatLLM("https://openrouter.ai/api/v1", "vendor/asked", api_key="<api-key>", transport=httpx.MockTransport(handler), jitter=lambda: 0.0)


def ok(req):
    reply = json.dumps({"results": [{"id": 0, "label": "positive", "confidence": 0.9}]})
    return httpx.Response(200, json={"id": "gen-7", "model": "vendor/served", "provider": "Fireworks", "choices": [{"finish_reason": "stop", "message": {"content": reply}}],
                                     "usage": {"prompt_tokens": 70, "completion_tokens": 9, "total_tokens": 79, "cost": 0.0004, "completion_tokens_details": {"reasoning_tokens": 2}}})


async def test_one_line_per_answer_with_request_org_cost_and_breaker_and_never_the_text(caplog):
    track_ai_status("req-1234abcd")
    org = "9b2f6c1e-1111-4222-8333-444455556666"
    a = llm(ok)
    with collect_results() as got:
        await a.classify_sentiment(["private respondent text, call me on 0501234567"])
    with caplog.at_level(logging.INFO, logger="app.ai"):
        ai_guard.log_call(org, got[0])
    lines = [json.loads(r.getMessage()) for r in caplog.records if r.name == "app.ai"]
    assert len(lines) == 1
    line = lines[0]
    assert line == {"rid": "req-1234abcd", "org": hash_ref(org), "task": "sentiment", "model": "vendor/served", "provider": "Fireworks", "gen": "gen-7", "prompt_tokens": 70,
                    "completion_tokens": 9, "reasoning_tokens": 2, "cost_usd": 0.0004, "ms": line["ms"], "attempt": 1, "reasked": False, "breaker": "closed"}
    assert isinstance(line["ms"], float) and org not in json.dumps(line)                   # the organisation only as the same short hash the access log uses
    text = caplog.text
    assert "private respondent text" not in text and "0501234567" not in text and "sk-or-v1" not in text


async def test_the_line_has_no_request_id_for_a_job_and_shows_the_probe_call(caplog):
    track_ai_status("")
    a = llm(ok)
    br = a.gate.breaker("vendor/asked")
    for _ in range(5):
        br.failure()
    br.opened_at -= 120                                                                  # the pause is over: the next call is the one probe
    with collect_results() as got:
        await a.classify_sentiment(["x"])
    assert got[0].breaker == "half_open"                                                 # and after it succeeded the breaker closed again
    assert a.gate.breaker("vendor/asked").state == "closed"
    with caplog.at_level(logging.INFO, logger="app.ai"):
        ai_guard.log_call("org-x", got[0])
    assert json.loads(caplog.records[-1].getMessage())["rid"] == ""
