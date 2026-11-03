"""LLMClient on the Anthropic Messages API. The model only ever returns JSON that is validated downstream by deterministic code.

Request rules for claude-opus-5-5 (skill-verified): no temperature/top_p/top_k (400), no assistant prefill, no forced tool_choice,
thinking left at its default (always on; depth via output_config.effort), structured output via output_config.format, and the
server-side refusal fallback opted in. Determinism comes from validation, not sampling: every field below is checked by code
(QueryPlan, verifier, evidence checks) before anything is shown or executed.
"""
import json
import time
from typing import Any

from app.adapters.llm_tasks import SCHEMAS, SYSTEM, CallInfo, LLMBadOutput, LLMRefused, LLMTasks, _wrap

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicLLM(LLMTasks):
    def __init__(self, client: Any = None, model: str = DEFAULT_MODEL, effort: str = "medium", max_tokens: int = 16000, fallbacks: bool = True,
                 base_url: str | None = None):
        if client is None:
            import anthropic                                  # imported lazily: the SDK is optional until LLM_PROVIDER=anthropic
            client = anthropic.AsyncAnthropic(base_url=base_url or None)    # key from the environment, never from code; base_url None = the SDK default
        self.client, self.model, self.effort, self.max_tokens, self.fallbacks = client, model, effort, max_tokens, fallbacks

    async def _send(self, instruction: str, payload: str, schema_key: str) -> tuple[Any, CallInfo]:
        kw: dict[str, Any] = {"model": self.model, "max_tokens": self.max_tokens, "system": SYSTEM,
                              "output_config": {"effort": self.effort, "format": {"type": "json_schema", "schema": SCHEMAS[schema_key]}},
                              "messages": [{"role": "user", "content": f"{instruction}\n\n{_wrap(payload)}"}]}
        t0 = time.perf_counter()
        if self.fallbacks:
            r = await self.client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **kw)
        else:
            r = await self.client.messages.create(**kw)
        u = getattr(r, "usage", None)
        pt, ct = (getattr(u, "input_tokens", 0) or 0, getattr(u, "output_tokens", 0) or 0) if u is not None else (0, 0)
        info = CallInfo(model=getattr(r, "model", None) or self.model, task=schema_key, generation_id=getattr(r, "id", None), latency_ms=round((time.perf_counter() - t0) * 1000, 1),
                        usage={"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct, "cost": None})
        if r.stop_reason == "refusal":
            raise LLMRefused(getattr(getattr(r, "stop_details", None), "category", None) or "refusal")
        if r.stop_reason == "max_tokens":
            raise LLMBadOutput("truncated")
        text = next((b.text for b in r.content if getattr(b, "type", "") == "text"), None)
        if text is None:
            raise LLMBadOutput("no text block")
        try:
            return json.loads(text), info
        except ValueError:
            raise LLMBadOutput("not json") from None
