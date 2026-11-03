"""Spend caps: a rolling-window budget for calls that belong to no owner, the exception every layer catches, and a backoff helper."""
from __future__ import annotations

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)
_METERED_RETRY_DELAYS = [2.0, 4.0]


def _retry_delay(attempt: int, exc: Exception | None = None) -> float:
    """/equal-jitter backoff in [base/2, base] (so concurrent projects do not retry in lockstep), raised to the server's
    Retry-After (seconds) when it sent one, and never above settings.llm_retry_max_delay_s."""
    import random
    from app._stubs import get_settings
    cap = get_settings().llm_retry_max_delay_s
    base = _METERED_RETRY_DELAYS[min(attempt, len(_METERED_RETRY_DELAYS)) - 1]
    delay = random.uniform(base / 2, base)
    headers = getattr(getattr(exc, "response", None), "headers", None)
    try:
        retry_after = float(headers.get("retry-after")) if headers is not None and headers.get("retry-after") else None
    except (TypeError, ValueError):
        retry_after = None
    if retry_after is not None and retry_after > delay:
        delay = retry_after
    return min(delay, cap)


class RunSpendCapExceeded(RuntimeError):
    """A spend cap stopped an LLM call. `scope` says which one: "run" (the run's cumulative billed cost reached
    the run cap; the run was paused), "pre_run" (an owner that has not started a run reached
    the pre-run cap) or "system" (the shared budget of calls that belong to no owner). The one type every layer catches;
    the host maps it to client-facing errors."""

    SCOPES = ("pre_run", "run", "system", "user")

    def __init__(self, message: str = "", scope: str = "run"):
        if scope not in self.SCOPES:
            raise ValueError(f"unknown spend cap scope {scope!r}")
        super().__init__(message)
        self.scope = scope


class SystemBudget:
    """the spend of LLM calls that belong to no owner (background helpers): a rolling window, in this
    process, with its own cap (the system cap over the system window). Never persisted: a restart
    resets it, which is the safe direction for a guard that exists to stop a runaway loop."""

    def __init__(self):
        self._entries: list[tuple[float, Decimal]] = []

    def _prune(self, now: float, window: float) -> None:
        self._entries = [(t, c) for t, c in self._entries if now - t < window]

    def add(self, cents) -> None:
        import time
        self._entries.append((time.monotonic(), Decimal(str(cents))))

    def spent(self) -> Decimal:
        import time
        from app._stubs import get_settings
        self._prune(time.monotonic(), get_settings().system_spend_window_s)
        return sum((c for _, c in self._entries), Decimal("0"))

    def check(self) -> None:
        from app._stubs import get_settings
        cap = get_settings().system_spend_cap_cents
        if cap <= 0:
            return
        spent = self.spent()
        if spent >= Decimal(str(cap)):
            logger.warning("[spend] system LLM budget exhausted: %s of %s cents", spent, cap)
            raise RunSpendCapExceeded(f"system LLM spend cap of {cap:.0f} cents reached", scope="system")

    def reset(self) -> None:
        self._entries = []


SYSTEM_BUDGET = SystemBudget()
