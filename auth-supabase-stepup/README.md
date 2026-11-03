# Auth: Supabase SSR login, FastAPI JWT verification, step-up MFA

**Exercised in the product?** Used in the product.

## What it does
Browser login with Supabase (server-side cookies), a BFF route that forwards calls to the API with the session token, FastAPI verification of Supabase JWTs against the project's signing keys (JWKS), a live revocation check, two-step sign-in required for administrators after a grace period, and step-up (a fresh authenticator code within five minutes) for sensitive actions such as plan changes or exports.

## When to use it
You use Supabase Auth with a separate API and need administrators on two-step sign-in.

## How it works
* Backend: `adapters/auth_supabase.py` verifies tokens and `alive()` asks the identity provider whether a session is still valid; `app/security.py` and `app/revocation.py` hold the aal2 and step-up rules; `core/ports.py` defines `AuthProvider`.
* Frontend: `proxy.ts` and `lib/supabase/*` manage the session; `components/MfaGate.tsx` and `lib/two-step.ts` gate the app; `app/api/bff/[...path]/route.ts` is the only way client code reaches the API (CSRF header, no token in browser code).

## Files

The Python package was renamed to `app` (imports look like `from app.core.verifier import ...`; the source tree is `backend/src/app/`, which contains its own `app/` sub-package) and the Postgres roles are `app_api` (runtime) and `app_owner` (tables and migrations). Capitalised brand names were replaced with `Acme`.

**src/ (copied as is; names and identifiers redacted)**

* `backend/src/app/adapters/auth_fake.py`  <- `backend/src/app/adapters/auth_fake.py`
* `backend/src/app/adapters/auth_supabase.py`  <- `backend/src/app/adapters/auth_supabase.py`
* `backend/src/app/app/deps.py`  <- `backend/src/app/app/deps.py`
* `backend/src/app/app/revocation.py`  <- `backend/src/app/app/revocation.py`
* `backend/src/app/app/security.py`  <- `backend/src/app/app/security.py`
* `backend/src/app/core/permissions.py`  <- `backend/src/app/core/permissions.py`
* `backend/src/app/core/ports.py`  <- `backend/src/app/core/ports.py`
* `frontend/app/api/bff/[...path]/route.ts`  <- `frontend/app/api/bff/[...path]/route.ts`
* `frontend/components/MfaGate.tsx`  <- `frontend/components/MfaGate.tsx`
* `frontend/lib/api-server.ts`  <- `frontend/lib/api-server.ts`
* `frontend/lib/client-api.ts`  <- `frontend/lib/client-api.ts`
* `frontend/lib/supabase/client.ts`  <- `frontend/lib/supabase/client.ts`
* `frontend/lib/supabase/env.ts`  <- `frontend/lib/supabase/env.ts`
* `frontend/lib/supabase/mfa.ts`  <- `frontend/lib/supabase/mfa.ts`
* `frontend/lib/supabase/middleware.ts`  <- `frontend/lib/supabase/middleware.ts`
* `frontend/lib/supabase/next-path.ts`  <- `frontend/lib/supabase/next-path.ts`
* `frontend/lib/supabase/server.ts`  <- `frontend/lib/supabase/server.ts`
* `frontend/lib/two-step.ts`  <- `frontend/lib/two-step.ts`
* `frontend/proxy.ts`  <- `frontend/proxy.ts`

