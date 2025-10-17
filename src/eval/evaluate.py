"""
Stage 1.2 - Data Analysis: Run evaluation and produce reports.

This CLI loads crawler outputs, computes coverage/fill-rate/speed and
datapoints metrics, and writes both a CSV and a human-readable summary.

Outputs (defaults):
- data/reports/metrics.csv
- data/reports/summary.md

Usage:
  python src/eval/evaluate.py
  python src/eval/evaluate.py --websites data/inputs/sample-websites.csv \
    --results python:data/outputs/python_results.ndjson node:data/outputs/node_results.ndjson \
    --out-dir data/reports
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Optional, Tuple

# Reuse parsing utilities from compute_metrics to keep things DRY
try:
    # When run as a module
    from .compute_metrics import (
        CrawlRecord,
        parse_ndjson,
        read_input_domains,
        group_best_record_by_domain,
    )
except Exception:  # pragma: no cover - fallback for script execution
    import sys
    from pathlib import Path as _Path
    repo_root = _Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from src.eval.compute_metrics import (  # type: ignore
        CrawlRecord,
        parse_ndjson,
        read_input_domains,
        group_best_record_by_domain,
    )


@dataclass
class EvalRow:
    crawler: str
    total_sites: int
    successes: int
    coverage: float  # 0..1
    avg_response_time_ms: float
    total_time_seconds: float  # Total crawl time
    phone_fill_rate: float  # 0..1
    social_fill_rate: float  # 0..1
    address_fill_rate: float  # 0..1
    total_datapoints: int
    avg_datapoints_per_site: float


def compute_eval_for_dataset(name: str, input_domains: List[str], records: List[CrawlRecord], results_path: Optional[Path] = None) -> EvalRow:
    by_domain = group_best_record_by_domain(records)
    total = len(input_domains)
    success_records: List[CrawlRecord] = []

    for d in input_domains:
        rec = by_domain.get(d)
        if rec and rec.is_success:
            success_records.append(rec)

    successes = len(success_records)
    coverage = (successes / total) if total > 0 else 0.0

    # Fill rates over success_records
    def fr(predicate) -> float:
        if successes == 0:
            return 0.0
        return (sum(1 for r in success_records if predicate(r)) / successes)

    # Avg response time over success_records
    lats = [float(r.response_time_ms) for r in success_records if r.response_time_ms is not None]
    avg_response_time_ms = mean(lats) if lats else float("nan")

    # Read total_time_seconds from meta.json if available
    total_time_seconds = float("nan")
    if results_path:
        meta_path = results_path.with_suffix(".meta.json")
        if meta_path.exists():
            try:
                import json
                with meta_path.open("r", encoding="utf-8") as f:
                    meta = json.load(f)
                    total_time_seconds = float(meta.get("total_time_seconds", float("nan")))
            except Exception:
                pass  # If meta file is missing or malformed, use NaN

    phone_fill = fr(lambda r: r.has_phone)
    social_fill = fr(lambda r: r.has_any_social)
    address_fill = fr(lambda r: r.has_address)

    # Datapoints per successful site: phones count + social links present + address present(1/0)
    def datapoints_for(r: CrawlRecord) -> int:
        socials = sum(
            1 for k in ("facebook_url", "linkedin_url", "twitter_url", "instagram_url") if r.social.get(k)
        )
        return len(r.phones) + socials + (1 if r.has_address else 0)

    total_datapoints = sum(datapoints_for(r) for r in success_records)
    avg_dps = (total_datapoints / successes) if successes > 0 else 0.0

    return EvalRow(
        crawler=name,
        total_sites=total,
        successes=successes,
        coverage=coverage,
        avg_response_time_ms=avg_response_time_ms,
        total_time_seconds=total_time_seconds,
        phone_fill_rate=phone_fill,
        social_fill_rate=social_fill,
        address_fill_rate=address_fill,
        total_datapoints=total_datapoints,
        avg_datapoints_per_site=avg_dps,
    )


def write_csv(rows: List[EvalRow], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "crawler",
        "coverage",
        "avg_response_time_ms",
        "total_time_seconds",
        "phone_fill_rate",
        "social_fill_rate",
        "address_fill_rate",
        "total_datapoints",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "crawler": r.crawler,
                    "coverage": round(r.coverage, 3),
                    "avg_response_time_ms": round(r.avg_response_time_ms) if not math.isnan(r.avg_response_time_ms) else "",
                    "total_time_seconds": round(r.total_time_seconds) if not math.isnan(r.total_time_seconds) else "",
                    "phone_fill_rate": round(r.phone_fill_rate, 3),
                    "social_fill_rate": round(r.social_fill_rate, 3),
                    "address_fill_rate": round(r.address_fill_rate, 3),
                    "total_datapoints": r.total_datapoints,
                }
            )


def write_summary_md(rows: List[EvalRow], md_path: Path, coverage_weight: float = 0.6, quality_weight: float = 0.4) -> None:
    md_path.parent.mkdir(parents=True, exist_ok=True)
    # Expect exactly two rows (python, node). Handle n>=2 generically, but compute winners for first two.
    def fmt_pct(x: float) -> str:
        return f"{x*100:.1f}%"

    def fmt_ms(x: float) -> str:
        return f"{x:.0f}ms" if not math.isnan(x) else "-"

    def fmt_time(seconds: float) -> str:
        """Format seconds as Xm Xs"""
        if math.isnan(seconds):
            return "-"
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"

    def compute_quality(r: EvalRow) -> float:
        """Quality = average of fill rates (matches choose_dataset.py logic)"""
        parts = [r.phone_fill_rate, r.social_fill_rate, r.address_fill_rate]
        present = [p for p in parts if p is not None]
        return sum(present) / len(present) if present else 0.0

    def compute_score(r: EvalRow) -> float:
        """Score = coverage_weight * coverage + quality_weight * quality"""
        return coverage_weight * r.coverage + quality_weight * compute_quality(r)

    # Build lines
    lines: List[str] = ["# Crawler Comparison Report\n\n"]

    # Coverage section
    lines.append("## Coverage\n")
    for r in rows:
        lines.append(f"- {r.crawler.capitalize()}: {r.successes}/{r.total_sites} sites ({fmt_pct(r.coverage)})\n")
    # Winner: max coverage
    winner_cov = max(rows, key=lambda r: r.coverage)
    # Compare deltas against the other top competitor if exists
    if len(rows) >= 2:
        other = max([x for x in rows if x is not winner_cov], key=lambda r: r.coverage, default=None)
        if other:
            diff_sites = winner_cov.successes - other.successes
            lines.append(f"**Winner: {winner_cov.crawler.capitalize()}** (+{diff_sites} sites)\n\n")
        else:
            lines.append(f"**Winner: {winner_cov.crawler.capitalize()}**\n\n")
    else:
        lines.append(f"**Winner: {winner_cov.crawler.capitalize()}**\n\n")

    # Speed section
    lines.append("## Speed\n")
    
    # Total crawl time subsection
    lines.append("### Total Crawl Time\n")
    for r in rows:
        lines.append(f"- {r.crawler.capitalize()}: {fmt_time(r.total_time_seconds)}\n")
    # Winner: min total_time_seconds
    winner_total_time = min(rows, key=lambda r: (r.total_time_seconds if not math.isnan(r.total_time_seconds) else float('inf')))
    if len(rows) >= 2:
        worst_total_time = max(rows, key=lambda r: (r.total_time_seconds if not math.isnan(r.total_time_seconds) else -float('inf')))
        if not math.isnan(worst_total_time.total_time_seconds) and not math.isnan(winner_total_time.total_time_seconds):
            diff = worst_total_time.total_time_seconds - winner_total_time.total_time_seconds
            pct = (diff / worst_total_time.total_time_seconds) * 100 if worst_total_time.total_time_seconds else 0.0
            lines.append(f"**Winner: {winner_total_time.crawler.capitalize()}** (-{diff:.0f}s, {pct:.0f}% faster)\n\n")
        else:
            lines.append(f"**Winner: {winner_total_time.crawler.capitalize()}**\n\n")
    else:
        lines.append(f"**Winner: {winner_total_time.crawler.capitalize()}**\n\n")
    
    # Avg response time subsection
    lines.append("### Avg Response Time (per request)\n")
    for r in rows:
        lines.append(f"- {r.crawler.capitalize()}: {fmt_ms(r.avg_response_time_ms)}\n")
    # Winner: min avg_response_time_ms
    winner_speed = min(rows, key=lambda r: (r.avg_response_time_ms if not math.isnan(r.avg_response_time_ms) else float('inf')))
    if len(rows) >= 2:
        # Compute absolute and percent improvement vs. worst
        worst = max(rows, key=lambda r: (r.avg_response_time_ms if not math.isnan(r.avg_response_time_ms) else -float('inf')))
        if not math.isnan(worst.avg_response_time_ms) and not math.isnan(winner_speed.avg_response_time_ms):
            diff = worst.avg_response_time_ms - winner_speed.avg_response_time_ms
            pct = (diff / worst.avg_response_time_ms) * 100 if worst.avg_response_time_ms else 0.0
            lines.append(f"**Winner: {winner_speed.crawler.capitalize()}** (-{diff:.0f}ms, {pct:.0f}% faster)\n\n")
        else:
            lines.append(f"**Winner: {winner_speed.crawler.capitalize()}**\n\n")
    else:
        lines.append(f"**Winner: {winner_speed.crawler.capitalize()}**\n\n")

    # Data Quality section
    lines.append("## Data Quality\n")
    for r in rows:
        lines.append(f"- {r.crawler.capitalize()}: {r.avg_datapoints_per_site:.1f} datapoints/site\n")
    winner_quality = max(rows, key=lambda r: r.avg_datapoints_per_site)
    if len(rows) >= 2:
        other = max([x for x in rows if x is not winner_quality], key=lambda r: r.avg_datapoints_per_site, default=None)
        if other:
            diff = winner_quality.avg_datapoints_per_site - other.avg_datapoints_per_site
            lines.append(f"**Winner: {winner_quality.crawler.capitalize()}** (+{diff:.1f} datapoints)\n\n")
        else:
            lines.append(f"**Winner: {winner_quality.crawler.capitalize()}**\n\n")
    else:
        lines.append(f"**Winner: {winner_quality.crawler.capitalize()}**\n\n")

    # Final Scores section
    lines.append("## Final Scores\n")
    lines.append(f"*Formula: Score = {coverage_weight:.1f} × Coverage + {quality_weight:.1f} × Quality*\n\n")
    lines.append("*Quality = avg(phone_fill_rate, social_fill_rate, address_fill_rate)*\n\n")
    
    # Compute and sort scores
    scored_rows = [(r, compute_quality(r), compute_score(r)) for r in rows]
    scored_rows.sort(key=lambda x: x[2], reverse=True)
    
    for r, quality, score in scored_rows:
        lines.append(f"- **{r.crawler.capitalize()}**: {score:.6f} ")
        lines.append(f"(coverage={r.coverage:.3f}, quality={quality:.3f})\n")
    lines.append("\n")

    # Recommendation
    lines.append("## Recommendation\n")
    # Use the highest scoring crawler
    winner = scored_rows[0][0]
    winner_score = scored_rows[0][2]
    lines.append(f"**Use {winner.crawler.capitalize()} crawler** (score: {winner_score:.6f})\n")
    lines.append(f"This crawler provides the best balance of coverage ({winner.coverage:.1%}) and data quality.\n")
    
    if len(rows) >= 2:
        other = [x for x in rows if x is not winner]
        if other:
            # Check if speed difference is acceptable (<=20%)
            best_speed = min(rows, key=lambda r: (r.avg_response_time_ms if not math.isnan(r.avg_response_time_ms) else float('inf')))
            worst_speed = max(rows, key=lambda r: (r.avg_response_time_ms if not math.isnan(r.avg_response_time_ms) else -float('inf')))
            if not math.isnan(best_speed.avg_response_time_ms) and not math.isnan(worst_speed.avg_response_time_ms):
                diff = worst_speed.avg_response_time_ms - best_speed.avg_response_time_ms
                pct = (diff / worst_speed.avg_response_time_ms) * 100 if worst_speed.avg_response_time_ms else 0.0
                lines.append("Speed difference is acceptable." if pct <= 20 else "Note: large speed difference.")
    lines.append("\n")

    with md_path.open("w", encoding="utf-8") as f:
        f.writelines(lines)


def parse_results_args(pairs: List[str]) -> List[Tuple[str, Path]]:
    results: List[Tuple[str, Path]] = []
    for p in pairs:
        if ":" not in p:
            raise ValueError(f"Invalid --results value '{p}', expected name:path")
        name, path = p.split(":", 1)
        results.append((name.strip(), Path(path.strip())))
    return results


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Run Stage 1.2 evaluation and write reports")
    ap.add_argument("--websites", default="data/inputs/sample-websites.csv", help="Input CSV with 'domain' column")
    ap.add_argument(
        "--results",
        nargs="*",
        default=[
            "python:data/outputs/python_results.ndjson",
            "node:data/outputs/node_results.ndjson",
        ],
        help="List of name:path pairs for crawler results",
    )
    ap.add_argument("--out-dir", default="data/reports", help="Directory for output artifacts")
    ap.add_argument("--coverage-weight", type=float, default=0.6, help="Weight for coverage in final score (default: 0.6)")
    ap.add_argument("--quality-weight", type=float, default=0.4, help="Weight for quality in final score (default: 0.4)")
    ap.add_argument("--no-color", action="store_true", help="Disable colored output")

    args = ap.parse_args(argv)

    websites_csv = Path(args.websites)
    # Color helpers
    import sys as _sys
    COLORS = {"green": "\x1b[32m", "cyan": "\x1b[36m", "reset": "\x1b[0m"}
    use_color = (not args.no_color) and _sys.stdout.isatty()
    def _c(s: str, c: str) -> str: return f"{COLORS[c]}{s}{COLORS['reset']}" if use_color else s
    def info(msg: str) -> None: print(_c(msg, "cyan"))
    def ok(msg: str) -> None: print(_c(msg, "green"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    input_domains = read_input_domains(websites_csv)
    datasets = parse_results_args(list(args.results))

    rows: List[EvalRow] = []
    for name, path in datasets:
        records = parse_ndjson(path)
        row = compute_eval_for_dataset(name, input_domains, records, path)
        rows.append(row)

    # CSV + MD
    write_csv(rows, out_dir / "metrics.csv")
    write_summary_md(rows, out_dir / "summary.md", args.coverage_weight, args.quality_weight)
    ok("[EVAL] Wrote metrics.csv and summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
