"""Mathematical properties and refusal rules."""
import numpy as np
import pandas as pd
from app.stats.reliability import cronbach_alpha
from app.stats.drivers import drivers
from app.stats.change import hedges_g, paired_change, reliable_change_threshold, regression_to_mean_flags
from app.stats.estimates import nps, rake
from app.stats.benchmarks import percentile_rank
from app.stats.multilevel import rwg_j, icc_oneway, mixed_drivers

rng = np.random.default_rng(1)


def test_alpha_invariant_to_item_order_and_refuses_small_n():
    x = pd.DataFrame(rng.normal(size=(200, 4)) + rng.normal(size=(200, 1)), columns=list("abcd"))
    assert cronbach_alpha(x, n_boot=10).value == cronbach_alpha(x[list("dcba")], n_boot=10).value
    s = cronbach_alpha(x.head(10))
    assert s.insufficient and s.value is None


def test_bootstrap_reproducible_with_seed():
    x = pd.DataFrame(rng.normal(size=(100, 3)) + rng.normal(size=(100, 1)))
    assert cronbach_alpha(x, n_boot=100, seed=3).ci == cronbach_alpha(x, n_boot=100, seed=3).ci


def _driver_data(n=400, corr=0.4):
    cov = np.full((4, 4), corr); np.fill_diagonal(cov, 1)
    X = rng.multivariate_normal(np.zeros(4), cov, n)
    y = X @ np.array([0.6, 0.3, 0.1, 0.0]) + rng.normal(scale=0.8, size=n)
    return pd.DataFrame(np.column_stack([X, y]), columns=["d1", "d2", "d3", "d4", "y"])


def test_relative_weights_sum_to_r2_and_rank_correctly():
    df = _driver_data()
    s = drivers(df, "y", ["d1", "d2", "d3", "d4"], n_boot=100)
    import statsmodels.api as sm
    r2 = sm.OLS(df["y"], sm.add_constant(df[["d1", "d2", "d3", "d4"]])).fit().rsquared
    assert abs(sum(v["weight"] for v in s.value.values()) - r2) < 1e-3
    assert s.value["d1"]["rank"] == 1 and s.value["d4"]["rank"] == 4


def test_relative_weights_equal_squared_r_when_orthogonal():
    X = rng.normal(size=(500, 4)); X -= X.mean(0)
    Q, _ = np.linalg.qr(X); X = Q * np.sqrt(len(X))              # sample correlations exactly zero
    y = X @ np.array([0.6, 0.3, 0.1, 0.0]) + rng.normal(scale=0.8, size=500)
    df = pd.DataFrame(np.column_stack([X, y]), columns=["d1", "d2", "d3", "d4", "y"])
    s = drivers(df, "y", ["d1", "d2", "d3", "d4"], n_boot=20)
    r = df.corr()["y"]
    for c in ["d1", "d2", "d3", "d4"]:
        assert abs(s.value[c]["weight"] - r[c] ** 2) < 1e-4


def test_dominance_matches_shapley_sum_and_agrees_with_rw():
    df = _driver_data()
    da = drivers(df, "y", ["d1", "d2", "d3", "d4"], method="dominance", n_boot=30)
    rw = drivers(df, "y", ["d1", "d2", "d3", "d4"], n_boot=30)
    assert abs(da.detail["r2"] - rw.detail["r2"]) < 1e-3
    for c in ["d1", "d2", "d3", "d4"]:
        assert abs(da.value[c]["weight"] - rw.value[c]["weight"]) < 0.02


def test_drivers_refuse_small_n():
    assert drivers(_driver_data(n=50), "y", ["d1", "d2"]).insufficient


def test_hedges_g_known_value_and_paired():
    a = rng.normal(50, 10, 500); b = rng.normal(55, 10, 500)
    s = hedges_g(a, b, n_boot=200)
    assert 0.35 < s.value < 0.65 and s.ci[0] < s.value < s.ci[1]
    p = paired_change(a, a + 2)
    assert abs(p.value - 2) < 1e-9
    assert abs(reliable_change_threshold(10, 0.8) - 1.96 * np.sqrt(2) * 10 * np.sqrt(0.2)) < 1e-12
    assert regression_to_mean_flags({f"t{i}": float(i) for i in range(20)}) == {"t0", "t1"}


def test_nps_bootstrap_and_weights():
    s = nps([10] * 54 + [8] * 34 + [3] * 12)
    assert s.value == 42.0 and s.ci[0] < 42 < s.ci[1]
    assert nps([10, 9]).insufficient


def test_raking_hits_margins_and_reports_deff():
    df = pd.DataFrame({"g": ["m"] * 70 + ["f"] * 30})
    s = rake(df, {"g": {"m": 0.5, "f": 0.5}})
    w = s.value
    assert abs(w[df.g == "f"].sum() / w.sum() - 0.5) < 1e-6 and s.detail["design_effect"] > 1


def test_percentile_rank_requires_pool():
    assert percentile_rank(70, [60, 65, 80]).insufficient
    s = percentile_rank(70, list(range(50, 90, 3)))
    assert 0 < s.value < 100


def test_rwg_bounds():
    agree = pd.DataFrame({"a": [4, 4, 4, 4], "b": [5, 5, 5, 5]})
    assert rwg_j(agree, 5).value == 1.0
    uniform = pd.DataFrame(rng.integers(1, 6, size=(500, 5)))
    assert rwg_j(uniform, 5).value < 0.3


def test_mixed_drivers_runs():
    teams = np.repeat(np.arange(20), 15)
    x = rng.normal(size=len(teams)); y = 0.5 * x + rng.normal(size=20)[teams] + rng.normal(size=len(teams))
    s = mixed_drivers(pd.DataFrame({"y": y, "x": x, "team": teams}), "y", ["x"], "team")
    assert 0.2 < s.value["x"]["beta"] < 0.6
    assert icc_oneway(pd.Series(y), pd.Series(teams)).value > 0.05
