"""Team-level aggregation checks: ICC(1), ICC(2) (Bliese, one-way ANOVA), rwg(j); mixed models for drivers."""
from __future__ import annotations
import pandas as pd
from .result import Stat, insufficient

ICC1_CUT, RWG_CUT = 0.05, 0.70   # conventional cut-offs; settings, not truths


def icc_oneway(values: pd.Series, groups: pd.Series, min_groups: int = 5) -> Stat:
    d = pd.DataFrame({"y": values, "g": groups}).dropna()
    gs = d.groupby("g")["y"]
    J, N = gs.ngroups, len(d)
    if J < min_groups:
        return insufficient("icc_oneway", J, min_groups, "teams")
    grand = d["y"].mean()
    ssb = float((gs.size() * (gs.mean() - grand) ** 2).sum())
    ssw = float(((d["y"] - gs.transform("mean")) ** 2).sum())
    msb, msw = ssb / (J - 1), ssw / (N - J)
    sizes = gs.size().to_numpy()
    k = (N - (sizes ** 2).sum() / N) / (J - 1)                 # average group size adjusted for unequal n
    icc1 = (msb - msw) / (msb + (k - 1) * msw)
    icc2 = (msb - msw) / msb if msb > 0 else float("nan")
    warn = [f"ICC(1) {icc1:.3f} below {ICC1_CUT}: team scores may not be meaningful"] if icc1 < ICC1_CUT else []
    return Stat(round(float(icc1), 4), None, N, "one-way ANOVA ICC(1)/ICC(2) (Bliese 2000)", warn,
                detail={"icc2": round(float(icc2), 4), "teams": J, "k": round(float(k), 3), "msb": msb, "msw": msw})


def rwg_j(items: pd.DataFrame, n_options: int) -> Stat:
    """James, Demaree & Wolf (1984) multi-item within-group agreement, uniform null."""
    d = items.astype(float).dropna()
    J, n = d.shape[1], len(d)
    if n < 3:
        return insufficient("rwg_j", n, 3, "raters in the team")
    s2 = float(d.var(ddof=1).mean())
    eu = (n_options ** 2 - 1) / 12
    ratio = min(s2 / eu, 1.0)
    r = (J * (1 - ratio)) / (J * (1 - ratio) + ratio)
    return Stat(round(r, 4), None, n, f"rwg(j), uniform null, A={n_options}",
                [f"rwg(j) {r:.2f} below {RWG_CUT}"] if r < RWG_CUT else [])


def mixed_drivers(df: pd.DataFrame, outcome: str, predictors: list[str], group: str, min_groups: int = 10) -> Stat:
    import statsmodels.formula.api as smf
    d = df[[outcome, group] + predictors].dropna()
    J = d[group].nunique()
    if J < min_groups:
        return insufficient("mixed_drivers", J, min_groups, "teams")
    z = d.copy()
    for c in [outcome] + predictors:
        z[c] = (z[c] - z[c].mean()) / z[c].std()
    m = smf.mixedlm(f"{outcome} ~ " + " + ".join(predictors), z, groups=z[group]).fit(reml=True, method="lbfgs")
    ci = m.conf_int()
    coefs = {p: {"beta": float(m.params[p]), "ci": (float(ci.loc[p, 0]), float(ci.loc[p, 1])), "p": float(m.pvalues[p])} for p in predictors}
    return Stat(coefs, None, len(d), "linear mixed model (statsmodels MixedLM, REML), standardised, random intercept per team",
                detail={"team_variance": float(m.cov_re.iloc[0, 0])})
