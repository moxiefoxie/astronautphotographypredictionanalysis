#!/bin/sh
# Run from any directory. The API and frontend stay together; worker is separate.
set -eu
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/backend${PYTHONPATH:+:$PYTHONPATH}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$PWD/runtime/dashboard.db}"
export INFERENCE_ENABLED="${INFERENCE_ENABLED:-0}"
.venv/bin/python -m app.import_benchmark
.venv/bin/python -m app.import_mediterranean
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 &
api_pid=$!
trap 'kill "$api_pid" 2>/dev/null || true' EXIT INT TERM
npm run dev -- --host 127.0.0.1
