"""Cronbach's alpha (with bootstrap CI, alpha-if-deleted, item-total r) and McDonald's omega."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .result import Stat, insufficient, percentile_ci

ALPHA_MIN_N = 30
OMEGA_MIN_N = 100


def _alpha_from_cov(c: np.ndarray) -> float:
    k = c.shape[0]
    return float(k / (k - 1) * (1 - np.trace(c) / c.sum()))


def _cov(df: pd.DataFrame, missing: str) -> np.ndarray:
    if missing == "complete":
        return np.cov(df.dropna().to_numpy(float), rowvar=False)
    return df.cov(min_periods=2).to_numpy(float)          # pairwise (same as psych::alpha default)


def reverse(df: pd.DataFrame, items, lo: float, hi: float) -> pd.DataFrame:
    out = df.copy()
    for c in items:
        out[c] = lo + hi - out[c]
    return out


def cronbach_alpha(items: pd.DataFrame, missing: str = "pairwise", n_boot: int = 1000, seed: int = 7) -> Stat:
    items = items.astype(float)
    n = int(items.dropna(how="all").shape[0])
    if items.shape[1] < 2:
        return Stat(None, None, n, "cronbach_alpha", ["need at least 2 items"], True)
    if n < ALPHA_MIN_N:
        return insufficient("cronbach_alpha", n, ALPHA_MIN_N)
    a = _alpha_from_cov(_cov(items, missing))
    rng = np.random.default_rng(seed)
    x = items.to_numpy(float)
    boots = []
    for _ in range(n_boot):
        s = pd.DataFrame(x[rng.integers(0, len(x), len(x))], columns=items.columns)
        boots.append(_alpha_from_cov(_cov(s, missing)))
    if_deleted = {c: _alpha_from_cov(_cov(items.drop(columns=c), missing)) for c in items.columns} if items.shape[1] > 2 else {}
    total = items.sum(axis=1, min_count=1)
    item_total = {c: float(items[c].corr(total - items[c].fillna(0))) for c in items.columns}
    warn = [f"alpha {a:.2f} below 0.70"] if a < 0.70 else []
    return Stat(round(a, 4), percentile_ci(boots), n, f"cronbach_alpha ({missing}, bootstrap {n_boot}, seed {seed})", warn,
                detail={"alpha_if_deleted": if_deleted, "corrected_item_total": item_total})


def omega_total(items: pd.DataFrame) -> Stat:
    """McDonald's omega (total) from a one-factor CFA (ML, semopy): (sum l)^2 / ((sum l)^2 + sum theta)."""
    import semopy
    d = items.astype(float).dropna()
    n = len(d)
    if n < OMEGA_MIN_N:
        return insufficient("omega_total", n, OMEGA_MIN_N)
    cols = [f"i{j}" for j in range(d.shape[1])]
    d.columns = cols
    m = semopy.Model("f =~ " + " + ".join(cols))
    m.fit(d)
    est = m.inspect(std_est=True)
    lam = est[(est["op"] == "~") & (est["rval"] == "f")].set_index("lval")["Est. Std"].reindex(cols).to_numpy(float)
    theta = 1 - lam ** 2                                    # standardised residual variances
    om = float(lam.sum() ** 2 / (lam.sum() ** 2 + theta.sum()))
    warn = ["one-factor model: some standardised loadings < 0.40"] if (np.abs(lam) < 0.40).any() else []
    return Stat(round(om, 4), None, n, "omega_total (one-factor CFA, ML, standardised, complete cases)", warn,
                detail={"loadings": dict(zip(items.columns, map(float, lam)))})
