# Semantic analysis (embeddings, clusters, nearest-theme assignment, search)

Additional method beside keyword tagging. It never replaces it: assignments carry `method: "semantic"` and `answer_tags` is untouched.
The LLM only **names** clusters. Sizes, distances, scores and bands come from deterministic Python (`core/semantic.py`, numpy, fixed seed).

## Seam
`EmbeddingProvider` port (`core/ports.py`: `model_id`, `dim`, `async embed(texts, kind='document'|'query')`) chosen in `app/container.py` by `EMBEDDINGS_PROVIDER`:

| value | adapter | notes |
|---|---|---|
| `fake` (default, all tests) | `adapters/embed_fake.py` | hashed word + char-trigram vectors, L2-normalised, optional synonym map so tests can make "terrible"/"awful"/"زفت"/"سيء" close |
| `local_en` | `adapters/embed_local_en.py` | `BAAI/bge-small-en-v1.5`, 384-d, run locally; queries get the model-card prefix; batched and re-normalised |

## Flow
```
answers --POST /semantic/embed--> text_embeddings (vector, per model_id/dim, source_hash)      [append-only]
text_embeddings --POST /semantic/cluster--> seeded k-means (auto-k, min size >= 5, outliers = unclustered)
      --> propose_cluster_labels (LLM, texts inside <data>) --> verify_label --> semantic_clusters/_members/_labels   [append-only]
frozen taxonomy + embeddings --POST /semantic/assign--> cosine to theme centroids
      >= HIGH assigned | LOW..HIGH review | < LOW other  --> theme_assignments (method='semantic')      [append-only]
GET /semantic/clusters | /assignments | /search?q=   (writers only; counts below min-n are suppressed)
```
Theme centroid = mean of embedded theme keywords + label, plus answers the frozen keyword tagging put in exactly that one theme (max 20).
Default thresholds HIGH 0.70 / LOW 0.50 are for bge-class models; calibrate per tenant (below).

## Label verifier (`verify_label`)
label 1-60 chars, description 1-300, no digits (the model never counts), no markup/control characters, 1-5 distinct `verbatim_ids`, each a real member of *that* cluster.
Any failure drops the label; the cluster is shown as `unlabelled`. A refusal/outage of the LLM also leaves clusters unlabelled (HTTP 201 either way).

## Append-only guarantees
Migration `0110`: `text_embeddings`, `semantic_clusters`, `semantic_cluster_members`, `semantic_cluster_labels`, `theme_assignments`. RLS via `app.apply_org_rls`
(forced); the API role has **SELECT + INSERT only** (tests: UPDATE/DELETE/TRUNCATE raise `InsufficientPrivilegeError`). A re-run inserts new rows under a new `run_id`;
the latest run wins on read. Idempotency: embeddings are unique per `(response, question, model, source_hash)`; cluster and assign runs carry an `inputs_hash` (same inputs -> `cached: true`, no new rows).
Known gap: these tables have no FK to `responses` (an FK would break erasure under forced RLS), so a data-subject erasure must also remove semantic rows via an owner-side job (not built yet).

## Models never mix
Storage is `vec vector` (no fixed dim) + `dim int` with `check (vector_dims(vec) = dim)`. Every read filters `model_id` and `dim`; `core.semantic` raises `CrossModelError` if two models/dims are compared.
Exact cosine (`<=>`) is used for search; no ANN index is needed at survey scale. When a tenant outgrows it, add a per-model HNSW expression index, e.g.
`create index on text_embeddings using hnsw ((vec::vector(384)) vector_cosine_ops) where model_id='BAAI/bge-small-en-v1.5';` (and include the same cast in the query).
pgvector must be installed (`scripts/dev-db.sh` runs `create extension vector`; the migration fails with a clear message otherwise).

## Enabling `local_en`
`pip install 'app[semantic]'` (sentence-transformers; weights download on first use), set `EMBEDDINGS_PROVIDER=local_en`. Respondent text stays on the host.

## Arabic / multilingual later
Add an adapter for `bge-m3` or `multilingual-e5-large` (1024-d, e5 needs `query:`/`passage:` prefixes) implementing the same port with its own `model_id`/`dim`, and select it in the container.
Existing English rows stay valid under their model_id; re-embed to compare. Until that model is evaluated, Arabic answers must not be treated as semantically analysed in production.

