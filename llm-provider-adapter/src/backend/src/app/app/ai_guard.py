"""The gate in front of every model call, and the meter behind it.

gate(c): the per-minute rate limits (429), the organisation's `llm` switch (403 when off), optionally the plan's credits, then the two daily caps (tokens and USD): 429 BEFORE any call is made.
metered(pool, org_id): collects the provider's answers inside the block and records their real usage (tokens, cost, the model that answered, the generation id) in its own
transaction, so the spend is kept even when the route fails afterwards."""
import json
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import HTTPException

from app.adapters.llm_tasks import CallResult, _status, collect_results
from app.app.settings import ai_settings
from app.core.obs import hash_ref
from app.db import tenant_tx
from app.db.repos import ai_budget as repo

log = logging.getLogger("app.ai")
DEFAULT_TOKEN_CAP = 200_000          # the column default; used when the organisation has no settings row


async def check_caps(c) -> None:
    env, caps, used = ai_settings(), await repo.caps(c), await repo.used_today(c)
    token_cap = min(x for x in (caps.tokens or DEFAULT_TOKEN_CAP, env.daily_token_cap) if x is not None)
    usd_cap = min((x for x in (caps.usd, env.daily_usd_cap) if x is not None), default=None)
    if used.tokens >= token_cap:
        raise HTTPException(429, "daily AI budget reached (tokens); AI features resume tomorrow")
    if usd_cap is not None and used.usd >= usd_cap:
        raise HTTPException(429, "daily AI budget reached (spend); AI features resume tomorrow")


async def rate_limit(o) -> None:
    """Per minute, per user and per organisation, for every request that can start model work (429 with `retry_after`, the window in seconds). A request that only
    enqueues a job counts once, here; the job itself runs later without a request and is not counted again."""
    cont = o.request.app.state.container
    for limiter, key in ((cont.ai_limiter, f"ai-user:{o.user_id}"), (cont.ai_org_limiter, f"ai-org:{o.org_id}")):
        if not await limiter.hit(key):
            wait = int(limiter.window)
            raise HTTPException(429, {"code": "ai_rate_limited", "retry_after": wait}, headers={"Retry-After": str(wait)})


async def gate(c, o=None, *, credits: bool = False, caps: bool = True) -> None:
    """`o` is the request's OrgCtx: every route passes it (a test scans for that). Background jobs have no request and pass nothing."""
    from app.app.billing import require
    from app.app.routers.privacy import processor_on
    if o is not None:
        await rate_limit(o)
    await processor_on(c, "llm")
    if caps:
        await check_caps(c)                  # the organisation's daily limits come first (429); the plan's credits (402) after
    if credits:
        await require(c, "credits")


async def spend(pool, org_id: str, results: list[CallResult]) -> None:
    if not results:
        return
    async with tenant_tx(pool, None, org_id) as c:
        await spend_on(c, org_id, results)


def log_call(org_id: str, r: CallResult) -> None:
    """One line per model answer: what it cost and how it went, with the request id (empty for a background job) and the hashed organisation id (the same as the access log's),
    so a cost spike can be traced to a request. Never any text, id of a respondent or key."""
    u = r.usage
    log.info(json.dumps({"rid": (_status.get().rid if _status.get() else ""), "org": hash_ref(org_id), "task": r.task, "model": r.model, "provider": r.provider, "gen": r.generation_id,
                         "prompt_tokens": u.get("prompt_tokens") or 0, "completion_tokens": u.get("completion_tokens") or 0, "reasoning_tokens": u.get("reasoning_tokens"),
                         "cost_usd": u.get("cost"), "ms": r.latency_ms, "attempt": r.attempt, "reasked": r.reasked, "breaker": r.breaker}))


async def spend_on(c, org_id: str, results: list[CallResult]) -> None:
    """Record the answers on a connection that is already inside the organisation's transaction (background jobs, which have no pool)."""
    for r in results:
        log_call(org_id, r)
        u = r.usage
        await repo.record_call(c, uuid.UUID(org_id), r.task, r.model, r.generation_id, u.get("prompt_tokens") or 0, u.get("completion_tokens") or 0, u.get("cost"), r.attempt, r.reasked, r.provider)


@asynccontextmanager
async def metered_on(c, org_id: str):
    with collect_results() as got:
        try:
            yield got
        finally:
            await spend_on(c, org_id, got)


@asynccontextmanager
async def metered(pool, org_id: str):
    with collect_results() as got:
        try:
            yield got
        finally:
            await spend(pool, org_id, got)
