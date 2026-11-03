# Retrieval over answers ("Ask your survey")

**Exercised in the product?** TESTS ONLY in practice. A screen exists, but nothing in the product creates the embeddings it needs (the only writer, `/semantic/embed`, has no caller), and the embedders available are a hashed stand-in or an optional local English model. An OpenAI-compatible embedder is not built (`app/container.py`).

## What it does
Finds the answers closest in meaning to a question (cosine similarity, ignoring anything below 0.30 and needing at least five close answers), has a model draft at most four sentences that cite their evidence, and a verifier throws the whole draft away if any sentence is unsupported. Embeddings are stored in Postgres with pgvector.

## When to use it
You want grounded answers over a bounded set of texts and can re-embed them yourself.

## How it works
* `core/embed.py`, `core/semantic.py`: chunking, similarity, clustering helpers.
* `core/rag.py`: retrieval, the draft step, and the per-sentence support check (quotes must be exact and digits are refused).
* `adapters/embed_fake.py` (hashed word-and-letter fingerprint) and `adapters/embed_local_en.py` (local English model); `db/repos/*` for storage.

## Files

The Python package was renamed to `app` (imports look like `from app.core.verifier import ...`; the source tree is `backend/src/app/`, which contains its own `app/` sub-package) and the Postgres roles are `app_api` (runtime) and `app_owner` (tables and migrations). Capitalised brand names were replaced with `Acme`.

**src/ (copied as is; names and identifiers redacted)**

* `backend/src/app/adapters/embed_fake.py`  <- `backend/src/app/adapters/embed_fake.py`
* `backend/src/app/adapters/embed_local_en.py`  <- `backend/src/app/adapters/embed_local_en.py`
* `backend/src/app/app/routers/semantic.py`  <- `backend/src/app/app/routers/semantic.py`
* `backend/src/app/core/embed.py`  <- `backend/src/app/core/embed.py`
* `backend/src/app/core/evidence.py`  <- `backend/src/app/core/evidence.py`
* `backend/src/app/core/rag.py`  <- `backend/src/app/core/rag.py`
* `backend/src/app/core/semantic.py`  <- `backend/src/app/core/semantic.py`
* `backend/src/app/db/repos/rag_answers.py`  <- `backend/src/app/db/repos/rag_answers.py`
* `backend/src/app/db/repos/semantic_clusters.py`  <- `backend/src/app/db/repos/semantic_clusters.py`
* `backend/src/app/db/repos/text_embeddings.py`  <- `backend/src/app/db/repos/text_embeddings.py`

**tests/**

* `backend/tests/integration/test_live_rag.py`  <- `backend/tests/integration/test_live_rag.py`
* `backend/tests/integration/test_semantic.py`  <- `backend/tests/integration/test_semantic.py`
* `backend/tests/integration/test_semantic_erasure.py`  <- `backend/tests/integration/test_semantic_erasure.py`
* `backend/tests/integration/test_semantic_rls.py`  <- `backend/tests/integration/test_semantic_rls.py`
* `backend/tests/unit/test_embed_core.py`  <- `backend/tests/unit/test_embed_core.py`
* `backend/tests/unit/test_embedders.py`  <- `backend/tests/unit/test_embedders.py`
* `backend/tests/unit/test_rag_core.py`  <- `backend/tests/unit/test_rag_core.py`
* `backend/tests/unit/test_semantic_core.py`  <- `backend/tests/unit/test_semantic_core.py`

**docs/**

* `SEMANTIC.md`  <- `docs/SEMANTIC.md`

## Depends on repository files that were NOT copied

Generated from the imports in the copied files. Each is needed (or must be replaced by your own equivalent) before this wires into a project.

* `backend/src/app/adapters/llm_anthropic.py`
* `backend/src/app/adapters/llm_tasks.py`
* `backend/src/app/app/ai_guard.py`
* `backend/src/app/app/container.py`
* `backend/src/app/app/deps.py`
* `backend/src/app/app/routers/surveys.py`
* `backend/src/app/app/routers/text.py`
* `backend/src/app/core/__init__.py`
* `backend/src/app/core/distribution.py`
* `backend/src/app/core/normalize_ar.py`
* `backend/src/app/core/query_plan.py`
* `backend/src/app/core/text_analysis.py`
* `backend/src/app/db/__init__.py`
* `backend/src/app/db/repos/__init__.py`
* `backend/src/app/db/repos/analysis_runs.py`
* `backend/src/app/db/repos/answer_tags.py`
* `backend/src/app/db/repos/taxonomies.py`
* `backend/src/app/db/repos/theme_assignments.py`

## External dependencies

* asyncpg
* fastapi
* numpy
* pydantic
* pytest
* sentence_transformers

## Known limits and notes
* `docs/AI_ARCHITECTURE.md` in the original repo mentions a `PgVectorRetriever` behind a flag; that class does not exist. This module is the whole retrieval path.
* The fake embedder only finds words that look alike; it does not understand meaning.
* The `integration/test_live_rag.py` test is written to run against a real model and database when configured.

## What was redacted or neutralised in these copies

* email: 4

No `.env` file, key, token, respondent data or account identifier is included. See the top-level `SECRET_SCAN.md`.
