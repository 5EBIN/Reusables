# Reusable modules

Copies of reusable building blocks from a survey-analytics product, packaged so they can be reused elsewhere. Nothing here is a runnable project: each module's README lists what it needs that was not copied.

Conventions: `src/` and `tests/` keep the original repo-relative paths, except that the Python package was renamed to `app` (the source tree is `backend/src/app/`, which has its own `app/` sub-package) and the Postgres roles to `app_api` and `app_owner`. Capitalised brand names were replaced with `Acme`. Product-specific parts are under `examples/`. Where a README's file list shows `<- path`, that is the original file with the rename applied.

| Module | What it is | In the product? |
|---|---|---|
| [llm-query-plan](llm-query-plan/README.md) | Typed query plan: the model plans, code compiles and runs | Used in the product (the "Ask your data" screen) |
| [narrative-verifier](narrative-verifier/README.md) | Narrative verifier: model-written text can only show numbers by reference | Used in the product (report summaries and the answers to "Ask your survey") |
| [approval-gate](approval-gate/README.md) | Approval gate: one place where risky writes run | Used in the product (invitations, reminders, publishing, 360 launches, case follow-ups, conversation starts) |
| [llm-provider-adapter](llm-provider-adapter/README.md) | LLM provider adapter, task layer, guard and budget | Used in the product with the OpenAI-compatible adapter on OpenRouter |
| [sentiment-and-themes](sentiment-and-themes/README.md) | Sentiment and theme tagging for open-text answers | The word-list sentiment and the theme taxonomy are used in the product |
| [retrieval-embeddings](retrieval-embeddings/README.md) | Retrieval over answers ("Ask your survey") | TESTS ONLY in practice |
| [stats-validated](stats-validated/README.md) | Statistics checked against published results | TESTS ONLY |
| [small-group-suppression](small-group-suppression/README.md) | Small-group suppression and anonymity rules | Used in the product (reports, engagement results, 360 reviews, Ask your data) |
| [response-quality-flags](response-quality-flags/README.md) | Careless-response and data-quality flags | Used in the product, run on demand from the quality screen (not on every submission) |
| [tenant-isolation-rls](tenant-isolation-rls/README.md) | Tenant isolation with Postgres row-level security | Used in the product (every table that holds organisation data) |
| [auth-supabase-stepup](auth-supabase-stepup/README.md) | Auth: Supabase SSR login, FastAPI JWT verification, step-up MFA | Used in the product |
| [send-time-checks](send-time-checks/README.md) | Consent, quiet hours and quota checked at send time | Used in the product for email |
| [audit-and-call-log](audit-and-call-log/README.md) | Audit log and model-call log | Used in the product |
| [i18n-rtl](i18n-rtl/README.md) | Interface translation and right-to-left layout (six languages) | Used in the product |
| [nav-drawer](nav-drawer/README.md) | NavDrawer: slide-over menu for narrow screens | Used in the product (the signed-in app below 1100 px) |
| [html-ui-to-code](html-ui-to-code/README.md) | HTML mockup to Next.js code maker | Used in the product as a build step: 38 pages are generated from mockups, 33 of them wired to live data |
| [rate-limiter-queue](rate-limiter-queue/README.md) | Rate limiter and Postgres job queue | Used in the product |
| [ssrf-and-input-hygiene](ssrf-and-input-hygiene/README.md) | SSRF guard, input sanitising and personal-data redaction | Used in the product |
| [repo-gates](repo-gates/README.md) | Phase gate, Makefile and import contracts | Development process (not product code) |

See `INDEX.md` for every module (set 1 and set 2) and `CHECKS.md` for the checks run over them.

## Set 2: generic modules

Added in a second import from another production Next.js / FastAPI app: generic UI, frontend and backend building blocks. Same conventions: nothing is a runnable project, each module README lists what the host must provide. Layout: each module is a folder at the root (`src/`, `tests/`, `README.md`, `deps.txt` / `deps.json`). Modules whose name ends in `-v2` sit next to a set 1 module and explain how they differ.

### Backend helper

* **agent-file-tools**: Budgeted glob / grep / read tools for a model, with path sandboxing and a plug-in point for more tools
* **body-size-limit**: ASGI middleware that refuses oversize request bodies with 413
* **hitl-approval-kit-v2**: Approval request lifecycle with status-based resolution, TTL expiry and wait-and-resume
* **llm-http-wrapper-v2**: OpenRouter-style completion over httpx with retries, schema fallback and truncation retry
* **llm-spend-meter-v2**: Exact LLM cost, model price cache and spend caps
* **object-storage-wrapper**: Thin server-side Supabase Storage client
* **owner-only-404**: FastAPI dependency: only the owner sees a resource, everyone else gets 404
* **pdf-report-engine**: Deterministic PDF report layer on reportlab: embedded fonts, header/footer, page numbers, tables, badges
* **safe-paths**: Validation and safe join/write for untrusted relative paths
* **scrub-safe-error-v2**: Secret/credential redaction for logs and stored payloads
* **soft-step**: Best-effort steps that fail loudly on programming errors
* **sse-broadcaster**: Per-key server-sent-event fan-out with bounded queues and keepalive
* **untrusted-text-fence-v2**: Fence untrusted text inside a prompt as labelled data

### Frontend library

* **diff-view**: Side-by-side diff on the Monaco diff editor, theme aware
* **file-tree**: File tree: path list to nested tree, persisted open state, react-arborist wrapper
* **password-strength**: Password analysis, strength meter and field
* **safe-markdown**: Small markdown parser and renderer that never emits raw HTML
* **visual-editor-wrapper**: GrapesJS wrapper: canvas, panels, block definitions, element property hook

### Landing page

* **hero-carousel**: Timed slide carousel with per-block reveal and reduced-motion fallback

### Testing kit

* **late-import-check**: Find function-local imports that should be module level
* **node-test-alias-loader**: Node test loader that resolves an @/ path alias to src/

### Frontend UI kit

* **app-shell-kit**: App shell pieces: layout with header and sidebar slots, profile menu, settings dialog, shell state store
* **command-palette**: Keyboard command palette (Ctrl+K) with filter and focus cycling
* **status-pill**: Generic status chip: colour + icon + word, with an example status map
* **ui-primitives**: Accessible UI primitives: Button, Dialog + focus trap, Sheet, Menu, Tabs, Table, TagInput, Toast and more
* **ui-tokens-theme**: Dark/light design tokens, theme preference and a WCAG contrast check

### Roadmap (to build, not in this set)

* Scripted LLM replay fakes (record once, replay in tests).
* A no-network test guard.
* A small inline diff view (the current diff view uses Monaco).
* PDF engine: cover page, table of contents, markdown/HTML to PDF, right-to-left text.

### Licence

MIT. The bundled IBM Plex fonts are under the SIL Open Font License (`OFL-IBM-Plex.txt`).
