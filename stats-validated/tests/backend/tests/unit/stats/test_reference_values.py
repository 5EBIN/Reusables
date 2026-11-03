"""Statistics validated against published reference results. Each test names its source."""
import pathlib
import pandas as pd
import pytest
from semopy.examples import holzinger39
from app.stats.reliability import cronbach_alpha, omega_total, reverse
from app.stats.factor import cfa, parallel_analysis, efa
from app.stats.invariance import measurement_invariance
from app.stats.multilevel import icc_oneway
from app.stats.estimates import wilson_ci

pytestmark = pytest.mark.golden      # scores the statistics against published reference values

FIX = pathlib.Path(__file__).parent / "fixtures"
HS_SPEC = {"visual": ["x1", "x2", "x3"], "textual": ["x4", "x5", "x6"], "speed": ["x7", "x8", "x9"]}


BFI_URL = "https://raw.githubusercontent.com/vincentarelbundock/Rdatasets/master/csv/psych/bfi.csv"
BFI_SHA16 = "68ae71a96c2157b0"


@pytest.fixture(scope="module")
def bfi():
    # psych::bfi (Revelle), 2,800 respondents, 25 items on a 1-6 scale, via Rdatasets. Downloaded and cached at
    # test time (not committed: the psych package is GPL-licensed). Skips when offline.
    import hashlib, urllib.request
    p = FIX / ".cache" / "bfi.csv"
    if not p.exists():
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(urllib.request.urlopen(BFI_URL, timeout=30).read())
        except Exception as e:
            pytest.skip(f"bfi reference data unavailable offline: {e}")
    assert hashlib.sha256(p.read_bytes()).hexdigest()[:16] == BFI_SHA16, "reference data changed upstream"
    d = pd.read_csv(p)
    return reverse(d, ["A1", "C4", "C5", "E1", "E2", "O2", "O5"], 1, 6)


# Source: psych package documentation, scoreItems/alpha on bfi with keys reversing A1,C4,C5,E1,E2,O2,O5:
# raw alpha A .70, C .72, E .76, N .81, O .60 (pairwise covariances).
@pytest.mark.parametrize("scale,expected", [("A", 0.70), ("C", 0.72), ("E", 0.76), ("N", 0.81), ("O", 0.60)])
def test_alpha_bfi_matches_psych(bfi, scale, expected):
    s = cronbach_alpha(bfi[[f"{scale}{i}" for i in range(1, 6)]], n_boot=200)
    assert abs(s.value - expected) < 0.01, (scale, s.value)
    assert s.ci[0] < s.value < s.ci[1]


# Source: lavaan tutorial, CFA of HolzingerSwineford1939 three-factor model:
# chi2 = 85.306, df = 24, CFI = 0.931, TLI = 0.896, RMSEA = 0.092.
def test_cfa_holzinger_matches_lavaan():
    model = "visual =~ x1 + x2 + x3\ntextual =~ x4 + x5 + x6\nspeed =~ x7 + x8 + x9"
    s = cfa(model, holzinger39.get_data())
    assert abs(s.value["chi2"] - 85.306) < 0.01 and s.value["DoF"] == 24
    assert abs(s.value["CFI"] - 0.931) < 0.001 and abs(s.value["TLI"] - 0.896) < 0.001 and abs(s.value["RMSEA"] - 0.092) < 0.001


# Source: lavaan tutorial, measurement invariance across school (Pasteur, Grant-White):
# configural chi2 115.851 df 48; metric 124.044 df 54; scalar 164.103 df 60; CFI .923 / .921 / .882.
def test_invariance_holzinger_matches_lavaan(monkeypatch):
    import app.stats.invariance as inv
    monkeypatch.setattr(inv, "GROUP_MIN_N", 100)            # groups have 156 and 145; lower the guard for the reference test only
    s = measurement_invariance(holzinger39.get_data(), "school", HS_SPEC)
    f = s.detail["fits"]
    assert (f["configural"]["chi2"], f["configural"]["df"]) == (115.851, 48)
    assert (f["metric"]["chi2"], f["metric"]["df"]) == (124.044, 54)
    assert (f["scalar"]["chi2"], f["scalar"]["df"]) == (164.103, 60)
    assert abs(f["configural"]["cfi"] - 0.923) < 0.001 and abs(f["scalar"]["cfi"] - 0.882) < 0.001
    assert s.value == "metric" and s.detail["means_comparable"] is False   # scalar step fails dCFI


def test_invariance_refuses_small_groups():
    s = measurement_invariance(holzinger39.get_data(), "school", HS_SPEC)
    assert s.insufficient and "smallest group" in s.warnings[0]


# Source: Shrout & Fleiss (1979), Table 2 data (6 targets x 4 judges): ICC(1,1) = .17, ICC(1,k) = .44.
def test_icc_matches_shrout_fleiss():
    data = [[9, 2, 5, 8], [6, 1, 3, 2], [8, 4, 6, 8], [7, 1, 2, 6], [10, 5, 6, 9], [6, 2, 4, 7]]
    vals = [v for row in data for v in row]; grp = [i for i, row in enumerate(data) for _ in row]
    s = icc_oneway(pd.Series(vals), pd.Series(grp))
    assert round(s.value, 2) == 0.17 and round(s.detail["icc2"], 2) == 0.44


# The bfi items were written for five factors (Big Five). Component-based parallel analysis should
# recover 5 or 6 (psych's documentation reports 6 for its own variant). Not an exact published value.
def test_parallel_analysis_bfi(bfi):
    s = parallel_analysis(bfi.iloc[:, 1:26], n_iter=50)
    assert s.value in (5, 6)


def test_efa_recovers_big_five(bfi):
    items = bfi.iloc[:, 1:26]
    load = pd.DataFrame(efa(items, 5).value)
    top = load.abs().idxmax(axis=1)                  # factor each item loads on most
    by_scale = {sc: top[[f"{sc}{i}" for i in range(1, 6)]].mode()[0] for sc in "ACENO"}
    hits = sum(top[f"{sc}{i}"] == by_scale[sc] for sc in "ACENO" for i in range(1, 6))
    assert len(set(by_scale.values())) == 5 and hits >= 22


def test_omega_at_least_close_to_alpha(bfi):
    for sc in "ACENO":
        it = bfi[[f"{sc}{i}" for i in range(1, 6)]]
        o, a = omega_total(it).value, cronbach_alpha(it.dropna(), missing="complete", n_boot=50).value
        assert o >= a - 0.02 and 0.5 < o < 0.9


# Source: statsmodels proportion_confint(method="wilson") as the reference implementation.
def test_wilson_matches_statsmodels():
    from statsmodels.stats.proportion import proportion_confint
    for k, n in [(0, 10), (3, 10), (81, 150), (150, 150)]:
        lo, hi = proportion_confint(k, n, method="wilson")
        s = wilson_ci(k, n)
        assert abs(s.ci[0] - lo) < 1e-9 and abs(s.ci[1] - hi) < 1e-9
