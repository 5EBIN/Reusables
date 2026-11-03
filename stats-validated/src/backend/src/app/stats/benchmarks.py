"""Percentile benchmarks from an opt-in normative pool. Never exposes a single organisation's value."""
from __future__ import annotations
import numpy as np
from scipy.stats import percentileofscore
from .result import Stat, insufficient

POOL_MIN_ORGS = 10


def percentile_rank(value: float, pool: list[float]) -> Stat:
    pool = [float(v) for v in pool if v is not None and not np.isnan(v)]
    if len(pool) < POOL_MIN_ORGS:
        return insufficient("percentile_rank", len(pool), POOL_MIN_ORGS, "organisations in the benchmark pool")
    pr = percentileofscore(pool, value, kind="mean")
    q = np.quantile(pool, [0.25, 0.5, 0.75])
    return Stat(round(float(pr), 1), None, len(pool), "percentile rank within opt-in pool (mean rank for ties)",
                detail={"pool_quartiles": [round(float(x), 2) for x in q]})
