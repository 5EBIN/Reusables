# Handoff: integrate the validated statistics module (phase ai-12b)

Files in this bundle: `stats/` (package), `tests/` (25 tests), `scripts/fetch_sentiment_benchmarks.py`, `VALIDATION.md`.

1. Copy `stats/` to `backend/src/app/stats/` and change imports from `stats.` to `app.stats.`.
2. Copy tests to `backend/tests/unit/stats/` (mark `golden` for the reference-value file); add `tests/fixtures/.cache/` to `.gitignore`.
3. Declare in `backend/pyproject.toml`: `scipy`, `statsmodels`, `scikit-learn`, `semopy` (check that `pip install semopy` builds; if not, pin a version that does or vendor its MIT source under `third_party/` with its LICENSE). Add all four to THIRD_PARTY_NOTICES.
4. Run the 25 tests twice; all green.
5. Wire into the product (one commit per item, with tests):
   - Fix the index first: org-intel and engagement use one function, fixed instrument weights over dimensions meeting min_n (`sum(w*s)/sum(w)`), not weight × n. Test: index unchanged when only participation changes.
   - Per dimension show alpha with CI (and omega when n ≥ 100) on org-intel and engagement screens; below thresholds show "insufficient n".
   - Drivers: relative weights with CI and rank stability replace raw Pearson as the main view (keep Pearson as secondary).
   - Round-to-round change: Hedges' g with CI plus the regression-to-the-mean flag; same instrument version only (existing rule).
   - Language comparisons: run `measurement_invariance` by locale when both groups have ≥ 200; if scalar is not reached, the UI must say "not comparable" instead of showing a difference.
   - Team scores: show ICC(1)/rwg; warn when below cut-offs.
   - NPS: use the bootstrap CI when n < 100 (keep the current normal approximation above).
   - Benchmarks: percentile rank only when the opt-in pool has ≥ 10 organisations.
   - Store method, library versions and input hash with every stored statistic.
6. Narratives: these numbers reach text only through code-made claims and the verifier (ai-9).
7. Sentiment: run `scripts/fetch_sentiment_benchmarks.py --out data/benchmarks` (git-ignored), then the ai-6 evaluator on `tweeteval`, `astd`, `hard` plus the internal gold sets. Report them separately; never merge external and real-customer scores.