## Evaluation plan (before enabling for a tenant)
1. Analyst labels ~200 reviews (themes from the frozen taxonomy, plus "none").
2. Run embed + assign; measure agreement (accuracy and Cohen's kappa) for `assigned`, and the share of analyst-labelled items that land in `review`/`other`.
3. Pick HIGH/LOW so `assigned` agreement >= 0.85 (same gate as the keyword classifier) and review volume is workable; store as the tenant's request parameters.
4. Check cluster labels by eye on 5 clusters (verbatim ids resolve, labels neutral). Enable only if gates pass; repeat per language/model.

## Ask your survey (RAG over one open-text question)
`POST /v1/surveys/{sid}/questions/{q}/ask` (`app/routers/ask_text.py`, pure logic in `core/rag.py`), `GET .../ask/history`. Writers/analysts only; one survey, one question at a time (no chat over all org data).

```
question (<=300 chars) + filters (date range, locale, location) + k (1..40)
  -> validate (422) -> per-user rate limit (429) -> survey visible under RLS? (else 404) -> processor 'llm' on + plan credits
  -> eligible answers = not excluded, not quality-flagged, inside filters           (same exclusions as analytics)
  -> language gate: embedder.languages vs question + answers (English only today)     -> insufficient_data(reason)
  -> stored embeddings of the CURRENT model only, source_hash must match the text     -> insufficient_data(embeddings_from_another_model)
  -> plan_retrieval: cosine, floor 0.30, >= 5 answers must pass the floor, top-k       -> insufficient_data(too_few_answers | low_similarity)   [LLM NOT called]
  -> inputs_hash seen before? -> return the stored row (cached:true, no LLM call, no new row)
  -> daily AI cap (429) -> LLMClient.answer_from_evidence(question, [{id:'e1',text}], labels)   (texts inside <data>, contact data redacted, opaque ids)
  -> verify_answer: ALL sentences pass or the whole draft is dropped
        verified | unverified (retrieved quotes only, "no verified summary") | insufficient_data(unsupported_by_evidence: model returned nothing)
  -> insert rag_answers (append-only) + analysis_runs(kind='rag_answer') + audit 'rag.ask'
```
Response: `{id, answer:[{text, source:'llm'|'structured', evidence:[{id,quote}]}], quotes, retrieved, status, reason, counts, redacted, method:'rag-1', models:{llm,embedder}, prompt_version, inputs_hash, cached}`.
`evidence.id` is an opaque `a_<hash>` (sha256 of org+survey+response id): the response id, contact details and respondent identity never leave the server and are never in the prompt.

### Guarantees
- The LLM never emits SQL, scores, counts or side effects. It returns sentences `{text, evidence_ids}`; everything else is code.
- Verifier (`core/rag.verify_answer`), per sentence: (a) every `evidence_id` was in the retrieved set shown to the model; (b) at least one id, no repeats, at most 8; (c) no digit of any script (incl. Arabic-Indic, fullwidth, superscripts, zero-width obfuscation) except through `{{ref:..}}` placeholders that code fills from computed values; `{{label:..}}` only from given labels; (d) text inside quotation marks (`"` `“”` `«»` `„“` `「」`) must be verbatim (case/whitespace-insensitive) in a *cited* answer, quotes must be balanced, non-empty, not nested; (e) 12..300 chars per sentence, 1..5 sentences, 900 total; no markup, links or `@`. One bad sentence rejects the whole answer; nothing is repaired.
- Counts are never taken from retrieval. For "how many / percentage / share" questions the answer starts with a code-written note, and if the question names a frozen theme (label or keyword) the number comes from `answer_tags` of the latest frozen taxonomy, inserted by placeholder. Counts below 5 are withheld ("fewer than 5 answers match..."). Model sentences containing digits are rejected as usual.
- Privacy: min evidence 5 (also the min-n for any grouped statement); the whole pool must hold >= 5 answers after filters; embeddings of two models are never compared (`CrossModelError` -> 409).
- Prompt injection: respondent text and the question are only ever inside `<data>` tags (a literal `</data>` is stripped), the system prompt says to ignore instructions in data, and the verifier drops any sentence citing ids outside the retrieved set or containing digits, regardless of what the model obeyed.
- Idempotent: `inputs_hash` covers survey, question id, normalised question, filters, k, embedder model/dim, LLM model, prompt version, thresholds, the retrieved ids with text hashes and the structured counts. Same hash -> stored answer, no LLM call. Insufficient-data results are stored too.
- Append-only (`0160`, `rag_answers`): api role SELECT + INSERT only, forced RLS. `app.erase_semantic_for_response` (audited definer function, also used by the retention sweep) now also removes the response id from `retrieved_ids`, replaces every sentence that cited it with a "[removed: ...]" marker, and drops it from the fallback quotes; the answer is flagged `redacted`.
- Limits per user (`ASK_LIMIT`/`ASK_WINDOW_S`, default 10/60 s), org daily AI token cap (`org_settings.ai_daily_tokens`, default 200000), plan credits.

### Limits and assumptions to calibrate
- Language: English only. `EmbeddingProvider.languages` is `{"en"}` for `fake` and `local_en`. An Arabic question, or a survey whose answers are mostly Arabic, returns `insufficient_data` with reason `question_language_unsupported` / `answer_language_unsupported` instead of weak retrieval; Arabic answers in a mixed survey are left out of the pool. A multilingual adapter (bge-m3, multilingual-e5) plugs in through the same port by declaring `languages = frozenset({"en","ar"})` after evaluation; the Arabic verifier path (RTL text, `«»` quotes, Arabic-Indic digit rejection) is already tested with the fake embedder widened.
- Uncalibrated constants in `core/rag.py`: `SIM_FLOOR = 0.30`, `MIN_EVIDENCE = 5`, `K_DEFAULT = 12`, `K_MAX = 40`, `POOL_MAX = 5000` (scoring is done in Python over at most 5000 stored vectors; above that the request is refused until an ANN index is added). The floor depends on the embedding model; calibrate it per model with an analyst-labelled sample (question -> relevant answers) so that recall at k=12 >= 0.8 and irrelevant questions fall below the floor.
- Server-written count/notice sentences are English; the UI labels, status badge, reasons and disclaimer are translated (ar, ur, hi, ru, fil; the last four are machine-drafted, needs native review).
- Location filter reads `responses.meta->>'location'` (set by the collector/kiosk meta catalog).
