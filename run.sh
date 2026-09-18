#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
set -a
[[ -f .env ]] && . ./.env
set +a
export ADMIN_PASSWORD="${ADMIN_PASSWORD:-changeme}"
export SESSION_SECRET="${SESSION_SECRET:-$(python3 -c 'import secrets;print(secrets.token_hex(32))')}"
export PORTAL_PUBLIC_URL="${PORTAL_PUBLIC_URL:-http://127.0.0.1:8080}"
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
