"""Completion over a raw httpx call to an OpenRouter-style chat API.

Why it exists: some client libraries drop the provider's `message.reasoning` field when they parse the reply. A direct call keeps it. This module also holds the
three things every direct caller needs: a bounded retry for transient statuses, a response-format fallback (a schema the provider rejects is retried with the next one),
and a truncation retry (a reply cut at max_tokens is asked again with more room, up to a cap).
"""
from __future__ import annotations

import asyncio
import logging
import random
import re

import httpx

logger = logging.getLogger(__name__)

RETRYABLE_STATUSES = {404, 408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
RETRY_DELAYS = [2.0, 4.0]


def retry_delay(attempt: int, exc: Exception | None = None, cap: float = 30.0) -> float:
    """Equal-jitter backoff in [base/2, base] (so concurrent callers do not retry in lockstep), raised to the server's Retry-After (seconds) when it sent one, never above `cap`."""
    base = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS)) - 1]
    delay = random.uniform(base / 2, base)
    headers = getattr(getattr(exc, "response", None), "headers", None)
    try:
        retry_after = float(headers.get("retry-after")) if headers is not None and headers.get("retry-after") else None
    except (TypeError, ValueError):
        retry_after = None
    if retry_after is not None and retry_after > delay:
        delay = retry_after
    return min(delay, cap)


class FormatWithFallback(dict):
    """A response format that carries the one to use if the provider rejects it. It is a plain dict on the wire; `complete` reads `.fallback` when a provider answers 400
    about response_format, retries with it, and records on `.used` which format actually ran ("primary", "fallback" or "none")."""

    def __init__(self, fmt: dict, fallback: dict | None):
        super().__init__(fmt)
        self.fallback = fallback
        self.used = "primary"


_THINK_TAG_RE = re.compile(r"<think>(.*?)</think>", re.IGNORECASE | re.DOTALL)


def split_inline_thinking(text: str) -> tuple[str | None, str]:
    """Some providers emit their reasoning as a <think>...</think> block inline in the completion text. Strip it out and return it, so callers never parse the block as if it
    were JSON. Returns (reasoning_or_None, text_with_block_removed); the second value is always safe to use.
    """
    if not text or "<think" not in text.lower():
        return None, text
    match = _THINK_TAG_RE.search(text)
    if not match:
        return None, text
    reasoning = match.group(1).strip()
    remainder = (text[:match.start()] + text[match.end():]).strip()
    return (reasoning or None), remainder


def extract_native_reasoning(response) -> str | None:
    """Best-effort read of the provider's native reasoning trace off a response object. The field name differs per provider; the first non-empty string wins, and an inline
    <think> block in `response.content` is checked last. Returns None (never an empty string) when nothing is present.
    """
    kwargs = getattr(response, "additional_kwargs", None) or {}
    meta   = getattr(response, "response_metadata", None) or {}
    for source in (kwargs, meta):
        for key in ("reasoning", "reasoning_content", "reasoning_details"):
            val = source.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
            if isinstance(val, list) and val:
                # reasoning_details can be a list of blocks (e.g. signed Claude
                # thinking blocks) — join any plain-text pieces, skip opaque ones.
                texts = [b.get("text", "") for b in val if isinstance(b, dict) and b.get("text")]
                if texts:
                    return "\n".join(texts).strip()
    content = getattr(response, "content", None)
    if isinstance(content, str):
        inline, _ = split_inline_thinking(content)
        if inline:
            return inline
    return None


class RawCompletionResult:
    """Minimal stand-in for a chat-library message: content, the provider's reasoning text, and the response metadata (token usage, id, model, finish reason)."""
    def __init__(self, content: str, reasoning: str | None, response_metadata: dict):
        self.content = content
        self.additional_kwargs = {"reasoning": reasoning} if reasoning else {}
        self.response_metadata = response_metadata
        self.usage_metadata = None  # token usage is read from response_metadata.token_usage

def _rejects_response_format_text(res) -> bool:
    """A 400 whose body is about the structured-output request (response_format / json_schema), not any other bad request."""
    try:
        text = res.text.lower()
    except Exception:
        return False
    return any(marker in text for marker in ("response_format", "json_schema", "structured output", "structured_output"))
