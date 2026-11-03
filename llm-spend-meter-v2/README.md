# llm-spend-meter-v2

**Category:** backend-helpers  
**Origin:** extracted from a production Next.js/FastAPI app.

**Variant of:** `llm-provider-adapter` (existing module). **How it differs:** its guard enforces per-organisation daily token/USD caps in the database; this one prices each request exactly and bounds ownerless spend in a rolling window.

## What it does
Exact per-request cost from the provider's generation record with a price-cache fallback (unknown model bills $0 and is flagged, never another model's price), a rolling-window budget, a spend-cap exception with scopes, and jittered backoff.

## Problem it solved
Token-price tables go stale and unknown models were silently mis-billed.

## Public interface
* `app/spend/caps.py`: `class RunSpendCapExceeded`
* `app/spend/caps.py`: `class SystemBudget`
* `app/spend/cost.py`: `async def compute_cost_cents_async(model: str, prompt_tokens: int, completion_tokens: int, markup_multiplier: float) -> tuple[Decimal, bool]`
* `app/spend/cost.py`: `def compute_cost_cents(model: str, prompt_tokens: int, completion_tokens: int, markup_multiplier: float, custom_llm_provider: str | None=None) -> tuple[int, bool]`
* `app/spend/pricing.py`: `class ModelPrice`
* `app/spend/pricing.py`: `async def get_model_price_usd(model_id: str) -> tuple[float, float] | tuple[None, None]`
* `app/spend/pricing.py`: `async def warm_cache() -> None`

## Dependencies
Python (`deps.txt`): `httpx>=0.27`

## Stubs and what the host must provide
`src/app/_stubs.py` / `src/_stubs.ts` keep imports resolvable. The host must replace: `get_settings`.

## Known limits
Per-run and per-user caps need host storage; this module supplies the exception, the window budget and the price/cost lookups. Markup and overrides are the host's.

## Quality
B (1 test copied; pure parts only)  
Tests copied: 1 (copied from the source, not run here).

## How to reuse
`compute_cost_cents_async(model, p, c, markup)`, `SystemBudget().check()`.

(Stub signatures were derived from the host code they stand for; they carry no behaviour.)
