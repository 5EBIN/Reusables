"""What protects the product and the bill when a model provider misbehaves: a circuit breaker per model and a process-wide limit on calls in flight."""
import asyncio
import time
from collections.abc import Callable

FAILURES_TO_OPEN = 5
OPEN_SECONDS = 60.0


class CircuitBreaker:
    """Closed until FAILURES_TO_OPEN consecutive failures; then open for OPEN_SECONDS, during which `allow()` is False so callers go straight to their fallback.
    After the pause one probe request is let through: if it succeeds the breaker closes, if it fails it opens again."""

    def __init__(self, clock: Callable[[], float] = time.monotonic, failures: int = FAILURES_TO_OPEN, pause: float = OPEN_SECONDS):
        self.clock, self.threshold, self.pause = clock, failures, pause
        self.consecutive, self.opened_at, self.probing = 0, None, False

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        return "half_open" if self.clock() - self.opened_at >= self.pause else "open"

    def allow(self) -> bool:
        st = self.state
        if st == "closed":
            return True
        if st == "half_open" and not self.probing:
            self.probing = True                              # exactly one probe at a time
            return True
        return False

    def success(self) -> None:
        self.consecutive, self.opened_at, self.probing = 0, None, False

    def failure(self) -> None:
        self.consecutive += 1
        self.probing = False
        if self.consecutive >= self.threshold or self.opened_at is not None:
            self.opened_at = self.clock()


class AiGate:
    """One per process: the semaphore that caps model calls in flight (AI_MAX_CONCURRENCY) and the breaker of each model."""

    def __init__(self, max_concurrency: int = 4, clock: Callable[[], float] = time.monotonic):
        self.semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self.clock = clock
        self._breakers: dict[str, CircuitBreaker] = {}

    def breaker(self, model: str) -> CircuitBreaker:
        return self._breakers.setdefault(model, CircuitBreaker(self.clock))
