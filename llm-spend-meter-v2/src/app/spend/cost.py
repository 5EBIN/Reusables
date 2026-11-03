"""
app/billing/cost.py
Cost engine — FALLBACK only (used when OpenRouter /api/v1/generation is unavailable).

Pricing source priority:
  1. OpenRouter /api/v1/generation  — exact cost charged (exact_cost.py, primary path)
  2. OpenRouter /api/v1/models      — live per-token rates (this module, fallback)
  3. flag_zero                      — unknown model, bills $0 + flagged=True

Invariants:
  I1  Real OpenRouter rates are the ONLY pricing source (no hardcoded tables,
      no litellm model_cost — that was replaced with openrouter_pricing.py).
  I2  Unknown model NEVER bills at another model's price.
      UNKNOWN_MODEL_POLICY applies; default is flag_zero.
"""
from __future__ import annotations
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

# Policy for models absent from the OpenRouter pricing cache.
#   "flag_zero"    — bill $0, mark flagged=True (default)
#   "flag_block"   — raise ValueError, refuse the request
UNKNOWN_MODEL_POLICY: str = "flag_zero"


async def compute_cost_cents_async(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    markup_multiplier: float,
) -> tuple[Decimal, bool]:
    """
    Async version — looks up live OpenRouter pricing.
    Returns (billed_cents, flagged).
    flagged=True when the model is unknown; cost is $0 in that case.

    This is the FALLBACK. Primary path is OpenRouter /api/v1/generation
    which returns the exact cost for the specific request (see exact_cost.py).
    """
    from app.spend.pricing import get_model_price_usd

    prompt_rate, completion_rate = await get_model_price_usd(model)

    if prompt_rate is None or completion_rate is None:
        logger.warning(
            "[spend/fallback] model %r not in OpenRouter price cache — applying policy=%s",
            model, UNKNOWN_MODEL_POLICY,
        )
        if UNKNOWN_MODEL_POLICY == "flag_block":
            raise ValueError(
                f"Unpriced model {model!r} — refusing to bill blind. "
                "Check that it's a valid OpenRouter model ID."
            )
        return Decimal(0), True  # flag_zero

    raw_usd = (
        Decimal(str(prompt_rate)) * prompt_tokens
        + Decimal(str(completion_rate)) * completion_tokens
    )
    billed_usd = raw_usd * Decimal(str(markup_multiplier))
    # Keep as Decimal — converting to float here loses IEEE 754 precision on
    # sub-cent values (e.g. $0.000137 × 100 = 0.0137¢).  SQLAlchemy maps
    # Decimal directly to NUMERIC(18,8) without any float coercion.
    billed_cents = billed_usd * 100
    logger.debug(
        "[spend/fallback] model=%s tokens=%d+%d rates=(%.8f, %.8f) cost=%s¢",
        model, prompt_tokens, completion_tokens,
        prompt_rate, completion_rate, billed_cents,
    )
    return billed_cents, False


def compute_cost_cents(
    model: str,
    prompt_tokens: int,  # noqa: ARG001
    completion_tokens: int,  # noqa: ARG001
    markup_multiplier: float,  # noqa: ARG001
    custom_llm_provider: str | None = None,  # noqa: ARG001
) -> tuple[int, bool]:
    """
    Sync shim kept for any remaining call sites that can't await.
    Bills $0 + flagged=True — callers should migrate to compute_cost_cents_async.
    """
    logger.warning(
        "[spend] sync compute_cost_cents called for model=%s — "
        "returning flag_zero. Migrate to compute_cost_cents_async.",
        model,
    )
    return 0, True
