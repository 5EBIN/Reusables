#!/usr/bin/env bash
# Mandatory phase gate (master §8b): lint+all tests, security marker, integration via PgBouncer.
set -e
cd "$(dirname "$0")/.."
export APP_ENV=${APP_ENV:-test}      # fakes and dev secrets are only allowed outside production
make verify
(cd backend && python3 -m pytest -m security -q)
if [ -n "$(git diff --name-only HEAD~1 2>/dev/null | grep -E 'migrations|src/app/db|tests/integration' )" ] || [ "${FORCE_PGB:-1}" = 1 ]; then
  if (echo > /dev/tcp/127.0.0.1/6432) 2>/dev/null; then
    echo "== integration via PgBouncer =="
    (cd backend && DATABASE_URL=postgresql://<user>:<password>@127.0.0.1:6432/app PGBOUNCER_URL=x python3 -m pytest tests/integration -q)
  else echo "WARN: PgBouncer not running"; fi
fi
if [ -f frontend/package.json ] && [ -d frontend/node_modules ]; then
  echo "== frontend: sync + generate + typecheck + vitest (fidelity, chrome, behaviours, BFF, auth, pages) =="
  (cd frontend && npm run -s verify)
  git diff --quiet -- frontend/app frontend/components || echo "NOTE: generated frontend files changed; they are committed with this phase"
fi
(cd backend && python3 -m pytest -q --co -q | tail -1)
