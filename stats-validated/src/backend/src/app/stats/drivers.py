"""Key-driver analysis: Johnson's relative weights and dominance analysis, with bootstrap CIs and rank stability."""
from __future__ import annotations
from itertools import combinations
import numpy as np
import pandas as pd
from .result import Stat, insufficient, percentile_ci

RW_MIN_N, DA_MAX_P = 100, 12


def _r2(R, y_idx, X_idx):
    if not X_idx:
        return 0.0
    rxx = R[np.ix_(X_idx, X_idx)]; rxy = R[X_idx, y_idx]
    return float(rxy @ np.linalg.solve(rxx, rxy))


def _relative_weights(R, p):
    rxx, rxy = R[:p, :p], R[:p, p]
    ev, V = np.linalg.eigh(rxx)
    lam = V @ np.diag(np.sqrt(np.clip(ev, 0, None))) @ V.T
    beta = np.linalg.solve(lam, rxy)
    return (lam ** 2) @ (beta ** 2)


def _general_dominance(R, p):
    gd = np.zeros(p)
    for i in range(p):
        others = [j for j in range(p) if j != i]
        tot = 0.0
        for k in range(p):
            inc = [_r2(R, p, list(s) + [i]) - _r2(R, p, list(s)) for s in combinations(others, k)]
            tot += np.mean(inc)
        gd[i] = tot / p
    return gd


def drivers(df: pd.DataFrame, outcome: str, predictors: list[str], method: str = "relative_weights",
            n_boot: int = 500, seed: int = 7) -> Stat:
    d = df[predictors + [outcome]].astype(float).dropna()
    n, p = len(d), len(predictors)
    if n < RW_MIN_N:
        return insufficient(f"drivers/{method}", n, RW_MIN_N)
    if method == "dominance" and p > DA_MAX_P:
        return Stat(None, None, n, "dominance", [f"dominance analysis limited to {DA_MAX_P} predictors"], True)
    fn = _relative_weights if method == "relative_weights" else _general_dominance
    x = d.to_numpy()
    w = fn(np.corrcoef(x, rowvar=False), p)
    rng = np.random.default_rng(seed)
    boots, ranks = [], []
    for _ in range(n_boot):
        s = x[rng.integers(0, n, n)]
        b = fn(np.corrcoef(s, rowvar=False), p)
        boots.append(b); ranks.append(np.argsort(np.argsort(-b)))
    boots, ranks = np.array(boots), np.array(ranks)
    base_rank = np.argsort(np.argsort(-w))
    r2 = float(w.sum())
    out = {}
    for i, c in enumerate(predictors):
        out[c] = {"weight": round(float(w[i]), 4), "share_of_r2": round(float(w[i] / r2), 4) if r2 else None,
                  "ci": percentile_ci(boots[:, i]), "rank": int(base_rank[i]) + 1,
                  "rank_stability": round(float(np.mean(ranks[:, i] == base_rank[i])), 3)}
    return Stat(out, None, n, f"{method} (bootstrap {n_boot}, seed {seed}); weights sum to R^2", detail={"r2": round(r2, 4)})
