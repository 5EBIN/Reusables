"""LLMClient on any OpenAI-compatible Chat Completions endpoint (OpenRouter, OpenAI, Groq, Together, Ollama, vLLM, ...).
Base URL, model and key come from the environment (see container.py), so switching provider is a configuration change.

response_format: "json_schema" asks the provider to enforce our schema (strict where the schema allows it); "json_object" only asks for valid JSON and puts the
schema in the prompt, for models without schema support. Either way the output is validated here and downstream by deterministic code.

Failure handling (https://openrouter.ai/docs/api-reference/errors): connection errors, 408, 429 and 5xx are retried with exponential backoff and jitter, honouring
Retry-After; other 4xx are never retried; 401 and 402 are an operator problem (key or credits), logged to `app.alert` and never shown to a user. Five failures in
a row for one model open a breaker for a minute, and a process-wide semaphore limits calls in flight."""
import asyncio
import json
import logging
import random
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.adapters.llm_guard import AiGate
from app.adapters.llm_tasks import (
    SCHEMAS, SYSTEM, TASKS, CallInfo, LLMBadOutput, LLMCircuitOpen, LLMOperatorAlert, LLMRefused, LLMTasks, LLMUnavailable, _wrap, strict_compatible,
)
from app.core.secret import Secret

CONNECT_TIMEOUT = 5.0
READ_TIMEOUT = 60.0
RETRY_STATUS = {408, 429, *range(500, 600)}       # worth another try; a 400, 403 or 404 is not
ALERT_STATUS = {401: "key", 402: "credits"}       # the account, not the request: an operator has to act
MAX_RETRIES = 2
BACKOFF = 1.0                                     # seconds; doubles each try, or the provider's Retry-After (capped) when it sends one
MAX_WAIT = 20.0
alert_log = logging.getLogger("app.alert")


