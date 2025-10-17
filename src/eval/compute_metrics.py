"""
Compute crawler coverage and fill-rate metrics (Stage 1.2).

Inputs
- Input sites CSV with a column named 'domain'.
- One or more crawler results files in NDJSON (one JSON per line) with fields:
  domain, http_status, response_time_ms, phones (list), facebook_url, linkedin_url,
  twitter_url, instagram_url, address, error (optional string).

Outputs
- CSV summary written to data/reports/metrics.csv (one row per crawler).
- Markdown summary written to data/reports/summary.md (side-by-side comparison).

Usage:
    python src/eval/compute_metrics.py \
    --input data/inputs/sample-websites.csv \
    --results python:data/outputs/python_results.ndjson \
                node:data/outputs/node_results.ndjson \
    --csv-out data/reports/metrics.csv \
    --md-out data/reports/summary.md

Notes
- Success is defined as http_status in [200..399].
- Fill rates are computed over successful crawls only.
- If a domain has no record in results, it is considered a failure (other).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Tuple

if TYPE_CHECKING:
    from src.eval.format_adapters import CrawlerFormatAdapter

SUCCESS_MIN = 200
SUCCESS_MAX = 399


@dataclass
class CrawlRecord:
    domain: str
    http_status: Optional[int]
    response_time_ms: Optional[float]
    phones: List[str]
    social: Dict[str, Optional[str]]
    address: Optional[str]
    error: Optional[str]

    @property
    def is_success(self) -> bool:
        if self.http_status is None:
            return False
        return SUCCESS_MIN <= int(self.http_status) <= SUCCESS_MAX

    @property
    def has_phone(self) -> bool:
        return bool(self.phones)

    @property
    def has_any_social(self) -> bool:
        return any(
            bool(self.social.get(k))
            for k in ("facebook_url", "linkedin_url", "twitter_url", "instagram_url")
        )

    def has_platform(self, platform: str) -> bool:
        return bool(self.social.get(platform))

    @property
    def has_address(self) -> bool:
        return bool(self.address and str(self.address).strip())


def read_input_domains(csv_path: Path) -> List[str]:
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "domain" not in (reader.fieldnames or []):
            raise ValueError("Input CSV must contain a 'domain' column")
        return [row["domain"].strip() for row in reader if row.get("domain")] 


def parse_ndjson(file_path: Path, adapter: Optional[CrawlerFormatAdapter] = None) -> List[CrawlRecord]:
    """
    Parse NDJSON file using the specified format adapter.
    
    Args:
        file_path: Path to NDJSON file
        adapter: Format adapter to use. If None, uses AutoDetectAdapter.
    
    Returns:
        List of CrawlRecord objects
    """
    # Import here to avoid circular dependency
    if adapter is None:
        from src.eval.format_adapters import AutoDetectAdapter
        adapter = AutoDetectAdapter()
    
    records: List[CrawlRecord] = []
    if not file_path.exists():
        return records
    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            records.append(
                CrawlRecord(
                    domain=adapter.get_domain(obj),
                    http_status=_safe_int(adapter.get_http_status(obj)),
                    response_time_ms=_safe_float(adapter.get_response_time_ms(obj)),
                    phones=adapter.get_phones(obj),
                    social=adapter.get_social_urls(obj),
                    address=adapter.get_address(obj),
                    error=adapter.get_error(obj),
                )
            )
    return records


def group_best_record_by_domain(records: Iterable[CrawlRecord]) -> Dict[str, CrawlRecord]:
    """Return one record per domain.
    Strategy: prefer a successful record; otherwise keep the first seen.
    """
    by_domain: Dict[str, CrawlRecord] = {}
    for r in records:
        if not r.domain:
            continue
        existing = by_domain.get(r.domain)
        if existing is None:
            by_domain[r.domain] = r
        else:
            if not existing.is_success and r.is_success:
                by_domain[r.domain] = r
    return by_domain


def quantile(values: List[float], q: float) -> float:
    if not values:
        return math.nan
    if q <= 0:
        return min(values)
    if q >= 1:
        return max(values)
    vs = sorted(values)
    idx = int(round(q * (len(vs) - 1)))
    idx = max(0, min(idx, len(vs) - 1))
    return float(vs[idx])


def classify_failure(rec: Optional[CrawlRecord]) -> str:
    if rec is None:
        return "other"
    status = rec.http_status
    if status is None:
        if rec.error and "timeout" in str(rec.error).lower():
            return "timeout"
        if rec.error and "ssl" in str(rec.error).lower():
            return "ssl"
        return "other"
    if status == 404:
        return "404"
    if 500 <= status <= 599:
        return "5xx"
    if rec.error and "timeout" in str(rec.error).lower():
        return "timeout"
    if rec.error and "ssl" in str(rec.error).lower():
        return "ssl"
    return "other"


def compute_metrics_for_dataset(name: str, input_domains: List[str], records: List[CrawlRecord]) -> Dict[str, float]:
    by_domain = group_best_record_by_domain(records)

    total = len(input_domains)
    success_domains: List[str] = []
    success_records: List[CrawlRecord] = []
    failures: Dict[str, int] = {"timeout": 0, "404": 0, "5xx": 0, "ssl": 0, "other": 0}

    for d in input_domains:
        rec = by_domain.get(d)
        if rec and rec.is_success:
            success_domains.append(d)
            success_records.append(rec)
        else:
            failures[classify_failure(rec)] += 1

    successes = len(success_domains)
    coverage = (successes / total) * 100 if total > 0 else 0.0

    # Fill rates over successful records
    def fr(predicate) -> float:
        if successes == 0:
            return 0.0
        return (sum(1 for r in success_records if predicate(r)) / successes) * 100.0

    phone_fill = fr(lambda r: r.has_phone)
    social_fill = fr(lambda r: r.has_any_social)
    address_fill = fr(lambda r: r.has_address)
    fb_fill = fr(lambda r: r.has_platform("facebook_url"))
    li_fill = fr(lambda r: r.has_platform("linkedin_url"))
    tw_fill = fr(lambda r: r.has_platform("twitter_url"))
    ig_fill = fr(lambda r: r.has_platform("instagram_url"))

    lats = [float(r.response_time_ms) for r in success_records if r.response_time_ms is not None]
    avg_lat = mean(lats) if lats else float("nan")
    p50_lat = median(lats) if lats else float("nan")
    p95_lat = quantile(lats, 0.95) if lats else float("nan")

    return {
        "crawler": name,
        "total_sites": total,
        "successes": successes,
        "coverage_pct": round(coverage, 1),
        "phone_fill_pct": round(phone_fill, 1),
        "social_fill_pct": round(social_fill, 1),
        "address_fill_pct": round(address_fill, 1),
        "facebook_fill_pct": round(fb_fill, 1),
        "linkedin_fill_pct": round(li_fill, 1),
        "twitter_fill_pct": round(tw_fill, 1),
        "instagram_fill_pct": round(ig_fill, 1),
        "avg_latency_ms": round(avg_lat, 1) if not math.isnan(avg_lat) else float("nan"),
        "p50_latency_ms": round(p50_lat, 1) if not math.isnan(p50_lat) else float("nan"),
        "p95_latency_ms": round(p95_lat, 1) if not math.isnan(p95_lat) else float("nan"),
        "fail_timeout": failures["timeout"],
        "fail_404": failures["404"],
        "fail_5xx": failures["5xx"],
        "fail_ssl": failures["ssl"],
        "fail_other": failures["other"],
    }


def write_csv(rows: List[Dict[str, float]], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "crawler",
        "total_sites",
        "successes",
        "coverage_pct",
        "phone_fill_pct",
        "social_fill_pct",
        "address_fill_pct",
        "facebook_fill_pct",
        "linkedin_fill_pct",
        "twitter_fill_pct",
        "instagram_fill_pct",
        "avg_latency_ms",
        "p50_latency_ms",
        "p95_latency_ms",
        "fail_timeout",
        "fail_404",
        "fail_5xx",
        "fail_ssl",
        "fail_other",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_markdown(rows: List[Dict[str, float]], md_path: Path) -> None:
    md_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "| Metric | "
        + " | ".join(row["crawler"] for row in rows)
        + " |\n|---|" + "|".join(["---"] * len(rows)) + "|\n"
    )

    def line(metric: str, fmt=lambda x: x):
        return "| {m} | ".format(m=metric) + " | ".join(
            fmt(row.get(metric_key(metric), float("nan"))) for row in rows
        ) + " |\n"

    def metric_key(metric_name: str) -> str:
        mapping = {
            "Coverage (%)": "coverage_pct",
            "Phone fill (%)": "phone_fill_pct",
            "Social fill (%)": "social_fill_pct",
            "Address fill (%)": "address_fill_pct",
            "Facebook fill (%)": "facebook_fill_pct",
            "LinkedIn fill (%)": "linkedin_fill_pct",
            "Twitter fill (%)": "twitter_fill_pct",
            "Instagram fill (%)": "instagram_fill_pct",
            "Avg latency (ms)": "avg_latency_ms",
            "p50 latency (ms)": "p50_latency_ms",
            "p95 latency (ms)": "p95_latency_ms",
        }
        return mapping[metric_name]

    def fmt_pct(x):
        return f"{x:.1f}" if isinstance(x, (int, float)) and not math.isnan(float(x)) else "-"

    def fmt_ms(x):
        return f"{x:.0f}" if isinstance(x, (int, float)) and not math.isnan(float(x)) else "-"

    lines = [
        "# Crawler comparison\n\n",
        header,
        line("Coverage (%)", fmt_pct),
        line("Phone fill (%)", fmt_pct),
        line("Social fill (%)", fmt_pct),
        line("Address fill (%)", fmt_pct),
        line("Facebook fill (%)", fmt_pct),
        line("LinkedIn fill (%)", fmt_pct),
        line("Twitter fill (%)", fmt_pct),
        line("Instagram fill (%)", fmt_pct),
        line("Avg latency (ms)", fmt_ms),
        line("p50 latency (ms)", fmt_ms),
        line("p95 latency (ms)", fmt_ms),
        "\n",
        "Notes: coverage and fill rates are computed over successful crawls (HTTP 2xx-3xx).\n",
    ]
    with md_path.open("w", encoding="utf-8") as f:
        f.writelines(lines)


def _safe_int(v) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _safe_float(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_results_args(pairs: List[str]) -> List[Tuple[str, Path]]:
    results: List[Tuple[str, Path]] = []
    for p in pairs:
        if ":" not in p:
            raise ValueError(f"Invalid --results value '{p}', expected name:path")
        name, path = p.split(":", 1)
        results.append((name.strip(), Path(path.strip())))
    return results


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Compute crawler coverage and fill-rate metrics")
    ap.add_argument("--input", default="data/inputs/sample-websites.csv", help="Input CSV with 'domain' column")
    ap.add_argument(
        "--results",
        nargs="*",
        default=[
            "python:data/outputs/python_results.ndjson",
            "node:data/outputs/node_results.ndjson",
        ],
        help="List of name:path pairs for crawler results",
    )
    ap.add_argument("--csv-out", default="data/reports/metrics.csv", help="Output CSV path")
    ap.add_argument("--md-out", default="data/reports/summary.md", help="Output Markdown path")

    args = ap.parse_args(argv)

    input_domains = read_input_domains(Path(args.input))
    datasets = parse_results_args(list(args.results))

    rows: List[Dict[str, float]] = []
    for name, path in datasets:
        records = parse_ndjson(Path(path))
        metrics = compute_metrics_for_dataset(name, input_domains, records)
        rows.append(metrics)

    # Write artifacts
    write_csv(rows, Path(args.csv_out))
    write_markdown(rows, Path(args.md_out))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
