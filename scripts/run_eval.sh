#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"

cd "$ROOT_DIR"

# Prefer existing venv if present; otherwise use system python
PY_BIN="python"
if [[ -x .venv/Scripts/python.exe ]]; then
  PY_BIN=".venv/Scripts/python.exe"
elif [[ -x .venv/bin/python ]]; then
  PY_BIN=".venv/bin/python"
fi

echo "[EVAL] Running Stage 1.2 evaluation..."
"$PY_BIN" src/eval/evaluate.py \
  --websites data/inputs/sample-websites.csv \
  --results python:data/outputs/python_results.ndjson node:data/outputs/node_results.ndjson \
  --out-dir data/reports

echo "[EVAL] Reports written to data/reports"
