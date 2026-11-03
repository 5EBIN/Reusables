"""The call itself: retries, response-format fallback, truncation retry. No prompts, no model tuning: the caller passes the model, the key and the request."""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

import httpx

from app.llm_http import (MAX_ATTEMPTS, RETRYABLE_STATUSES, FormatWithFallback, RawCompletionResult, _rejects_response_format_text, retry_delay)

logger = logging.getLogger(__name__)

UsageHook = Callable[[dict], Awaitable[None]]


async def complete(*, base_url: str, api_key: str, model: str, system_prompt: str, user_prompt: str, temperature: float = 0.2, max_tokens: int = 4000,
                   max_tokens_cap: int | None = None, response_format: dict | None = None, extra_body: dict | None = None, timeout: float = 180.0,
                   on_usage: UsageHook | None = None) -> RawCompletionResult:
    """One chat completion. `extra_body` is merged into the request (for example a provider's reasoning control); `on_usage` receives {model, id, usage, finish_reason}
    after a successful call (metering is the host's business). A reply cut off at max_tokens (finish_reason == "length") is asked again once with twice the room, up to
    `max_tokens_cap` (no retry when it is None)."""
    budget = max_tokens
    last_exc: Exception | None = None
    res = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        body = {"model": model, "temperature": temperature, "max_tokens": budget, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]}
        if response_format is not None:
            body["response_format"] = response_format
        if extra_body:
            body.update(extra_body)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.post(f"{base_url}/chat/completions", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=body)
            if response_format is not None and res.status_code == 400 and _rejects_response_format_text(res):
                fallback = getattr(response_format, "fallback", None)
                logger.warning("[llm_http] provider rejected response_format (HTTP 400) -- retrying %s", "with its fallback" if fallback else "without it")
                if isinstance(response_format, FormatWithFallback):
                    response_format.used = "fallback" if fallback else "none"
                response_format = fallback
                continue
            if res.status_code in RETRYABLE_STATUSES and attempt < MAX_ATTEMPTS:
                delay = retry_delay(attempt, httpx.HTTPStatusError("", request=res.request, response=res))
                logger.warning("[llm_http] HTTP %d (attempt %d/%d) -- retrying in %.1fs", res.status_code, attempt, MAX_ATTEMPTS, delay)
                await asyncio.sleep(delay)
                continue
            res.raise_for_status()
            data = res.json()
            choice = (data.get("choices") or [{}])[0]
            if choice.get("finish_reason") == "length" and max_tokens_cap and budget < max_tokens_cap and attempt < MAX_ATTEMPTS:
                budget = min(max_tokens_cap, budget * 2)
                logger.warning("[llm_http] reply cut at max_tokens -- asking again with %d", budget)
                continue
            break
        except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError) as exc:
            last_exc = exc
            if attempt >= MAX_ATTEMPTS:
                raise
            await asyncio.sleep(retry_delay(attempt, exc))
    if res is None:
        raise RuntimeError("no response after all retry attempts") from last_exc
    data = res.json()
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message", {})
    usage = data.get("usage") or {}
    meta = {"token_usage": {"prompt_tokens": usage.get("prompt_tokens", 0), "completion_tokens": usage.get("completion_tokens", 0),
                            "completion_tokens_details": usage.get("completion_tokens_details") or {}},
            "id": data.get("id"), "model_name": model, "finish_reason": choice.get("finish_reason")}
    result = RawCompletionResult(content=msg.get("content") or "", reasoning=msg.get("reasoning") or None, response_metadata=meta)
    if on_usage is not None:
        try:
            await on_usage({"model": model, "id": data.get("id"), "usage": usage, "finish_reason": choice.get("finish_reason")})
        except Exception as exc:                         # metering must never break the call
            logger.error("[llm_http] usage hook failed: %s", exc)
    return result
