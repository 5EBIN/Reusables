"""Change between rounds: Hedges' g with bootstrap CI, paired test, reliable change, regression-to-the-mean flag."""
from __future__ import annotations
import numpy as np
from scipy import stats as st
from .result import Stat, insufficient, percentile_ci

MIN_N = 20


def hedges_g(a, b, n_boot: int = 1000, seed: int = 7) -> Stat:
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if min(len(a), len(b)) < MIN_N:
        return insufficient("hedges_g", min(len(a), len(b)), MIN_N, "responses per round")

    def g(x, y):
        n1, n2 = len(x), len(y)
        sp = np.sqrt(((n1 - 1) * x.var(ddof=1) + (n2 - 1) * y.var(ddof=1)) / (n1 + n2 - 2))
        j = 1 - 3 / (4 * (n1 + n2) - 9)
        return float(j * (y.mean() - x.mean()) / sp)
    rng = np.random.default_rng(seed)
    boots = [g(rng.choice(a, len(a)), rng.choice(b, len(b))) for _ in range(n_boot)]
    t = st.ttest_ind(b, a, equal_var=False)
    return Stat(round(g(a, b), 4), percentile_ci(boots), len(a) + len(b), "Hedges' g (later minus earlier), Welch t-test",
                detail={"mean_diff": float(b.mean() - a.mean()), "welch_p": float(t.pvalue)})


def paired_change(before, after) -> Stat:
    x, y = np.asarray(before, float), np.asarray(after, float)
    m = ~(np.isnan(x) | np.isnan(y)); x, y = x[m], y[m]
    if len(x) < MIN_N:
        return insufficient("paired_change", len(x), MIN_N, "matched respondents")
    d = y - x
    dz = float(d.mean() / d.std(ddof=1))
    t = st.ttest_rel(y, x)
    return Stat(round(float(d.mean()), 4), tuple(map(float, t.confidence_interval())), len(x), "paired t-test; effect size d_z",
                detail={"d_z": round(dz, 4), "p": float(t.pvalue)})


def reliable_change_threshold(sd_baseline: float, reliability: float) -> float:
    """Jacobson & Truax (1991): an individual change larger than this is unlikely to be measurement noise (95%)."""
    se_diff = np.sqrt(2) * sd_baseline * np.sqrt(1 - reliability)
    return float(1.96 * se_diff)


def regression_to_mean_flags(team_scores_before: dict, decile: float = 0.10) -> set:
    """Teams in the lowest decile at baseline: expect some improvement from regression to the mean alone."""
    if not team_scores_before:
        return set()
    cut = np.quantile(list(team_scores_before.values()), decile)
    return {k for k, v in team_scores_before.items() if v <= cut}