class OpenAICompatLLM(LLMTasks):
    def __init__(self, base_url: str, model: str, api_key: "str | Secret" = "", max_tokens: int | None = None, response_format: str = "json_schema",
                 transport: httpx.AsyncBaseTransport | None = None, extra_headers: dict[str, str] | None = None,
                 retries: int = MAX_RETRIES, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 temperature: float = 0.0, seed: int | None = None, provider: dict[str, Any] | None = None, task_models: dict[str, str] | None = None, reasoning: dict[str, Any] | None = None,
                 timeout: float = READ_TIMEOUT, gate: AiGate | None = None, jitter: Callable[[], float] = random.random):
        if response_format not in ("json_schema", "json_object"):
            raise ValueError("response_format must be json_schema or json_object")
        if not base_url or not model:
            raise ValueError("base_url and model are required")
        self._key = api_key if isinstance(api_key, Secret) else Secret(api_key)
        headers = {"Authorization": f"Bearer {self._key.reveal()}"} if self._key else {}
        self.client = httpx.AsyncClient(base_url=base_url.rstrip("/") + "/", headers=headers | (extra_headers or {}), transport=transport,
                                        timeout=httpx.Timeout(timeout, connect=CONNECT_TIMEOUT))
        self.model, self.max_tokens, self.response_format = model, max_tokens, response_format      # max_tokens: an optional ceiling over the per-task sizes
        self.temperature, self.seed, self.provider, self.task_models, self.reasoning = temperature, seed, provider, dict(task_models or {}), reasoning
        self.retries, self.sleep, self.jitter, self.gate = retries, sleep, jitter, gate or AiGate()

    def __repr__(self) -> str:
        return f"OpenAICompatLLM(model={self.model!r}, key={self._key.masked()!r})"           # never the real key

    def request_body(self, schema_key: str, instruction: str, payload: str) -> tuple[dict[str, Any], str]:
        """The exact request for one task, and the model it goes to. The preflight script sends this same body."""
        schema, spec = SCHEMAS[schema_key], TASKS[schema_key]
        model = self.task_models.get(schema_key, self.model)
        system, user = SYSTEM, f"{instruction}\n\n{_wrap(payload)}"
        body: dict[str, Any] = {"model": model, "max_tokens": min(spec.max_tokens, self.max_tokens or spec.max_tokens),
                                "temperature": spec.temperature if spec.temperature is not None else self.temperature}
        if self.seed is not None:
            body["seed"] = self.seed
        if self.provider:
            body["provider"] = self.provider
        if self.reasoning:
            body["reasoning"] = self.reasoning                          # OpenRouter: reasoning tokens share max_tokens, so a model that thinks first can run out before it answers
        if self.response_format == "json_schema":
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": schema_key, "strict": strict_compatible(schema), "schema": schema}}
        else:
            body["response_format"] = {"type": "json_object"}
            system += "\nReturn one JSON object that matches this JSON schema: " + json.dumps(schema)
        body["messages"] = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        return body, model

    async def _send(self, instruction: str, payload: str, schema_key: str) -> tuple[Any, CallInfo]:
        body, model = self.request_body(schema_key, instruction, payload)
        t0 = time.perf_counter()
        breaker = self.gate.breaker(model).state
        data, attempts = await self._post(body, model)
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        u = data.get("usage") or {}
        pt, ct = u.get("prompt_tokens") or 0, u.get("completion_tokens") or 0
        info = CallInfo(model=data.get("model") or model, task=schema_key, generation_id=data.get("id"), breaker=breaker, provider=data.get("provider") if isinstance(data.get("provider"), str) else None, latency_ms=round((time.perf_counter() - t0) * 1000, 1), attempt=attempts,
                        usage={"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": u.get("total_tokens") or pt + ct, "cost": u.get("cost"),
                               "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens")})

        def unusable(reason: str) -> LLMBadOutput:
            e = LLMBadOutput(reason)
            e.info = info                                               # the provider charged for this answer: the caller records it
            return e
        if msg.get("refusal") or choice.get("finish_reason") == "content_filter":
            raise LLMRefused(msg.get("refusal") or "content_filter")
        if choice.get("finish_reason") == "length":
            raise unusable("truncated")
        text = msg.get("content")
        if not text:
            raise unusable("no text")
        try:
            parsed = json.loads(text)
        except ValueError:
            raise unusable("not json") from None
        return parsed, info

    async def _post(self, body: dict[str, Any], model: str) -> tuple[dict[str, Any], int]:
        """One request, with the retries and the breaker. Returns the parsed response and the number of attempts it took."""
        breaker = self.gate.breaker(model)
        if not breaker.allow():
            raise LLMCircuitOpen(f"circuit open for {model}")
        try:
            data, attempts = await self._attempts(body)
        except (LLMUnavailable, httpx.HTTPError):
            breaker.failure()
            raise
        breaker.success()
        return data, attempts

    async def _attempts(self, body: dict[str, Any]) -> tuple[dict[str, Any], int]:
        for attempt in range(1, self.retries + 2):
            last = attempt == self.retries + 1
            try:
                async with self.gate.semaphore:
                    resp = await self.client.post("chat/completions", json=body)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                if last:
                    raise LLMUnavailable(f"connection failed: {type(e).__name__}") from None
                await self._pause(attempt, None)
                continue
            status = resp.status_code
            if status == 402 and resp.headers.get("retry-after") and not last:         # documented: only the in-flight budget limit sends Retry-After; anything else is out of credits
                await self._pause(attempt, resp.headers.get("retry-after"))
                continue
            if status in ALERT_STATUS:
                alert_log.error("operator alert: the model provider rejected the account (%s, HTTP %s) for model %s", ALERT_STATUS[status], status, body.get("model"))
                raise LLMOperatorAlert(ALERT_STATUS[status])
            if status in RETRY_STATUS:
                if last:
                    raise LLMUnavailable(f"provider answered HTTP {status}")
                await self._pause(attempt, resp.headers.get("retry-after"))
                continue
            if status >= 400:
                raise LLMBadOutput(f"request rejected (HTTP {status})")                  # our request is wrong: a retry would be too
            data = resp.json()
            if isinstance(data, dict) and data.get("error") and not data.get("choices"):    # an error carried inside a 200 (the docs: check for it even when the status is 200)
                code = (data["error"] or {}).get("code") if isinstance(data["error"], dict) else None
                if code in ALERT_STATUS:
                    alert_log.error("operator alert: the model provider rejected the account (%s) for model %s", ALERT_STATUS[code], body.get("model"))
                    raise LLMOperatorAlert(ALERT_STATUS[code])
                if code in RETRY_STATUS and not last:
                    await self._pause(attempt, None)
                    continue
                raise LLMUnavailable(f"provider reported an error ({code})")
            return data, attempt
        raise AssertionError("unreachable")

    async def _pause(self, attempt: int, retry_after: str | None) -> None:
        try:
            wait = float(retry_after) if retry_after else BACKOFF * 2 ** (attempt - 1)
        except ValueError:
            wait = BACKOFF * 2 ** (attempt - 1)
        await self.sleep(min(MAX_WAIT, max(0.0, wait)) * (1 + 0.25 * self.jitter()))

    async def aclose(self) -> None:
        await self.client.aclose()
