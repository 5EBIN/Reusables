"""Exploratory (parallel analysis + ML EFA with varimax) and confirmatory factor analysis (semopy)."""
from __future__ import annotations
import re
import numpy as np
import pandas as pd
from .result import Stat, insufficient

EFA_MIN_N, CFA_MIN_N = 150, 200


def parallel_analysis(items: pd.DataFrame, n_iter: int = 100, seed: int = 7, quantile: float = 0.95) -> Stat:
    """Horn's parallel analysis on principal components and on the SMC-reduced correlation matrix (factors)."""
    x = items.astype(float).dropna().to_numpy()
    n, p = x.shape
    if n < max(EFA_MIN_N, 5 * p):
        return insufficient("parallel_analysis", n, max(EFA_MIN_N, 5 * p))
    r = np.corrcoef(x, rowvar=False)

    def reduced(rm):
        smc = 1 - 1 / np.diag(np.linalg.inv(rm))
        rr = rm.copy(); np.fill_diagonal(rr, smc)
        return rr

    obs_pc, obs_fa = np.linalg.eigvalsh(r)[::-1], np.linalg.eigvalsh(reduced(r))[::-1]
    rng = np.random.default_rng(seed)
    sim_pc, sim_fa = [], []
    for _ in range(n_iter):
        rr = np.corrcoef(rng.standard_normal((n, p)), rowvar=False)
        sim_pc.append(np.linalg.eigvalsh(rr)[::-1]); sim_fa.append(np.linalg.eigvalsh(reduced(rr))[::-1])
    thr_pc, thr_fa = np.quantile(sim_pc, quantile, axis=0), np.quantile(sim_fa, quantile, axis=0)

    def count(obs, thr):
        k = 0
        while k < p and obs[k] > thr[k]:
            k += 1
        return k
    # Primary: Horn's original component-based count. The SMC-reduced (factor) count tends to over-extract
    # and is reported for reference only.
    return Stat(count(obs_pc, thr_pc), None, n, f"parallel analysis (Horn, principal components; {n_iter} sims, {int(quantile*100)}th pct, seed {seed})",
                detail={"n_factors_smc": count(obs_fa, thr_fa), "eig_pc": obs_pc[:10].round(3).tolist()})


def efa(items: pd.DataFrame, n_factors: int, rotation: str = "varimax", seed: int = 7) -> Stat:
    from sklearn.decomposition import FactorAnalysis
    d = items.astype(float).dropna()
    n, p = d.shape
    if n < max(EFA_MIN_N, 5 * p):
        return insufficient("efa", n, max(EFA_MIN_N, 5 * p))
    z = (d - d.mean()) / d.std(ddof=0)
    fa = FactorAnalysis(n_components=n_factors, rotation=rotation, random_state=seed).fit(z.to_numpy())
    load = pd.DataFrame(fa.components_.T, index=items.columns, columns=[f"F{i+1}" for i in range(n_factors)])
    weak = [c for c in load.index if load.loc[c].abs().max() < 0.40]
    return Stat(load.round(3).to_dict(), None, n, f"ML factor analysis (scikit-learn), rotation={rotation}",
                [f"items with no loading >= 0.40: {weak}"] if weak else [], detail={"uniqueness": dict(zip(items.columns, fa.noise_variance_.round(3)))})


def cfa(model_desc: str, data: pd.DataFrame) -> Stat:
    """CFA via semopy (ML). Returns fit indices and standardised loadings; flags loadings < 0.40."""
    import semopy
    names = sorted(set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", model_desc)) & set(data.columns))
    d = data[names].dropna()                                 # complete cases on model variables only
    n = len(d)
    if n < CFA_MIN_N:
        return insufficient("cfa", n, CFA_MIN_N)
    m = semopy.Model(model_desc)
    m.fit(d)
    st = semopy.calc_stats(m).T["Value"]
    est = m.inspect(std_est=True)
    lam = est[est["op"] == "~"][["lval", "rval", "Est. Std"]]
    loadings = {f"{r.rval}->{r.lval}": float(r["Est. Std"]) for _, r in lam.iterrows()}
    fit = {k: float(st[k]) for k in ("chi2", "DoF", "CFI", "TLI", "RMSEA")}
    warn = [f"weak loading {k}: {v:.2f}" for k, v in loadings.items() if abs(v) < 0.40]
    if fit["CFI"] < 0.90 or fit["RMSEA"] > 0.08:
        warn.append("model fit below conventional thresholds (CFI >= 0.90 / RMSEA <= 0.08)")
    return Stat(fit, None, n, "CFA, maximum likelihood (semopy)", warn, detail={"std_loadings": loadings})
