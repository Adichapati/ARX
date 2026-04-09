#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
export BIND_HOST="${BIND_HOST:-127.0.0.1}"
export BIND_PORT="${BIND_PORT:-18890}"
exec uvicorn main:app --host "$BIND_HOST" --port "$BIND_PORT"
