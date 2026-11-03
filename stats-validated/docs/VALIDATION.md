# Acme statistics module: validation report

Run: 18 Oct 2026, Python 3, numpy 2.5.3, scipy 1.18.1, statsmodels 0.15.0, scikit-learn, semopy 2.3.11 (MIT).
Result: **25 tests passed, on two consecutive runs.** Command: `python -m pytest -q tests`.

## Matched against published results

| Function | Reference data | Published value | Ours |
|---|---|---|---|
| `factor.cfa` | Holzinger & Swineford (1939), 3-factor model, n=301 (lavaan tutorial) | χ² 85.306, df 24, CFI .931, TLI .896, RMSEA .092 | identical |
| `invariance.measurement_invariance` | Same data, groups = school (lavaan tutorial) | configural χ² 115.851/48, metric 124.044/54, scalar 164.103/60; CFI .923/.921/.882 | identical; verdict "metric" (scalar fails ΔCFI) |
| `reliability.cronbach_alpha` | psych::bfi, 2,800 respondents, Big Five, reversed items keyed | A .70, C .72, E .76, N .81, O .60 | within 0.01 |
| `multilevel.icc_oneway` | Shrout & Fleiss (1979), 6 targets × 4 judges | ICC(1,1) .17, ICC(1,k) .44 | .17, .44 |
| `estimates.wilson_ci` | statsmodels `proportion_confint(method="wilson")` | reference implementation | equal to 1e-9 |

## Checked by mathematical property (no exact published value used)

- `factor.parallel_analysis` on bfi recovers 5–6 components; `factor.efa` with 5 factors groups ≥ 22 of 25 items with their own scale.
- `reliability.omega_total`: within 0.02 of alpha or above, for every bfi scale.
- `drivers` (relative weights and dominance): weights sum to R²; equal squared correlations for orthogonal predictors; the two methods agree within 0.02; correct ranking on simulated data; rank stability reported.
- `change`: Hedges' g in the expected range with CI; paired change exact; Jacobson–Truax threshold formula; regression-to-the-mean flags lowest decile.
- `estimates`: NPS exact (54% − 12% = 42) with bootstrap CI; raking reaches target margins and reports design effect.
- `multilevel.rwg_j`: 1.0 for perfect agreement, below 0.3 for uniform random answers. `mixed_drivers` recovers the simulated effect.
- Every function refuses below its minimum n (returns `insufficient`, never a number); bootstrap is reproducible with a seed.

## Minimum sample sizes built in (editable constants)
alpha 30 · omega 100 · EFA 150 and ≥ 5 per item · CFA 200 · invariance 200 per group · relative weights 100 · dominance ≤ 12 predictors · change 20 per round · NPS 5 · ICC 5 teams · mixed model 10 teams · benchmark percentile 10 organisations.

## Limits
- Oblique rotation (oblimin) is not implemented; EFA uses varimax via scikit-learn.
- `cfa` inherits semopy's estimator (ML); no robust (MLR) or ordinal (WLSMV) estimation for Likert items. For 5-point items, results are standard practice but approximate.
- The relative-weights and dominance routines are validated by properties, not against a published table.
- semopy 2.3.11 failed to build as a wheel here (a setuptools/Debian packaging quirk), so it was installed by copying its pure-Python source. Check `pip install semopy` works in the project's environment.

## Benchmark sentiment data (`scripts/fetch_sentiment_benchmarks.py`)
Verified downloads, stratified samples in evaluator format:
- TweetEval sentiment (English tweets): positive / neutral / negative.
- ASTD (Arabic tweets, Egyptian-heavy): positive / negative / neutral (objective) / mixed.
- HARD (Arabic hotel reviews, Gulf-relevant): positive / negative from star ratings (noisy labels).
**Evaluation only.** None states a commercial licence, so do not commit or ship them; cite the papers in reports.
These are external checks. They are not a substitute for 300+ real Acme comments labelled by two people.
