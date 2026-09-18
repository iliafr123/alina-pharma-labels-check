#!/usr/bin/env bash
# Regression gate. Run this before every deploy to production:
#
#     bash scripts/predeploy.sh
#
# It needs no database, no Redis, no S3 and no provider API key - the backend
# suite runs against a throwaway SQLite file and every outbound call is stubbed,
# so it is safe and free to run as often as you like.
#
# Exit code 0 means the branch is safe to push to master (Railway deploys from
# master automatically). Any non-zero exit means: do not deploy.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FAILED=0
step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
fail() { printf '\033[31mFAIL: %s\033[0m\n' "$1"; FAILED=1; }
ok()   { printf '\033[32mOK: %s\033[0m\n' "$1"; }

# --- backend -----------------------------------------------------------------
step "Backend: pytest"
if [ -x "backend/.venv/Scripts/python.exe" ]; then
  PY="backend/.venv/Scripts/python.exe"          # Windows dev checkout
elif [ -x "backend/.venv/bin/python" ]; then
  PY="backend/.venv/bin/python"                  # Linux/macOS venv
else
  PY="python"                                    # CI, where deps are preinstalled
fi
( cd backend && "../$PY" -m pytest ) && ok "backend tests" || fail "backend tests"

# --- frontend ----------------------------------------------------------------
step "Frontend: unit tests"
( cd frontend && npm test --silent ) && ok "frontend tests" || fail "frontend tests"

step "Frontend: type check + production build"
# `npm run build` is `tsc -b && vite build`: a type error or a broken import here
# is exactly the class of bug that otherwise only shows up as a blank page in prod.
( cd frontend && npm run build ) && ok "frontend build" || fail "frontend build"

# --- summary -----------------------------------------------------------------
printf '\n'
if [ "$FAILED" -ne 0 ]; then
  printf '\033[31m========================================\n'
  printf ' NOT SAFE TO DEPLOY - see failures above\n'
  printf '========================================\033[0m\n'
  exit 1
fi
printf '\033[32m====================================\n'
printf ' All checks passed - safe to deploy\n'
printf '====================================\033[0m\n'
