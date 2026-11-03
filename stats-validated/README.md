# Statistics checked against published results

**Exercised in the product?** TESTS ONLY. Nothing in the product imports this package, and its libraries are not in the app's lockfile.

## What it does
Reliability (alpha, omega), exploratory and confirmatory factor analysis, measurement invariance, relative-weights and dominance drivers, Wilson and bootstrap intervals, raking, change scores, ICC and within-group agreement. Every function returns `insufficient` instead of a number when it has too few responses, and bootstrap results are reproducible with a seed.

## When to use it
You need survey statistics you can defend, with a test suite that reproduces published numbers.

## How it works
* `stats/reliability.py`, `factor.py`, `invariance.py`, `drivers.py`, `estimates.py`, `change.py`, `multilevel.py`, `benchmarks.py`; results share the `Result` type in `result.py`.
* `tests/unit/stats/test_reference_values.py` compares to published values: Holzinger and Swineford (1939) CFA and invariance (lavaan tutorial), `psych::bfi` alpha, Shrout and Fleiss (1979) ICC, and statsmodels' Wilson interval. `test_properties.py` checks mathematical properties. `docs/VALIDATION.md` lists each comparison.

## Files

The Python package was renamed to `app` (imports look like `from app.core.verifier import ...`; the source tree is `backend/src/app/`, which contains its own `app/` sub-package) and the Postgres roles are `app_api` (runtime) and `app_owner` (tables and migrations). Capitalised brand names were replaced with `Acme`.

**src/ (copied as is; names and identifiers redacted)**

* `backend/src/app/stats/__init__.py`  <- `backend/src/app/stats/__init__.py`
* `backend/src/app/stats/benchmarks.py`  <- `backend/src/app/stats/benchmarks.py`
* `backend/src/app/stats/change.py`  <- `backend/src/app/stats/change.py`
* `backend/src/app/stats/drivers.py`  <- `backend/src/app/stats/drivers.py`
* `backend/src/app/stats/estimates.py`  <- `backend/src/app/stats/estimates.py`
* `backend/src/app/stats/factor.py`  <- `backend/src/app/stats/factor.py`
* `backend/src/app/stats/invariance.py`  <- `backend/src/app/stats/invariance.py`
* `backend/src/app/stats/multilevel.py`  <- `backend/src/app/stats/multilevel.py`
* `backend/src/app/stats/reliability.py`  <- `backend/src/app/stats/reliability.py`
* `backend/src/app/stats/result.py`  <- `backend/src/app/stats/result.py`

**tests/**

* `backend/tests/unit/stats/fixtures/.gitignore`  <- `backend/tests/unit/stats/fixtures/.gitignore`
* `backend/tests/unit/stats/test_properties.py`  <- `backend/tests/unit/stats/test_properties.py`
* `backend/tests/unit/stats/test_reference_values.py`  <- `backend/tests/unit/stats/test_reference_values.py`

**docs/**

* `INTEGRATE.md`  <- `docs/app-prod-handoff/handoff/app_stats/INTEGRATE.md`
* `VALIDATION.md`  <- `docs/app-prod-handoff/handoff/app_stats/VALIDATION.md`

## Depends on repository files that were NOT copied

Generated from the imports in the copied files. Each is needed (or must be replaced by your own equivalent) before this wires into a project.

* none

## External dependencies

* numpy
* pandas
* pytest
* scikit-learn
* scipy
* semopy
* statsmodels

Required for the tests of this module: semopy, pandas, scipy, statsmodels (also numpy and scikit-learn).

## Known limits and notes
* THE REFERENCE DATASETS ARE NOT COPIED AND NOT IN THE REPO. The Holzinger and Swineford data comes from the `semopy` package's bundled example data (`semopy.examples.holzinger39`). The Big Five `psych::bfi` data is fetched or read from a cache (see the test's fixture code and the `.cache/` ignore rule); get it from the R `psych` package.
* Oblique rotation is not implemented; EFA uses varimax.
* Minimum sample sizes are editable constants (alpha 30, omega 100, EFA 150, CFA 200, invariance 200 per group, weights 100).

## What was redacted or neutralised in these copies

* brand_name: 3

No `.env` file, key, token, respondent data or account identifier is included. See the top-level `SECRET_SCAN.md`.
