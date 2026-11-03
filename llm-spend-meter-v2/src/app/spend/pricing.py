"""
app/spend/pricing.py
Periodic pricing cache backed by OpenRouter's /api/v1/models endpoint.

OpenRouter returns per-token USD pricing for every model it supports.
We cache it in memory and refresh every REFRESH_HOURS hours so our
fallback cost path always uses real rates — not a stale static table.

Usage:
    from app.spend.pricing import get_model_price_usd

    prompt_usd, completion_usd = await get_model_price_usd("vendor/model-name")
    # Returns (price_per_prompt_token, price_per_completion_token) in USD.
    # Returns (None, None) if the model is unknown or the cache is empty.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import NamedTuple

import httpx


logger = logging.getLogger(__name__)
class _LazySettings:
    # reads the host's settings on first use, so importing this module never needs them

    def __getattr__(self, name):
        from app._stubs import get_settings
        return getattr(get_settings(), name)


settings = _LazySettings()

# How often to refresh the price table from OpenRouter (seconds)
REFRESH_HOURS: float = 6
REFRESH_SECONDS: float = REFRESH_HOURS * 3600

# In-memory cache: model_id → (prompt_usd_per_token, completion_usd_per_token)
_price_cache: dict[str, tuple[float, float]] = {}
_last_fetched: float = 0.0          # epoch seconds
_fetch_lock = asyncio.Lock()


class ModelPrice(NamedTuple):
    prompt_per_token: float      # USD
    completion_per_token: float  # USD


async def _fetch_prices() -> dict[str, tuple[float, float]]:
    """
    Call GET /api/v1/models, parse pricing.prompt / pricing.completion.
    Returns {model_id: (prompt_usd_per_token, completion_usd_per_token)}.
    """
    api_key = settings.openrouter_api_key
    url = f"{settings.openrouter_base_url}/models"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.get(url, headers=headers)
        res.raise_for_status()
        data = res.json()

    prices: dict[str, tuple[float, float]] = {}
    for model in data.get("data", []):
        model_id: str = model.get("id", "")
        pricing = model.get("pricing") or {}
        try:
            prompt_usd = float(pricing.get("prompt") or 0)
            completion_usd = float(pricing.get("completion") or 0)
            prices[model_id] = (prompt_usd, completion_usd)
        except (TypeError, ValueError):
            continue

    logger.info("[pricing] fetched prices for %d models (%d with reasoning capabilities)", len(prices), len(reasoning))
    return prices


async def _ensure_cache_fresh() -> None:
    """Refresh the price cache if it's stale or empty."""
    global _price_cache, _last_fetched

    now = time.monotonic()
    if _price_cache and (now - _last_fetched) < REFRESH_SECONDS:
        return  # still fresh

    async with _fetch_lock:
        # Double-check inside lock
        now = time.monotonic()
        if _price_cache and (now - _last_fetched) < REFRESH_SECONDS:
            return

        try:
            _price_cache = await _fetch_prices()
            _last_fetched = now
        except Exception as exc:
            logger.warning(
                "[pricing] price refresh failed (keeping old cache): %s", exc
            )
            if not _price_cache:
                logger.error("[pricing] no cached prices available — fallback will flag_zero")


async def get_model_price_usd(model_id: str) -> tuple[float, float] | tuple[None, None]:
    """
    Return (prompt_usd_per_token, completion_usd_per_token) for a model.
    Returns (None, None) if the model is unknown.

    Tries the exact model_id first, then strips common suffixes (:free, :nitro,
    :extended, :floor) to find the base model price.
    """
    await _ensure_cache_fresh()

    # 1. Exact match
    if model_id in _price_cache:
        return _price_cache[model_id]

    # 2. :free models are always $0 — never fall through to the paid base rate (B8)
    if model_id.endswith(":free"):
        return (0.0, 0.0)

    # 3. Strip other variant suffixes and retry
    for suffix in (":nitro", ":extended", ":floor", ":beta"):
        if model_id.endswith(suffix):
            base = model_id[: -len(suffix)]
            if base in _price_cache:
                return _price_cache[base]

    # 3. Case-insensitive search (rare but some models have mixed casing)
    lower = model_id.lower()
    for key, val in _price_cache.items():
        if key.lower() == lower:
            return val

    logger.debug("[pricing] model %r not in price cache", model_id)
    return None, None


async def warm_cache() -> None:
    """Pre-warm the cache at startup — call from app lifespan."""
    try:
        await _ensure_cache_fresh()
    except Exception as exc:
        logger.warning("[pricing] warm_cache failed: %s", exc)
