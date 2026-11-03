"""Exact cost of one finished request, from the provider's generation record (the price cache is the fallback)."""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

class _LazySettings:
    # reads the host's settings on first use, so importing this module never needs them

    def __getattr__(self, name):
        from app._stubs import get_settings
        return getattr(get_settings(), name)


settings = _LazySettings()


async def _fetch_openrouter_cost_usd(generation_id: str) -> float | None:
    """
    Call GET /api/v1/generation?id={generation_id} to get the exact cost
    OpenRouter charged for this request (in USD).

    OpenRouter indexes generation records asynchronously; they can take several
    seconds to appear. We retry up to 4 times with exponential backoff
    (2s → 4s → 6s → 8s) before giving up and falling back to the price cache.

    Returns total_cost as a float (USD) or None on any failure.
    """
    import httpx

    api_key = settings.openrouter_api_key
    if not api_key:
        logger.debug("[meter] the provider API key is not set — skipping exact-cost fetch")
        return None

    url = f"{settings.openrouter_base_url}/generation"
    headers = {"Authorization": f"Bearer {api_key}"}

    delays = [2.0, 4.0, 6.0, 8.0]  # waits between retries (seconds)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for attempt, wait in enumerate(delays, start=1):
                res = await client.get(url, params={"id": generation_id}, headers=headers)

                if res.status_code == 200:
                    data = res.json()
                    cost_usd = data.get("data", {}).get("total_cost")
                    if cost_usd is not None:
                        logger.info(
                            "[exact_cost] gen=%s → total_cost=%.8f USD (attempt %d)",
                            generation_id, cost_usd, attempt,
                        )
                        return float(cost_usd)
                    logger.warning(
                        "[exact_cost] gen=%s response has no total_cost field: %s",
                        generation_id, data,
                    )
                    return None  # 200 but no cost — don't retry

                if res.status_code == 404:
                    if attempt < len(delays):
                        logger.debug(
                            "[exact_cost] gen=%s not indexed yet (attempt %d/%d), retrying in %.0fs",
                            generation_id, attempt, len(delays), wait,
                        )
                        await asyncio.sleep(wait)
                        continue
                    else:
                        logger.warning(
                            "[exact_cost] gen=%s still 404 after %d attempts — falling back to price cache",
                            generation_id, len(delays),
                        )
                else:
                    logger.warning(
                        "[exact_cost] gen=%s → HTTP %d — falling back to price cache",
                        generation_id, res.status_code,
                    )
                    break  # non-404 error, don't retry

    except Exception as exc:
        logger.warning("[exact_cost] openrouter generation API error: %s — falling back to price cache", exc)

    return None
