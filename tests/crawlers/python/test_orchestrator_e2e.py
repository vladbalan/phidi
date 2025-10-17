from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from src.crawlers.python.main import chunked


def test_batching_respects_concurrency() -> None:
    seq = [str(i) for i in range(8)]
    batches = list(chunked(seq, 3))
    assert batches == [["0", "1", "2"], ["3", "4", "5"], ["6", "7"]]


def test_e2e_writes_valid_ndjson(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Prepare tiny CSV input
    csv_path = tmp_path / "sites.csv"
    csv_path.write_text("domain\nexample.com\n", encoding="utf-8")

    out_path = tmp_path / "out.ndjson"

    # Run the module via python -m to keep venv/interpreter consistent
    repo_root = Path(__file__).resolve().parents[3]
    crawler_dir = repo_root / "src/crawlers/python"
    cmd = [
        sys.executable,  # Use current Python interpreter (venv)
        str(crawler_dir / "main.py"),
        "--input",
        str(csv_path),
        "--output",
        str(out_path),
        "--concurrency",
        "1",
        "--timeout",
        "10",
    ]

    proc = subprocess.run(cmd, cwd=str(crawler_dir), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    # Basic log assertions
    assert "Python Crawler Starting" in proc.stdout
    assert "Batch 1/" in proc.stdout
    assert "Completed in" in proc.stdout

    # NDJSON: 1 line (example.com), a JSON object validated by schema
    lines = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    # load schema
    schema_path = repo_root / "schemas/crawl_result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        from jsonschema import Draft7Validator
    except Exception:  # pragma: no cover - dependency might be missing
        Draft7Validator = None
    for line in lines:
        obj = json.loads(line)
        if Draft7Validator is not None:
            Draft7Validator(schema).validate(obj)
        else:
            # Fallback: minimal checks if jsonschema isn't installed
            assert "domain" in obj and "url" in obj and "crawled_at" in obj
            assert "company_name" in obj
