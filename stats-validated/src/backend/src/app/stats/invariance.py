"""Multi-group CFA measurement invariance (configural -> metric -> scalar), ML with mean structure.

Own implementation (numpy/scipy) so equality constraints across groups are explicit. Marker-variable
identification (first loading of each factor = 1); latent means fixed to 0 except in non-reference
groups at the scalar step. Test statistic T = sum_g n_g * F_g (biased covariance), as in lavaan.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import chi2 as chi2dist
from .result import Stat, insufficient

GROUP_MIN_N = 200
LEVELS = ("configural", "metric", "scalar")


def _parse(spec: dict[str, list[str]]):
    obs = [v for vs in spec.values() for v in vs]
    facs = list(spec)
    pat = np.zeros((len(obs), len(facs)), bool)
    for j, f in enumerate(facs):
        for v in spec[f]:
            pat[obs.index(v), j] = True
    return obs, facs, pat


def _fit(level, groups, obs, facs, pat):
    p, k, G = len(obs), len(facs), len(groups)
    free_l = [(i, j) for j in range(k) for i in np.where(pat[:, j])[0][1:]]  # first indicator is the marker
    tril = np.tril_indices(k)
    shared_l, shared_nu = level in ("metric", "scalar"), level == "scalar"
    sizes = []

    def add(name, size, shared):
        for g in range(G if not shared else 1):
            sizes.append((name, g if not shared else None, size))
    add("lam", len(free_l), shared_l)
    add("nu", p, shared_nu)
    add("theta", p, False)
    add("phi", len(tril[0]), False)
    if level == "scalar":
        for g in range(1, G):
            sizes.append(("kappa", g, k))
    idx, pos = {}, 0
    for name, g, size in sizes:
        idx[(name, g)] = slice(pos, pos + size); pos += size

    def get(theta, name, g):
        return theta[idx[(name, g)]] if (name, g) in idx else theta[idx[(name, None)]]

    def implied(theta, g):
        L = pat.astype(float).copy() * 0
        for j in range(k):
            L[np.where(pat[:, j])[0][0], j] = 1.0
        for (i, j), v in zip(free_l, get(theta, "lam", g)):
            L[i, j] = v
        C = np.zeros((k, k)); C[tril] = get(theta, "phi", g)
        d = np.arange(k); C[d, d] = np.exp(C[d, d])
        Phi = C @ C.T
        Th = np.diag(np.exp(get(theta, "theta", g)))
        kap = theta[idx[("kappa", g)]] if ("kappa", g) in idx else np.zeros(k)
        return L @ Phi @ L.T + Th, get(theta, "nu", g) + L @ kap

    stats = []
    for df in groups:
        x = df[obs].to_numpy(float)
        stats.append((len(x), np.cov(x, rowvar=False, bias=True), x.mean(0)))

    def F(theta):
        tot = 0.0
        for g, (n, S, m) in enumerate(stats):
            Sig, mu = implied(theta, g)
            sign, ld = np.linalg.slogdet(Sig)
            if sign <= 0:
                return 1e10
            Si = np.linalg.inv(Sig); dm = m - mu
            tot += n * (ld + np.trace(S @ Si) - np.linalg.slogdet(S)[1] - p + dm @ Si @ dm)
        return tot

    x0 = np.zeros(pos)
    for (name, g), sl in idx.items():
        gg = 0 if g is None else g
        n, S, m = stats[gg]
        if name == "lam": x0[sl] = 1.0
        elif name == "nu": x0[sl] = m
        elif name == "theta": x0[sl] = np.log(np.diag(S) * 0.5)
        elif name == "phi":
            v = np.zeros(len(tril[0]))
            for t, (a, b) in enumerate(zip(*tril)):
                if a == b: v[t] = np.log(np.sqrt(0.5 * S[np.where(pat[:, a])[0][0]] [np.where(pat[:, a])[0][0]]))
            x0[sl] = v
    r1 = minimize(F, x0, method="L-BFGS-B", options={"maxiter": 20000, "maxfun": 200000})
    res = minimize(F, r1.x, method="BFGS", options={"maxiter": 5000, "gtol": 1e-7})
    converged = abs(r1.fun - res.fun) < 1e-3 or res.success
    T = float(res.fun)
    moments = G * (p * (p + 1) // 2 + p)
    df_ = moments - pos
    N = sum(s[0] for s in stats)
    # baseline (independence) model with free means: per group diag Sigma
    Tb = 0.0
    for n, S, m in stats:
        Tb += n * (np.sum(np.log(np.diag(S))) - np.linalg.slogdet(S)[1])
    dfb = G * (p * (p + 1) // 2 + p) - G * 2 * p
    cfi = 1 - max(T - df_, 0) / max(T - df_, Tb - dfb, 1e-12)
    rmsea = float(np.sqrt(max(T - df_, 0) / (df_ * N)) * np.sqrt(G)) if df_ > 0 else 0.0
    return {"chi2": round(T, 3), "df": int(df_), "cfi": round(float(cfi), 4), "rmsea": round(rmsea, 4), "converged": bool(converged)}


def measurement_invariance(data: pd.DataFrame, group_col: str, spec: dict[str, list[str]],
                           d_cfi: float = -0.01, d_rmsea: float = 0.015) -> Stat:
    obs, facs, pat = _parse(spec)
    order = list(dict.fromkeys(data[group_col].dropna()))      # reference group = first in data order
    groups = [data[data[group_col] == g][obs].dropna() for g in order]
    nmin = min(len(g) for g in groups)
    if nmin < GROUP_MIN_N:
        out = insufficient("measurement_invariance", nmin, GROUP_MIN_N, "responses in the smallest group")
        out.detail["note"] = "means must not be compared across these groups until invariance is established"
        return out
    fits = {lvl: _fit(lvl, groups, obs, facs, pat) for lvl in LEVELS}
    reached = "none"
    prev = None
    for lvl in LEVELS:
        f = fits[lvl]
        if prev is None:
            ok = f["cfi"] >= 0.90
        else:
            ok = (f["cfi"] - fits[prev]["cfi"]) >= d_cfi and (f["rmsea"] - fits[prev]["rmsea"]) <= d_rmsea
            f["delta_chi2_p"] = float(chi2dist.sf(f["chi2"] - fits[prev]["chi2"], f["df"] - fits[prev]["df"]))
        if not ok:
            break
        reached, prev = lvl, lvl
    comparable = reached == "scalar"
    warn = [] if comparable else [f"invariance reached '{reached}': do not compare means across {group_col}"]
    return Stat(reached, None, sum(len(g) for g in groups), f"multi-group CFA (ML), criteria dCFI >= {d_cfi}, dRMSEA <= {d_rmsea}",
                warn, detail={"groups": order, "fits": fits, "means_comparable": comparable})
