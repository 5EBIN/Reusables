"""Phase 4a: what a chat request to OpenRouter looks like. No network: a mocked transport records the request."""
import json

import httpx
import pytest

import app.adapters.llm_task_definitions  # noqa: F401  (registers the example tasks)
from app.adapters.llm_tasks import SCHEMAS, TASKS, strict_compatible
from app.adapters.openrouter_options import attribution_headers, is_openrouter, provider_options
from app.app.container import build_container
from app.app.settings import ConfigError, ai_settings

ENV = {"APP_ENV": "test", "LLM_PROVIDER": "openai_compat", "LLM_API_KEY": "<api-key>", "LLM_MODEL": "vendor/base"}


def llm_for(extra=None):
    """The configured client with its transport swapped for one that records requests and answers with a valid sentiment reply."""
    llm = build_container({**ENV, **(extra or {})}).llm
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        content = json.dumps({"results": [{"id": 0, "label": "positive", "confidence": 0.9}], "question": "Why?", "looks_covered": False})
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": content}}], "usage": {}})

    llm.client = httpx.AsyncClient(base_url=str(llm.client.base_url), headers=llm.client.headers, transport=httpx.MockTransport(handler))
    return llm, seen


# ---- the provider object ----------------------------------------------------------------------------------------------------------------
def test_defaults_send_data_collection_allow_and_no_zdr():
    assert provider_options(ai_settings({})) == {"data_collection": "allow", "require_parameters": True, "allow_fallbacks": True}


def test_zdr_and_deny_are_sent_when_switched_on_and_order_only_when_set():
    p = provider_options(ai_settings({"OPENROUTER_DATA_COLLECTION": "deny", "OPENROUTER_ZDR": "true", "OPENROUTER_PROVIDER_ORDER": "anthropic, openai",
                                      "OPENROUTER_ALLOW_FALLBACKS": "false", "OPENROUTER_REQUIRE_PARAMETERS": "false"}))
    assert p == {"data_collection": "deny", "require_parameters": False, "allow_fallbacks": False, "zdr": True, "order": ["anthropic", "openai"]}
    assert "zdr" not in provider_options(ai_settings({"OPENROUTER_ZDR": "false"})) and "order" not in provider_options(ai_settings({}))


def test_attribution_headers_use_the_documented_names():
    assert attribution_headers(ai_settings({"OPENROUTER_APP_URL": "https://app.example", "OPENROUTER_APP_TITLE": "Acme"})) == {"X-OpenRouter-Title": "Acme", "HTTP-Referer": "https://app.example"}
    assert attribution_headers(ai_settings({})) == {"X-OpenRouter-Title": "Acme"}                                 # title defaults to the product name; no referer unless set


@pytest.mark.parametrize("url,expected", [("https://openrouter.ai/api/v1", True), ("https://eu.openrouter.ai/api/v1", True), ("https://openrouter.ai.evil.example/v1", False),
                                          ("https://notopenrouter.ai/v1", False), ("http://localhost:11434/v1", False), ("", False)])
def test_only_openrouter_hosts_count(url, expected):
    assert is_openrouter(url) is expected


# ---- the request body ----------------------------------------------------------------------------------------------------------------
async def test_a_chat_call_to_openrouter_carries_strict_schema_temperature_seed_provider_and_headers():
    llm, seen = llm_for({"OPENROUTER_APP_URL": "https://app.example"})
    await llm.classify_sentiment(["great"])
    req = seen[0]
    body = json.loads(req.content)
    assert body["model"] == "vendor/base" and body["temperature"] == 0.0 and body["seed"] == 7 and body["max_tokens"] == TASKS["sentiment"].max_tokens
    assert body["response_format"]["json_schema"]["strict"] is True and body["response_format"]["json_schema"]["name"] == "sentiment"
    assert body["provider"] == {"data_collection": "allow", "require_parameters": True, "allow_fallbacks": True}          # privacy routing off by default, no zdr
    assert req.headers["x-openrouter-title"] == "Acme" and req.headers["http-referer"] == "https://app.example" and req.headers["authorization"].startswith("Bearer sk-or-")


async def test_the_restricted_setting_reaches_the_request():
    llm, seen = llm_for({"OPENROUTER_DATA_COLLECTION": "deny", "OPENROUTER_ZDR": "true"})
    await llm.classify_sentiment(["x"])
    assert json.loads(seen[0].content)["provider"]["data_collection"] == "deny" and json.loads(seen[0].content)["provider"]["zdr"] is True


async def test_seed_can_be_switched_off_and_another_endpoint_gets_a_plain_request():
    llm, seen = llm_for({"LLM_SEND_SEED": "false"})
    await llm.classify_sentiment(["x"])
    assert "seed" not in json.loads(seen[0].content)
    llm, seen = llm_for({"LLM_BASE_URL": "http://localhost:11434/v1", "LLM_ALLOW_CUSTOM_BASE_URL": "true"})
    await llm.classify_sentiment(["x"])
    body = json.loads(seen[0].content)
    assert "provider" not in body and "x-openrouter-title" not in seen[0].headers                          # OpenRouter's fields are not sent elsewhere


async def test_each_task_can_have_its_own_model_and_the_wording_tasks_their_own_temperature():
    llm, seen = llm_for({"LLM_MODEL_SENTIMENT": "vendor/cheap", "LLM_MODEL_SECONDARY": "vendor/second"})
    await llm.classify_sentiment(["x"])
    await llm.interview_next("learn about parking", "it is hard", "en")
    await llm.draft_survey("resident pulse", "en", "satisfaction")
    bodies = [json.loads(r.content) for r in seen]
    assert bodies[0]["model"] == "vendor/cheap" and bodies[1]["model"] == "vendor/base" and bodies[2]["model"] == "vendor/base"      # LLM_MODEL_SECONDARY is not a task
    assert [b["temperature"] for b in bodies] == [0.0, 0.4, 0.7]                                           # classification at 0; the wording tasks have their own
    assert [b["max_tokens"] for b in bodies] == [TASKS["sentiment"].max_tokens, TASKS["interview"].max_tokens, TASKS["survey"].max_tokens]
    assert bodies[2]["response_format"]["json_schema"]["strict"] is False                                  # a survey definition is free-form
    assert all(TASKS[k].temperature is None for k in TASKS if k not in ("survey", "interview"))              # everything else runs at the configured 0


def test_a_task_model_for_a_task_that_does_not_exist_is_refused_at_startup():
    with pytest.raises(ConfigError, match="sentimnet"):
        build_container({**ENV, "LLM_MODEL_SENTIMNET": "vendor/x"})


# ---- the tables ---------------------------------------------------------------------------------------------------------------------
def test_every_schema_has_a_size_and_nothing_else_does():
    assert set(TASKS) == set(SCHEMAS)
    assert all(t.max_tokens >= 300 for t in TASKS.values())


def test_strict_is_on_for_every_schema_that_can_be_strict_and_the_exceptions_are_named():
    not_strict = {k for k, s in SCHEMAS.items() if not strict_compatible(s)}
    assert not_strict == {"narrate", "survey"}                    # they hold free-form objects (claims; a survey definition); code validates them afterwards
    assert strict_compatible({"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"], "additionalProperties": False})
    assert not strict_compatible({"type": "object", "properties": {"a": {"type": "string"}}, "required": [], "additionalProperties": False})
