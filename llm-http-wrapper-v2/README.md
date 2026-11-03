# llm-http-wrapper-v2

**Category:** backend-helpers  
**Origin:** extracted from a production Next.js/FastAPI app.

**Variant of:** `llm-provider-adapter` (existing module). **How it differs:** that adapter is a typed port with circuit breaker and strict-schema re-ask; this one keeps the provider's reasoning field, falls back through response formats, retries truncated replies and honours Retry-After.

## What it does
Chat completion over raw httpx for OpenRouter-style APIs: bounded retries with equal-jitter backoff and Retry-After, response-format fallback chain (`FormatWithFallback`), one truncation retry with more room, inline `<think>` splitting, native reasoning extraction, and a usage hook.

## Problem it solved
Client libraries drop the provider's reasoning field, a rejected structured-output schema failed the whole call, and a reply cut at max_tokens produced broken JSON.

## Public interface
* `app/llm_http.py`: `def retry_delay(attempt: int, exc: Exception | None=None, cap: float=30.0) -> float`
* `app/llm_http.py`: `class FormatWithFallback`
* `app/llm_http.py`: `def split_inline_thinking(text: str) -> tuple[str | None, str]`
* `app/llm_http.py`: `def extract_native_reasoning(response) -> str | None`
* `app/llm_http.py`: `class RawCompletionResult`
* `app/llm_http_complete.py`: `async def complete(*, base_url: str, api_key: str, model: str, system_prompt: str, user_prompt: str, temperature: float=0.2, max_tokens: int=4000, max_tokens_cap: int | None=None, response_format: dict | None=None, extra_body: dict | None=None, timeout: float=180.0, on_usage: UsageHook | None=None) -> RawCompletionResult`

## Dependencies
Python (`deps.txt`): `httpx>=0.27`

## Stubs and what the host must provide
No stubs: every import resolves inside the module.

## Known limits
No prompts, no model table, no reasoning tuning: callers pass them. Metering is the `on_usage` hook.

## Quality
B (3 tests copied; network faked with a mock transport)  
Tests copied: 1 (copied from the source, not run here).

## How to reuse
Call `complete(...)`; pass `response_format=FormatWithFallback(strict, loose)`.
