import asyncio

import httpx

from app.llm_http import FormatWithFallback, retry_delay, split_inline_thinking
from app.llm_http_complete import complete


def test_split_inline_thinking():
    reasoning, text = split_inline_thinking("<think>plan it</think>{\"a\": 1}")
    assert reasoning == "plan it" and text == '{"a": 1}'
    assert split_inline_thinking("plain") == (None, "plain")


def test_retry_delay_honours_retry_after_and_cap():
    exc = httpx.HTTPStatusError("", request=httpx.Request("POST", "http://x"), response=httpx.Response(429, headers={"retry-after": "12"}, request=httpx.Request("POST", "http://x")))
    assert retry_delay(1, exc) == 12.0
    assert retry_delay(1, exc, cap=5.0) == 5.0


def _client_factory(handler):
    transport = httpx.MockTransport(handler)
    real = httpx.AsyncClient
    return lambda **kw: real(transport=transport, **kw)


def test_response_format_fallback_and_truncation(monkeypatch):
    calls = []

    def handler(request):
        import json
        body = json.loads(request.content)
        calls.append(body)
        if body.get("response_format", {}).get("name") == "strict":
            return httpx.Response(400, text="response_format is not supported")
        finish = "length" if body["max_tokens"] < 200 else "stop"
        return httpx.Response(200, json={"id": "g1", "choices": [{"message": {"content": "ok"}, "finish_reason": finish}], "usage": {"prompt_tokens": 1, "completion_tokens": 2}})

    monkeypatch.setattr(httpx, "AsyncClient", _client_factory(handler))
    fmt = FormatWithFallback({"type": "json_schema", "name": "strict"}, {"type": "json_object"})
    res = asyncio.run(complete(base_url="http://x", api_key="k", model="m", system_prompt="s", user_prompt="u", max_tokens=100, max_tokens_cap=400, response_format=fmt))
    assert res.content == "ok" and fmt.used == "fallback"
    assert [c["max_tokens"] for c in calls] == [100, 100, 200]
