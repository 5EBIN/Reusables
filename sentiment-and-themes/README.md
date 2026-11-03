# Sentiment and theme tagging for open-text answers

**Exercised in the product?** The word-list sentiment and the theme taxonomy are used in the product. The MODEL sentiment route (`app/routers/sentiment.py`) is exercised in TESTS ONLY: no screen calls it (a live check on 24 Oct 2026 got 16 of 16 clear examples right).

## What it does
Two ways to label an answer positive, neutral or negative (an English and Arabic lexicon, or a model that must pick from the fixed labels, with a confidence below which the answer counts as neutral-with-a-flag), plus themes: a model proposes themes, a person approves them, the taxonomy is frozen, and answers are tagged by keyword or by a model that may only choose from the approved list.

## When to use it
You analyse free-text answers and need results that are reproducible and reviewable.

## How it works
* `core/lexicon.py` and `core/sentiment.py`: the lexicon classifier and the gate that decides when to trust a label.
* `core/themes.py`, `core/theme.py`, `core/text_analysis.py`: propose, approve, freeze and tag (keyword and model routes, a confidence gate of 0.85 and 0.15).
* `db/repos/*`: taxonomies are versioned and frozen so earlier counts stay reproducible.

## Files

The Python package was renamed to `app` (imports look like `from app.core.verifier import ...`; the source tree is `backend/src/app/`, which contains its own `app/` sub-package) and the Postgres roles are `app_api` (runtime) and `app_owner` (tables and migrations). Capitalised brand names were replaced with `Acme`.

**src/ (copied as is; names and identifiers redacted)**

* `backend/src/app/app/routers/sentiment.py`  <- `backend/src/app/app/routers/sentiment.py`
* `backend/src/app/app/routers/text.py`  <- `backend/src/app/app/routers/text.py`
* `backend/src/app/core/lexicon.py`  <- `backend/src/app/core/lexicon.py`
* `backend/src/app/core/normalize_ar.py`  <- `backend/src/app/core/normalize_ar.py`
* `backend/src/app/core/sentiment.py`  <- `backend/src/app/core/sentiment.py`
* `backend/src/app/core/text_analysis.py`  <- `backend/src/app/core/text_analysis.py`
* `backend/src/app/core/theme.py`  <- `backend/src/app/core/theme.py`
* `backend/src/app/core/themes.py`  <- `backend/src/app/core/themes.py`
* `backend/src/app/db/repos/answer_sentiment.py`  <- `backend/src/app/db/repos/answer_sentiment.py`
* `backend/src/app/db/repos/answer_tags.py`  <- `backend/src/app/db/repos/answer_tags.py`
* `backend/src/app/db/repos/org_themes.py`  <- `backend/src/app/db/repos/org_themes.py`
* `backend/src/app/db/repos/taxonomies.py`  <- `backend/src/app/db/repos/taxonomies.py`
* `backend/src/app/db/repos/theme_assignments.py`  <- `backend/src/app/db/repos/theme_assignments.py`
* `backend/src/app/db/repos/themes.py`  <- `backend/src/app/db/repos/themes.py`
* `scripts/eval_sentiment.py`  <- `scripts/eval_sentiment.py`

**tests/**

* `backend/tests/integration/test_ask_text.py`  <- `backend/tests/integration/test_ask_text.py`
* `backend/tests/integration/test_sentiment_api.py`  <- `backend/tests/integration/test_sentiment_api.py`
* `backend/tests/integration/test_tagging_llm.py`  <- `backend/tests/integration/test_tagging_llm.py`
* `backend/tests/unit/test_lexicon.py`  <- `backend/tests/unit/test_lexicon.py`
* `backend/tests/unit/test_sentiment_core.py`  <- `backend/tests/unit/test_sentiment_core.py`
* `backend/tests/unit/test_themes_core.py`  <- `backend/tests/unit/test_themes_core.py`

## Depends on repository files that were NOT copied

Generated from the imports in the copied files. Each is needed (or must be replaced by your own equivalent) before this wires into a project.

* `backend/src/app/adapters/llm_openai_compat.py`
* `backend/src/app/adapters/llm_tasks.py`
* `backend/src/app/adapters/ratelimit.py`
* `backend/src/app/app/ai_fallback.py`
* `backend/src/app/app/ai_guard.py`
* `backend/src/app/app/analytics/engine.py`
* `backend/src/app/app/audit.py`
* `backend/src/app/app/container.py`
* `backend/src/app/app/deps.py`
* `backend/src/app/app/routers/__init__.py`
* `backend/src/app/app/routers/semantic.py`
* `backend/src/app/app/routers/surveys.py`
* `backend/src/app/app/security.py`
* `backend/src/app/core/__init__.py`
* `backend/src/app/core/exporters.py`
* `backend/src/app/core/narrative.py`
* `backend/src/app/core/query_plan.py`
* `backend/src/app/core/rag.py`
* `backend/src/app/db/__init__.py`
* `backend/src/app/db/repos/__init__.py`
* `backend/src/app/db/repos/analysis_runs.py`
* `backend/src/app/db/repos/answers.py`
* `backend/src/app/db/repos/org_settings.py`

## External dependencies

* asyncpg
* fastapi
* httpx
* pydantic
* pytest

## Known limits and notes
* The lexicon is English and Arabic only. No tests cover Urdu, Hindi, Russian or Filipino sentiment.
* The model routes depend on the task layer in `llm-provider-adapter`.
* `scripts/eval_sentiment.py` scores a labelled set; the labelled data is not included.

## What was redacted or neutralised in these copies

* email: 3

No `.env` file, key, token, respondent data or account identifier is included. See the top-level `SECRET_SCAN.md`.
