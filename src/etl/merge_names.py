from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Dict, Iterable, List, Optional
try:
    from src.common.console import Console
except Exception:  # pragma: no cover - fallback when run as a script
    import sys as _sys
    from pathlib import Path as _Path
    _repo_root = _Path(__file__).resolve().parents[2]
    if str(_repo_root) not in _sys.path:
        _sys.path.insert(0, str(_repo_root))
    from src.common.console import Console  # type: ignore


def read_ndjson(path: Path) -> Iterable[Dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def write_ndjson(path: Path, records: Iterable[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read_names_csv(csv_path: Path) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        # Expect at least: domain, company_name
        for row in reader:
            d = (row.get("domain") or "").strip().lower()
            name = (row.get("company_name") or "").strip()
            if d and name:
                mapping[d] = name
    return mapping


def merge(records: Iterable[Dict], names_map: Dict[str, str]) -> Iterable[Dict]:
    for r in records:
        d = (r.get("domain") or "").strip().lower()
        if not d:
            yield r
            continue
        out = dict(r)
        if d in names_map:
            out["company_name"] = names_map[d]
        else:
            out.setdefault("company_name", None)
        yield out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="ETL Step 2: Merge company names into normalized crawl data")
    ap.add_argument("--input", default="data/staging/crawl_results_normalized.ndjson")
    ap.add_argument("--names", default="data/inputs/sample-websites-company-names.csv")
    ap.add_argument("--output", default="data/staging/crawl_results_merged.ndjson")
    ap.add_argument("--no-color", action="store_true", help="Disable colored output")
    args = ap.parse_args(argv)

    inp = Path(args.input)
    names_csv = Path(args.names)
    out = Path(args.output)

    # Console
    c = Console(no_color=args.no_color)
    info = c.info
    warn = c.warn
    error = c.error
    success = c.success

    # Friendly preflight checks
    if not inp.exists():
        error("[ETL] Missing normalized input: " + str(inp))
        info("[ETL] Run 'make etl' (which runs normalize first) or provide --input explicitly.")
        return 2
    if not names_csv.exists():
        error("[ETL] Missing names CSV: " + str(names_csv))
        info("[ETL] Expected columns include 'domain' and 'company_name'.")
        return 2

    names_map = read_names_csv(names_csv)
    write_ndjson(out, merge(read_ndjson(inp), names_map))
    success(f"[ETL] Wrote merged records: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
