"""Survey estimates: Wilson CI for proportions, NPS with bootstrap CI, raking weights with Kish design effect."""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import norm
from .result import Stat, insufficient, percentile_ci

NPS_MIN_N = 5


def wilson_ci(successes: int, n: int, level: float = 0.95) -> Stat:
    if n == 0:
        return insufficient("wilson_ci", 0, 1)
    z = norm.ppf(1 - (1 - level) / 2); p = successes / n
    den = 1 + z ** 2 / n
    c = (p + z ** 2 / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / den
    return Stat(round(p, 6), (float(c - h), float(c + h)), n, "Wilson score interval")


def nps(scores, n_boot: int = 2000, seed: int = 7, weights=None) -> Stat:
    s = np.asarray(scores, float); m = ~np.isnan(s); s = s[m]
    w = np.ones_like(s) if weights is None else np.asarray(weights, float)[m]
    if len(s) < NPS_MIN_N:
        return insufficient("nps", len(s), NPS_MIN_N)

    def val(x, ww):
        return float(100 * (ww[x >= 9].sum() - ww[x <= 6].sum()) / ww.sum())
    rng = np.random.default_rng(seed)
    idx = [rng.integers(0, len(s), len(s)) for _ in range(n_boot)]
    boots = [val(s[i], w[i]) for i in idx]
    return Stat(round(val(s, w), 2), percentile_ci(boots), len(s), f"NPS, bootstrap percentile CI ({n_boot}, seed {seed})" + (", weighted" if weights is not None else ""))


def rake(df: pd.DataFrame, margins: dict[str, dict], max_iter: int = 100, tol: float = 1e-8) -> Stat:
    """Iterative proportional fitting to population margins {var: {level: share}}; returns weights mean 1."""
    w = np.ones(len(df))
    for it in range(max_iter):
        mx = 0.0
        for var, target in margins.items():
            for lvl, share in target.items():
                mask = (df[var] == lvl).to_numpy()
                cur = w[mask].sum() / w.sum()
                if cur == 0:
                    return Stat(None, None, len(df), "raking", [f"no respondents in {var}={lvl}"], True)
                f = share / cur; w[mask] *= f; mx = max(mx, abs(f - 1))
        if mx < tol:
            break
    w = w / w.mean()
    deff = float(len(w) * (w ** 2).sum() / w.sum() ** 2)
    warn = [f"design effect {deff:.2f} (> 2): weighted estimates are much less precise"] if deff > 2 else []
    return Stat(w, None, len(df), f"raking (IPF), {it+1} iterations", warn, detail={"design_effect": deff, "effective_n": len(w) / deff})
