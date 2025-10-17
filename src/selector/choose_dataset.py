"""
Stage 1.3 - Dataset Selection

Reads metrics from data/reports/metrics.csv, computes a weighted score per crawler,
selects the winner, copies its NDJSON to data/staging/crawl_results.ndjson, and writes a manifest.

Score = coverage_weight * coverage + quality_weight * quality
Where quality = average of (phone_fill, social_fill, address_fill)
Supported metrics.csv layouts:
- Ratios in [0..1]: coverage, phone_fill_rate, social_fill_rate, address_fill_rate
- Percentages in [0..100]: coverage_pct, phone_fill_pct, social_fill_pct, address_fill_pct

Usage:
  python src/selector/choose_dataset.py
  python src/selector/choose_dataset.py \
    --metrics data/reports/metrics.csv \
    --outputs python:data/outputs/python_results.ndjson node:data/outputs/node_results.ndjson \
    --out-dir data/staging --coverage-weight 0.6 --quality-weight 0.4
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
try:
    from src.common.console import Console
except Exception:  # pragma: no cover - fallback for script execution
    import sys as _sys
    from pathlib import Path as _Path
    _repo_root = _Path(__file__).resolve().parents[2]
    if str(_repo_root) not in _sys.path:
        _sys.path.insert(0, str(_repo_root))
    from src.common.console import Console  # type: ignore


@dataclass
class MetricsRow:
    crawler: str
    coverage: float  # 0..1
    phone_fill: float  # 0..1
    social_fill: float  # 0..1
    address_fill: float  # 0..1

    @property
    def quality(self) -> float:
        parts = [self.phone_fill, self.social_fill, self.address_fill]
        present = [p for p in parts if p is not None]
        return sum(present) / len(present) if present else 0.0


def _to_ratio(row: Dict[str, str], key_ratio: str, key_pct: str) -> Optional[float]:
    if key_ratio in row and row[key_ratio] != "":
        try:
            v = float(row[key_ratio])
            # If someone wrote 78 instead of 0.78, detect and correct
            return v / 100.0 if v > 1.5 else v
        except ValueError:
            return None
    if key_pct in row and row[key_pct] != "":
        try:
            return float(row[key_pct]) / 100.0
        except ValueError:
            return None
    return None


def read_metrics(csv_path: Path) -> List[MetricsRow]:
    rows: List[MetricsRow] = []
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            crawler = (r.get("crawler") or r.get("name") or r.get("dataset") or "").strip()
            if not crawler:
                continue
            coverage = _to_ratio(r, "coverage", "coverage_pct") or 0.0
            phone = _to_ratio(r, "phone_fill_rate", "phone_fill_pct") or 0.0
            social = _to_ratio(r, "social_fill_rate", "social_fill_pct") or 0.0
            address = _to_ratio(r, "address_fill_rate", "address_fill_pct") or 0.0
            rows.append(MetricsRow(crawler=crawler, coverage=coverage, phone_fill=phone, social_fill=social, address_fill=address))
    return rows


def parse_outputs_map(pairs: List[str]) -> Dict[str, Path]:
    out: Dict[str, Path] = {}
    for p in pairs:
        if ":" not in p:
            raise ValueError(f"Invalid --outputs value '{p}', expected name:path")
        name, path = p.split(":", 1)
        out[name.strip()] = Path(path.strip())
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def count_lines(path: Path) -> int:
    n = 0
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for _ in f:
            n += 1
    return n


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Stage 1.3 - Choose dataset based on metrics and stage it")
    ap.add_argument("--metrics", default="data/reports/metrics.csv", help="Path to metrics CSV")
    ap.add_argument(
        "--outputs",
        nargs="*",
        default=[
            "python:data/outputs/python_results.ndjson",
            "node:data/outputs/node_results.ndjson",
        ],
        help="List of name:path pairs mapping crawler to its NDJSON output",
    )
    ap.add_argument("--out-dir", default="data/staging", help="Directory to write staged dataset")
    ap.add_argument("--coverage-weight", type=float, default=0.6)
    ap.add_argument("--quality-weight", type=float, default=0.4)
    ap.add_argument("--schema-version", default="1.0")
    ap.add_argument("--no-color", action="store_true", help="Disable colored output")

    args = ap.parse_args(argv)

    metrics_csv = Path(args.metrics)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics = read_metrics(metrics_csv)
    outputs_map = parse_outputs_map(list(args.outputs))

    if not metrics:
        raise SystemExit(f"No metrics found in {metrics_csv}")

    # Compute scores
    scored: List[Tuple[str, float]] = []
    for m in metrics:
        score = args.coverage_weight * m.coverage + args.quality_weight * m.quality
        scored.append((m.crawler, score))

    # Pick winner
    winner = max(scored, key=lambda t: t[1])
    winner_name, winner_score = winner

    if winner_name not in outputs_map:
        raise SystemExit(f"No output NDJSON configured for dataset '{winner_name}'")
    source_path = outputs_map[winner_name]
    if not source_path.exists():
        raise SystemExit(f"Source NDJSON not found: {source_path}")

    target_path = out_dir / "crawl_results.ndjson"
    target_path.write_bytes(source_path.read_bytes())

    # Manifest
    checksum = sha256_file(target_path)
    record_count = count_lines(target_path)
    dataset_id = f"crawl_{datetime.now(timezone.utc).date()}_{winner_name}"
    manifest = {
        "dataset_id": dataset_id,
        "source": winner_name,
        "score": round(winner_score, 6),
        "weights": {"coverage": args.coverage_weight, "quality": args.quality_weight},
        "checksum": checksum,
        "record_count": record_count,
        "schema_version": args.schema_version,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    with (out_dir / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    c = Console(no_color=args.no_color)
    c.success(f"Winner: {winner_name} (score={winner_score:.6f})")
    c.info(f"Staged: {target_path}")
    c.info(f"Manifest: {out_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
