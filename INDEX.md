# Index

45 modules: 19 in set 1 (the original import) and 26 in set 2. Every module has a README with its interface, dependencies and the stubs a host must provide. Machine-readable list: `catalog.json`.

## Set 1

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

## Set 2

Status: new, or variant (sits next to a set 1 module and its README says how it differs).

| Module | Category | What it is | Status | Tests | Stubs |
|---|---|---|---|---|---|
| [agent-file-tools](agent-file-tools/README.md) | backend-helpers | Budgeted glob / grep / read tools for a model, with path sandboxing and a plug-in point for more tools | new | 1 | 0 |
| [body-size-limit](body-size-limit/README.md) | backend-helpers | ASGI middleware that refuses oversize request bodies with 413 | new | 0 | 0 |
| [hitl-approval-kit-v2](hitl-approval-kit-v2/README.md) | backend-helpers | Approval request lifecycle with status-based resolution, TTL expiry and wait-and-resume | variant of `approval-gate` | 1 | 2 |
| [llm-http-wrapper-v2](llm-http-wrapper-v2/README.md) | backend-helpers | OpenRouter-style completion over httpx with retries, schema fallback and truncation retry | variant of `llm-provider-adapter` | 1 | 0 |
| [llm-spend-meter-v2](llm-spend-meter-v2/README.md) | backend-helpers | Exact LLM cost, model price cache and spend caps | variant of `llm-provider-adapter` | 1 | 1 |
| [object-storage-wrapper](object-storage-wrapper/README.md) | backend-helpers | Thin server-side Supabase Storage client | new | 0 | 1 |
| [owner-only-404](owner-only-404/README.md) | backend-helpers | FastAPI dependency: only the owner sees a resource, everyone else gets 404 | new | 0 | 3 |
| [pdf-report-engine](pdf-report-engine/README.md) | backend-helpers | Deterministic PDF report layer on reportlab: embedded fonts, header/footer, page numbers, tables, badges | new | 1 | 0 |
| [safe-paths](safe-paths/README.md) | backend-helpers | Validation and safe join/write for untrusted relative paths | new | 0 | 0 |
| [scrub-safe-error-v2](scrub-safe-error-v2/README.md) | backend-helpers | Secret/credential redaction for logs and stored payloads | variant of `ssrf-and-input-hygiene` | 1 | 0 |
| [soft-step](soft-step/README.md) | backend-helpers | Best-effort steps that fail loudly on programming errors | new | 1 | 1 |
| [sse-broadcaster](sse-broadcaster/README.md) | backend-helpers | Per-key server-sent-event fan-out with bounded queues and keepalive | new | 1 | 0 |
| [untrusted-text-fence-v2](untrusted-text-fence-v2/README.md) | backend-helpers | Fence untrusted text inside a prompt as labelled data | variant of `llm-provider-adapter` | 0 | 0 |
| [diff-view](diff-view/README.md) | frontend-lib | Side-by-side diff on the Monaco diff editor, theme aware | new | 0 | 0 |
| [file-tree](file-tree/README.md) | frontend-lib | File tree: path list to nested tree, persisted open state, react-arborist wrapper | new | 1 | 0 |
| [password-strength](password-strength/README.md) | frontend-lib | Password analysis, strength meter and field | new | 0 | 0 |
| [safe-markdown](safe-markdown/README.md) | frontend-lib | Small markdown parser and renderer that never emits raw HTML | new | 0 | 0 |
| [visual-editor-wrapper](visual-editor-wrapper/README.md) | frontend-lib | GrapesJS wrapper: canvas, panels, block definitions, element property hook | new | 1 | 2 |
| [hero-carousel](hero-carousel/README.md) | landing | Timed slide carousel with per-block reveal and reduced-motion fallback | new | 0 | 0 |
| [late-import-check](late-import-check/README.md) | testing-kit | Find function-local imports that should be module level | new | 1 | 0 |
| [node-test-alias-loader](node-test-alias-loader/README.md) | testing-kit | Node test loader that resolves an @/ path alias to src/ | new | 0 | 0 |
| [app-shell-kit](app-shell-kit/README.md) | ui-kit | App shell pieces: layout with header and sidebar slots, profile menu, settings dialog, shell state store | new | 0 | 3 |
| [command-palette](command-palette/README.md) | ui-kit | Keyboard command palette (Ctrl+K) with filter and focus cycling | new | 0 | 0 |
| [status-pill](status-pill/README.md) | ui-kit | Generic status chip: colour + icon + word, with an example status map | new | 1 | 0 |
| [ui-primitives](ui-primitives/README.md) | ui-kit | Accessible UI primitives: Button, Dialog + focus trap, Sheet, Menu, Tabs, Table, TagInput, Toast and more | new | 0 | 0 |
| [ui-tokens-theme](ui-tokens-theme/README.md) | ui-kit | Dark/light design tokens, theme preference and a WCAG contrast check | new | 4 | 0 |

## Recorded as covered (not copied)

* Supabase JWT / JWKS verification: covered by `auth-supabase-stepup` (`adapters/auth_supabase.py`: single-flight JWKS refresh, issuer and required-claim checks).
* Browser Supabase session code and the generic server-to-server forwarder: covered by `auth-supabase-stepup`.
