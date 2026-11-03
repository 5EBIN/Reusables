from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Stat:
    value: Any = None
    ci: tuple[float, float] | None = None
    n: int = 0
    method: str = ""
    warnings: list[str] = field(default_factory=list)
    insufficient: bool = False
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def insufficient(method: str, n: int, need: int, what: str = "responses") -> Stat:
    return Stat(None, None, n, method, [f"insufficient n: {n} {what}, need at least {need}"], True)


def percentile_ci(samples, level: float = 0.95) -> tuple[float, float]:
    import numpy as np
    a = (1 - level) / 2
    lo, hi = np.nanquantile(np.asarray(samples, float), [a, 1 - a])
    return float(lo), float(hi)