**tests/**

* `backend/tests/integration/test_aal1_bypass.py`  <- `backend/tests/integration/test_aal1_bypass.py`
* `backend/tests/integration/test_auth_orgs.py`  <- `backend/tests/integration/test_auth_orgs.py`
* `backend/tests/integration/test_mfa_grace.py`  <- `backend/tests/integration/test_mfa_grace.py`
* `backend/tests/integration/test_revocation.py`  <- `backend/tests/integration/test_revocation.py`
* `backend/tests/support/gotrue_stub.py`  <- `backend/tests/support/gotrue_stub.py`
* `backend/tests/unit/test_auth_live_check.py`  <- `backend/tests/unit/test_auth_live_check.py`
* `backend/tests/unit/test_auth_supabase.py`  <- `backend/tests/unit/test_auth_supabase.py`
* `backend/tests/unit/test_auth_tokens.py`  <- `backend/tests/unit/test_auth_tokens.py`
* `frontend/e2e/auth-flow.spec.ts`  <- `frontend/e2e/auth-flow.spec.ts`
* `frontend/e2e/mfa-gate.spec.ts`  <- `frontend/e2e/mfa-gate.spec.ts`
* `frontend/e2e/support/auth.ts`  <- `frontend/e2e/support/auth.ts`
* `frontend/tests/api-server-mfa.test.ts`  <- `frontend/tests/api-server-mfa.test.ts`
* `frontend/tests/auth.test.tsx`  <- `frontend/tests/auth.test.tsx`
* `frontend/tests/bff.test.ts`  <- `frontend/tests/bff.test.ts`
* `frontend/tests/loaders-mfa.test.ts`  <- `frontend/tests/loaders-mfa.test.ts`
* `frontend/tests/mfa-gate.test.tsx`  <- `frontend/tests/mfa-gate.test.tsx`
* `frontend/tests/supabase-mfa.test.ts`  <- `frontend/tests/supabase-mfa.test.ts`
* `frontend/tests/supabase-session.test.ts`  <- `frontend/tests/supabase-session.test.ts`

## Depends on repository files that were NOT copied

Generated from the imports in the copied files. Each is needed (or must be replaced by your own equivalent) before this wires into a project.

* `backend/src/app/app/__init__.py`
* `backend/src/app/app/audit.py`
* `backend/src/app/app/clientip.py`
* `backend/src/app/app/scheduler.py`
* `backend/src/app/app/settings.py`
* `backend/src/app/core/__init__.py`
* `backend/src/app/core/timing.py`
* `backend/src/app/db/__init__.py`
* `backend/src/app/db/repos/__init__.py`
* `backend/src/app/db/repos/auth_sessions.py`
* `backend/src/app/db/repos/memberships.py`
* `backend/src/app/db/repos/orgs.py`
* `backend/src/app/db/repos/security_policy.py`
* `backend/src/app/db/repos/users.py`
* `frontend/app/(generated)/auth/content.tsx`
* `frontend/app/api/org/route.ts`
* `frontend/app/auth/callback/route.ts`
* `frontend/app/auth/confirm/route.ts`
* `frontend/components/Behaviors.tsx`
* `frontend/components/I18n.tsx`
* `frontend/components/e/Modal.tsx`
* `frontend/e2e/support/totp.ts`
* `frontend/lib/backend.ts`
* `frontend/lib/config.ts`
* `frontend/lib/csp.ts`
* `frontend/lib/embed.ts`
* `frontend/lib/loaders/_util.ts`
* `frontend/lib/loaders/surveys.ts`
* `frontend/lib/loaders/team.ts`
* `frontend/lib/loaders/templates.ts`
* `frontend/lib/messages.ts`
* `frontend/lib/perf-env.ts`
* `frontend/lib/perf.ts`
* `frontend/lib/route-helpers.ts`
* `frontend/tests/msw.ts`
* `frontend/tests/setup.ts`

## External dependencies

* @playwright/test
* @supabase/ssr
* @testing-library/react
* PyJWT
* asyncpg
* cryptography
* fastapi
* httpx
* msw
* next
* pytest
* react
* vitest

## Known limits and notes
* `backend/tests/support/gotrue_stub.py` stubs the identity provider; the live-check tests need it.
* The role names (`client_admin`, `analyst`, ...) and the grace period are product settings.
* Environment variable names and the Supabase project settings are documented in the original repo's docs, which were not copied.

## What was redacted or neutralised in these copies

* client_name: 2
* email: 54

No `.env` file, key, token, respondent data or account identifier is included. See the top-level `SECRET_SCAN.md`.
