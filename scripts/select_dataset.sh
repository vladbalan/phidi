#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$ROOT_DIR"

PY_BIN="python"
if [[ -x .venv/Scripts/python.exe ]]; then
  PY_BIN=".venv/Scripts/python.exe"
elif [[ -x .venv/bin/python ]]; then
  PY_BIN=".venv/bin/python"
fi

echo "[SEL] Choosing best dataset and staging..."
"$PY_BIN" src/selector/choose_dataset.py \
  --metrics data/reports/metrics.csv \
  --outputs python:data/outputs/python_results.ndjson node:data/outputs/node_results.ndjson \
  --out-dir data/staging --coverage-weight 0.6 --quality-weight 0.4

echo "[SEL] Done. See data/staging/manifest.json"
