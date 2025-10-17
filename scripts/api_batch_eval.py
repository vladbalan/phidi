from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_API_URL = os.getenv("API_URL", "http://localhost:8000")
DEFAULT_CONCURRENCY = 10


def _http_get(url: str, timeout: float = 5.0) -> tuple[int, bytes]:
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=timeout) as resp:  # nosec B310
            return resp.getcode(), resp.read()
    except HTTPError as e:
        return e.code, e.read()


def _http_post_json(url: str, body: dict, timeout: float = 10.0) -> tuple[int, bytes]:
    data = json.dumps(body).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:  # nosec B310
            return resp.getcode(), resp.read()
    except HTTPError as e:
        return e.code, e.read()


@dataclass
class InputRow:
    company_name: str = ""
    website: str = ""
    phone_number: str = ""
    facebook_url: str = ""


def _normalize_key(k: str) -> str:
    return "".join(ch for ch in k.lower().strip() if ch.isalnum())


def _build_header_mapping(fieldnames: List[str]) -> Dict[str, str]:
    # Map a variety of possible column headers to canonical keys
    aliases = {
        "company_name": [
            "company_name",
            "input name",
            "input_name",
            "name",
            "company",
            "inputcompany",
            "input_company",
        ],
        "website": [
            "website",
            "input website",
            "input_website",
            "domain",
            "url",
            "input url",
            "input_url",
        ],
        "phone_number": [
            "phone_number",
            "phone",
            "input phone",
            "input_phone",
            "phonenumber",
            "phone number",
        ],
        "facebook_url": [
            "facebook_url",
            "facebook",
            "input_facebook",
            "facebook url",
            "facebookurl",
        ],
    }

    norm_to_orig: Dict[str, str] = {_normalize_key(k): k for k in fieldnames}
    mapping: Dict[str, str] = {}
    for canonical, keys in aliases.items():
        for key in keys:
            nk = _normalize_key(key)
            if nk in norm_to_orig:
                mapping[canonical] = norm_to_orig[nk]
                break
    return mapping


def read_input_csv(path: str) -> Iterable[InputRow]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return
        mapping = _build_header_mapping(list(reader.fieldnames))
        missing = [k for k in ("company_name", "website", "phone_number", "facebook_url") if k not in mapping]
        if missing:
            print(f"[API-BATCH][INFO] Using best-effort header mapping. Missing canonical keys: {missing}")
        for i, raw in enumerate(reader, start=1):
            def _g(canonical: str) -> str:
                src = mapping.get(canonical)
                if not src:
                    return ""
                v = raw.get(src, "")
                return ("" if v is None else str(v)).strip()

            row = InputRow(
                company_name=_g("company_name"),
                website=_g("website"),
                phone_number=_g("phone_number"),
                facebook_url=_g("facebook_url"),
            )
            # Skip rows with no usable fields
            if not any([row.company_name, row.website, row.phone_number, row.facebook_url]):
                continue
            yield row


def ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def health_check(api_url: str, retries: int = 15, delay: float = 0.3) -> None:
    url = f"{api_url}/healthz"
    last_err: Optional[BaseException] = None
    for _ in range(retries):
        try:
            status, _ = _http_get(url)
            if status == 200:
                return
        except URLError as e:  # network not ready yet
            last_err = e
        time.sleep(delay)
    if last_err is not None:
        raise SystemExit(f"[API-BATCH] Health check failed for {url}: {last_err}")
    raise SystemExit(f"[API-BATCH] Health check failed for {url} (status != 200)")


# Async HTTP client implementation
try:
    import aiohttp  # type: ignore
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


@dataclass
class MatchResult:
    """Result of a single match request."""
    input_company: str
    input_website: str
    matched: bool
    confidence: float
    matched_company: str
    matched_domain: str
    response_time_ms: float
    error: Optional[str] = None


async def _async_post_match(
    session: Any,
    api_url: str,
    payload: Dict[str, Any],
    timeout: float,
) -> Tuple[bool, float, Optional[Dict[str, Any]], float, Optional[str]]:
    """Async POST to /match endpoint.
    
    Returns: (matched, confidence, company_data, response_time_ms, error)
    """
    url = f"{api_url}/match"
    t0 = time.perf_counter()
    
    try:
        async with session.post(url, json=payload, timeout=timeout) as resp:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            data = await resp.json()
            
            matched = bool(data.get("match_found", False))
            confidence = float(data.get("confidence", 0.0) or 0.0)
            company = data.get("company")
            
            return matched, confidence, company, dt_ms, None
            
    except asyncio.TimeoutError:
        dt_ms = (time.perf_counter() - t0) * 1000.0
        return False, 0.0, None, dt_ms, "timeout"
    except Exception as e:
        dt_ms = (time.perf_counter() - t0) * 1000.0
        return False, 0.0, None, dt_ms, str(e)


async def _process_batch_async(
    rows: List[InputRow],
    api_url: str,
    timeout: float,
    concurrency: int,
) -> List[MatchResult]:
    """Process batch of rows with controlled concurrency."""
    if not AIOHTTP_AVAILABLE:
        raise RuntimeError("aiohttp is required for async mode. Install with: pip install aiohttp")
    
    semaphore = asyncio.Semaphore(concurrency)
    results: List[MatchResult] = []
    
    async def process_one(row: InputRow, session: Any) -> MatchResult:
        """Process single row with semaphore control."""
        async with semaphore:
            payload = {
                "company_name": row.company_name,
                "website": row.website,
                "phone_number": row.phone_number,
                "facebook_url": row.facebook_url,
            }
            
            matched, confidence, company, dt_ms, error = await _async_post_match(
                session, api_url, payload, timeout
            )
            
            matched_company = ""
            matched_domain = ""
            if company:
                matched_company = company.get("company_name") or company.get("name") or ""
                matched_domain = company.get("domain") or ""
            
            return MatchResult(
                input_company=row.company_name,
                input_website=row.website,
                matched=matched,
                confidence=confidence,
                matched_company=matched_company,
                matched_domain=matched_domain,
                response_time_ms=dt_ms,
                error=error,
            )
    
    # Create session with connection pooling
    timeout_obj = aiohttp.ClientTimeout(total=timeout)
    connector = aiohttp.TCPConnector(limit=concurrency, limit_per_host=concurrency)
    
    async with aiohttp.ClientSession(timeout=timeout_obj, connector=connector) as session:
        tasks = [process_one(row, session) for row in rows]
        results = await asyncio.gather(*tasks)
    
    return results


async def run_async(
    input_csv: str,
    out_csv: str,
    out_summary: str,
    api_url: str,
    limit: Optional[int] = None,
    timeout: float = 10.0,
    concurrency: int = DEFAULT_CONCURRENCY,
    out_report: Optional[str] = None,
) -> None:
    """Async implementation of batch evaluation."""
    print(f"[API-BATCH] API_URL: {api_url}")
    print(f"[API-BATCH] Concurrency: {concurrency}")
    print(f"[API-BATCH] Reading: {input_csv}")
    
    # Health check (sync)
    health_check(api_url)
    
    # Read all rows
    rows = list(read_input_csv(input_csv))
    if limit:
        rows = rows[:limit]
    
    total = len(rows)
    print(f"[API-BATCH] Processing {total} rows...")
    
    # Process batch async
    t_start = time.perf_counter()
    results = await _process_batch_async(rows, api_url, timeout, concurrency)
    t_total = (time.perf_counter() - t_start) * 1000.0
    
    # Aggregate metrics
    matches_found = sum(1 for r in results if r.matched)
    high = sum(1 for r in results if r.matched and r.confidence >= 0.9)
    medium = sum(1 for r in results if r.matched and 0.7 <= r.confidence < 0.9)
    low = sum(1 for r in results if r.matched and r.confidence < 0.7)
    no_matches = total - matches_found
    sum_conf = sum(r.confidence for r in results)
    avg_conf = sum_conf / total if total else 0.0
    
    resp_times_ms = [r.response_time_ms for r in results]
    avg_ms = sum(resp_times_ms) / len(resp_times_ms) if resp_times_ms else 0.0
    
    # Convert to output format
    results_rows = [
        {
            "input_company": r.input_company,
            "input_website": r.input_website,
            "matched": str(r.matched).lower(),
            "confidence": f"{r.confidence:.4f}",
            "matched_company": r.matched_company,
            "matched_domain": r.matched_domain,
        }
        for r in results
    ]
    
    # Write outputs
    ensure_dir(out_csv)
    ensure_dir(out_summary)
    
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "input_company",
            "input_website",
            "matched",
            "confidence",
            "matched_company",
            "matched_domain",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results_rows)
    
    summary = {
        "total_queries": total,
        "matches_found": matches_found,
        "match_rate": (matches_found / total) if total else 0.0,
        "high_confidence_matches": high,
        "medium_confidence_matches": medium,
        "low_confidence_matches": low,
        "no_matches": no_matches,
        "avg_confidence": avg_conf,
        "avg_response_time_ms": round(avg_ms, 2),
        "total_time_ms": round(t_total, 2),
        "throughput_req_per_sec": round(total / (t_total / 1000.0), 2) if t_total > 0 else 0.0,
    }
    
    with open(out_summary, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    
    # Write markdown report if requested
    if out_report:
        write_markdown_report(
            out_path=out_report,
            summary=summary,
            results_rows=results_rows,
            resp_times_ms=resp_times_ms,
            input_csv=input_csv,
            api_url=api_url,
        )
    
    # Log errors if any
    errors = [r for r in results if r.error]
    if errors:
        print(f"[API-BATCH] Warnings: {len(errors)} requests had errors")
        for r in errors[:3]:  # Show first 3
            print(f"  - {r.input_company}: {r.error}")
    
    print("[API-BATCH] Done.")
    print(f"[API-BATCH] Total requests: {total}")
    print(f"[API-BATCH] Total time:     {t_total:.0f} ms")
    print(f"[API-BATCH] Throughput:     {summary['throughput_req_per_sec']:.1f} req/s")
    print(f"[API-BATCH] Avg per request: {avg_ms:.1f} ms")
    print(f"[API-BATCH] Results CSV:    {out_csv}")
    print(f"[API-BATCH] Summary JSON:  {out_summary}")
    if out_report:
        print(f"[API-BATCH] Report MD:     {out_report}")
    print(
        f"[API-BATCH] Matches: {matches_found}/{total} "
        f"({summary['match_rate']:.3f}), avg_conf={avg_conf:.4f}, avg_ms={avg_ms:.1f}"
    )
    
    # Print formatted report to terminal if generated
    if out_report:
        _print_formatted_report(summary, results_rows, resp_times_ms)


def categorize_confidence(conf: float) -> str:
    # Keep thresholds aligned with API metrics labeling
    if conf >= 0.9:
        return "high"
    if conf >= 0.7:
        return "medium"
    return "low"


def write_markdown_report(
    out_path: str,
    summary: Dict[str, Any],
    results_rows: List[Dict[str, Any]],
    resp_times_ms: List[float],
    input_csv: str,
    api_url: str,
) -> None:
    """Generate a human-readable markdown report from evaluation results."""
    from datetime import datetime
    
    total = summary["total_queries"]
    high = summary["high_confidence_matches"]
    medium = summary["medium_confidence_matches"]
    low = summary["low_confidence_matches"]
    no_match = summary["no_matches"]
    
    # Calculate percentages
    high_pct = (high / total * 100) if total else 0
    medium_pct = (medium / total * 100) if total else 0
    low_pct = (low / total * 100) if total else 0
    no_match_pct = (no_match / total * 100) if total else 0
    
    # Performance stats
    sorted_times = sorted(resp_times_ms) if resp_times_ms else [0.0]
    fastest = min(sorted_times)
    slowest = max(sorted_times)
    median = sorted_times[len(sorted_times) // 2]
    
    # Sample high-confidence matches (up to 3)
    high_conf_samples = [
        r for r in results_rows 
        if r["matched"] == "true" and float(r["confidence"]) >= 0.9
    ][:3]
    
    # Sample no-matches (up to 10)
    no_match_samples = [
        r for r in results_rows 
        if r["matched"] == "false"
    ][:10]
    
    # Build markdown
    lines = [
        "# API Match Evaluation Report",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Input File:** {input_csv}  ",
        f"**API Endpoint:** {api_url}",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| **Total Queries** | {total} |",
        f"| **Matches Found** | {summary['matches_found']} |",
        f"| **Match Rate** | {summary['match_rate']:.1%} |",
        f"| **Average Confidence** | {summary['avg_confidence']:.4f} |",
        f"| **Average Response Time** | {summary['avg_response_time_ms']:.1f} ms |",
        "",
        "---",
        "",
        "## Match Quality Breakdown",
        "",
        "| Confidence Level | Count | Percentage |",
        "|-----------------|-------|------------|",
        f"| 🟢 High (≥0.9) | {high} | {high_pct:.1f}% |",
        f"| 🟡 Medium (≥0.7) | {medium} | {medium_pct:.1f}% |",
        f"| 🔴 Low (<0.7) | {low} | {low_pct:.1f}% |",
        f"| ⚪ No Match | {no_match} | {no_match_pct:.1f}% |",
        "",
        "---",
        "",
        "## Performance",
        "",
        f"- **Fastest Response:** {fastest:.1f} ms",
        f"- **Slowest Response:** {slowest:.1f} ms",
        f"- **Median Response:** {median:.1f} ms",
        "",
    ]
    
    # Add high-confidence samples if available
    if high_conf_samples:
        lines.extend([
            "---",
            "",
            "## Sample Matches",
            "",
            f"### High Confidence Matches ({len(high_conf_samples)} example{'s' if len(high_conf_samples) > 1 else ''})",
            "",
        ])
        for i, row in enumerate(high_conf_samples, 1):
            input_co = row["input_company"] or "(no name)"
            input_web = row["input_website"] or "(no website)"
            matched_co = row["matched_company"] or "(no name)"
            matched_dom = row["matched_domain"] or "(no domain)"
            conf = row["confidence"]
            lines.extend([
                f"{i}. **Input:** \"{input_co}\" ({input_web})  ",
                f"   **Matched:** {matched_co} ({matched_dom})  ",
                f"   **Confidence:** {conf}",
                "",
            ])
    
    # Add no-match samples if available
    if no_match_samples:
        lines.extend([
            f"### No Matches ({len(no_match_samples)} example{'s' if len(no_match_samples) > 1 else ''})",
            "",
        ])
        for i, row in enumerate(no_match_samples, 1):
            input_co = row["input_company"] or "(no name)"
            input_web = row["input_website"] or "(no website)"
            lines.extend([
                f"{i}. **Input:** \"{input_co}\" ({input_web})  ",
                f"   **Reason:** No match found",
                "",
            ])
    
    # Write to file
    ensure_dir(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _print_formatted_report(
    summary: Dict[str, Any],
    results_rows: List[Dict[str, Any]],
    resp_times_ms: List[float],
) -> None:
    """Print a formatted report to the terminal (not raw markdown)."""
    # ANSI color codes
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    RESET = "\033[0m"
    DIM = "\033[2m"
    
    total = summary["total_queries"]
    high = summary["high_confidence_matches"]
    medium = summary["medium_confidence_matches"]
    low = summary["low_confidence_matches"]
    no_match = summary["no_matches"]
    matches = summary["matches_found"]
    
    # Calculate percentages
    high_pct = (high / total * 100) if total else 0
    medium_pct = (medium / total * 100) if total else 0
    low_pct = (low / total * 100) if total else 0
    no_match_pct = (no_match / total * 100) if total else 0
    
    # Performance stats
    sorted_times = sorted(resp_times_ms) if resp_times_ms else [0.0]
    fastest = min(sorted_times)
    slowest = max(sorted_times)
    median = sorted_times[len(sorted_times) // 2]
    
    # Sample high-confidence matches (up to 3)
    high_conf_samples = [
        r for r in results_rows 
        if r["matched"] == "true" and float(r["confidence"]) >= 0.9
    ][:3]
    
    # Sample no-matches (up to 10)
    no_match_samples = [
        r for r in results_rows 
        if r["matched"] == "false"
    ][:10]
    
    # Print formatted report
    print("\n" + "=" * 80)
    print(f"{BOLD}{CYAN}API Match Evaluation Report{RESET}")
    print("=" * 80)
    
    # Summary section
    print(f"\n{BOLD}Summary:{RESET}")
    print(f"  Total Queries:        {BOLD}{total}{RESET}")
    print(f"  Matches Found:        {BOLD}{GREEN}{matches}{RESET} ({summary['match_rate']:.1%})")
    print(f"  Average Confidence:   {summary['avg_confidence']:.4f}")
    print(f"  Average Response:     {summary['avg_response_time_ms']:.1f} ms")
    
    # Match quality breakdown
    print(f"\n{BOLD}Match Quality:{RESET}")
    print(f"  {GREEN}🟢 High (≥0.9):{RESET}     {high:3d}  ({high_pct:5.1f}%)")
    print(f"  {YELLOW}🟡 Medium (≥0.7):{RESET}   {medium:3d}  ({medium_pct:5.1f}%)")
    print(f"  {RED}🔴 Low (<0.7):{RESET}      {low:3d}  ({low_pct:5.1f}%)")
    print(f"  {DIM}⚪ No Match:{RESET}       {no_match:3d}  ({no_match_pct:5.1f}%)")
    
    # Performance
    print(f"\n{BOLD}Performance:{RESET}")
    print(f"  Fastest:  {fastest:6.1f} ms")
    print(f"  Median:   {median:6.1f} ms")
    print(f"  Slowest:  {slowest:6.1f} ms")
    
    # Sample matches
    if high_conf_samples:
        print(f"\n{BOLD}High Confidence Matches ({len(high_conf_samples)} sample{'s' if len(high_conf_samples) > 1 else ''}):{RESET}")
        for i, row in enumerate(high_conf_samples, 1):
            input_co = row["input_company"] or "(no name)"
            input_web = row["input_website"] or "(no website)"
            matched_co = row["matched_company"] or "(no name)"
            matched_dom = row["matched_domain"] or "(no domain)"
            conf = row["confidence"]
            print(f"  {i}. {GREEN}✓{RESET} {BOLD}{input_co}{RESET} ({input_web})")
            print(f"     → {matched_co} ({matched_dom}) {DIM}[conf: {conf}]{RESET}")
    
    # No matches
    if no_match_samples:
        print(f"\n{BOLD}No Matches ({len(no_match_samples)} sample{'s' if len(no_match_samples) > 1 else ''}):{RESET}")
        for i, row in enumerate(no_match_samples, 1):
            input_co = row["input_company"] or "(no name)"
            input_web = row["input_website"] or "(no website)"
            print(f"  {i}. {RED}✗{RESET} {input_co} ({input_web})")
    
    print("\n" + "=" * 80 + "\n")


def run(
    input_csv: str,
    out_csv: str,
    out_summary: str,
    api_url: str,
    limit: Optional[int] = None,
    timeout: float = 10.0,
    pause: float = 0.0,
    out_report: Optional[str] = None,
) -> None:
    print(f"[API-BATCH] API_URL: {api_url}")
    print(f"[API-BATCH] Reading: {input_csv}")
    health_check(api_url)

    results_rows: List[Dict[str, Any]] = []

    total = 0
    matches_found = 0
    high = 0
    medium = 0
    low = 0
    no_matches = 0
    sum_conf = 0.0
    resp_times_ms: List[float] = []

    skipped_empty = 0
    for row in read_input_csv(input_csv):
        if limit is not None and total >= limit:
            break

        payload = {
            "company_name": row.company_name,
            "website": row.website,
            "phone_number": row.phone_number,
            "facebook_url": row.facebook_url,
        }

        total += 1
        t0 = time.perf_counter()
        try:
            status, data = _http_post_json(f"{api_url}/match", payload, timeout=timeout)
        except URLError as e:
            # Treat network errors as no-match but continue
            status, data = 599, b"{}"
            print(f"[API-BATCH][WARN] Request failed for '{row.company_name}' ({row.website}): {e}")
        dt_ms = (time.perf_counter() - t0) * 1000.0
        resp_times_ms.append(dt_ms)

        matched = False
        confidence = 0.0
        matched_company = None
        matched_domain = None

        try:
            obj = json.loads(data.decode("utf-8", errors="ignore")) if data else {}
            matched = bool(obj.get("match_found", False))
            confidence = float(obj.get("confidence", 0.0) or 0.0)
            comp = obj.get("company") or {}
            matched_company = comp.get("company_name") or comp.get("name")
            matched_domain = comp.get("domain")
        except Exception as e:
            print(f"[API-BATCH][WARN] Failed to parse JSON response for '{row.company_name}': {e}")

        # Update metrics
        sum_conf += confidence
        if matched:
            matches_found += 1
            bucket = categorize_confidence(confidence)
            if bucket == "high":
                high += 1
            elif bucket == "medium":
                medium += 1
            else:
                low += 1
        else:
            no_matches += 1

        results_rows.append(
            {
                "input_company": row.company_name,
                "input_website": row.website,
                "matched": str(matched).lower(),  # keep as 'true'/'false' for CSV readability
                "confidence": f"{confidence:.4f}",
                "matched_company": matched_company or "",
                "matched_domain": matched_domain or "",
            }
        )

        if total % 50 == 0:
            print(f"[API-BATCH] Progress: {total} rows... (avg {average(resp_times_ms):.1f} ms/req)")

        if pause > 0:
            time.sleep(pause)

    # Write outputs
    ensure_dir(out_csv)
    ensure_dir(out_summary)

    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "input_company",
            "input_website",
            "matched",
            "confidence",
            "matched_company",
            "matched_domain",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results_rows)

    avg_conf = (sum_conf / total) if total else 0.0
    avg_ms = average(resp_times_ms)

    summary = {
        "total_queries": total,
        "matches_found": matches_found,
        "match_rate": (matches_found / total) if total else 0.0,
        "high_confidence_matches": high,
        "medium_confidence_matches": medium,
        "low_confidence_matches": low,
        "no_matches": no_matches,
        "avg_confidence": avg_conf,
        "avg_response_time_ms": round(avg_ms, 2),
    }

    with open(out_summary, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Write markdown report if requested
    if out_report:
        write_markdown_report(
            out_path=out_report,
            summary=summary,
            results_rows=results_rows,
            resp_times_ms=resp_times_ms,
            input_csv=input_csv,
            api_url=api_url,
        )

    print("[API-BATCH] Done.")
    print(f"[API-BATCH] Total requests: {total}")
    print(f"[API-BATCH] Total time:     {sum(resp_times_ms):.0f} ms")
    print(f"[API-BATCH] Avg per request: {avg_ms:.1f} ms")
    print(f"[API-BATCH] Results CSV:    {out_csv}")
    print(f"[API-BATCH] Summary JSON:  {out_summary}")
    if out_report:
        print(f"[API-BATCH] Report MD:     {out_report}")
    print(
        f"[API-BATCH] Matches: {matches_found}/{total} "
        f"({summary['match_rate']:.3f}), avg_conf={avg_conf:.4f}, avg_ms={avg_ms:.1f}"
    )
    
    # Print formatted report to terminal if generated
    if out_report:
        _print_formatted_report(summary, results_rows, resp_times_ms)


def average(values: List[float]) -> float:
    return (sum(values) / len(values)) if values else 0.0


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Batch-evaluate the /match API over an input CSV and write results + summary.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--input", default="data/inputs/api-input-sample.csv", help="Input CSV path")
    p.add_argument(
        "--csv-out",
        default="data/reports/api_match_results.csv",
        help="Output CSV with per-row results",
    )
    p.add_argument(
        "--summary-out",
        default="data/reports/api_match_summary.json",
        help="Output JSON summary path",
    )
    p.add_argument(
        "--report-out",
        default=None,
        help="Output human-readable markdown report (optional)",
    )
    p.add_argument("--api-url", default=DEFAULT_API_URL, help="Base URL of the API (or set API_URL)")
    p.add_argument("--limit", type=int, default=None, help="Process only first N rows (debug)")
    p.add_argument("--timeout", type=float, default=10.0, help="Request timeout in seconds")
    p.add_argument("--pause", type=float, default=0.0, help="Delay between requests (sync mode only)")
    p.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help="Max concurrent requests (async mode only)",
    )
    p.add_argument(
        "--sync",
        action="store_true",
        help="Use synchronous mode (default: async if aiohttp available)",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    
    # Determine execution mode
    use_async = not args.sync and AIOHTTP_AVAILABLE
    
    if use_async:
        # Run async version
        asyncio.run(
            run_async(
                input_csv=args.input,
                out_csv=args.csv_out,
                out_summary=args.summary_out,
                api_url=args.api_url,
                limit=args.limit,
                timeout=args.timeout,
                concurrency=args.concurrency,
                out_report=args.report_out,
            )
        )
    else:
        # Run sync version (fallback)
        if not args.sync and not AIOHTTP_AVAILABLE:
            print("[API-BATCH] aiohttp not available, falling back to sync mode")
            print("[API-BATCH] Install aiohttp for better performance: pip install aiohttp")
        
        run(
            input_csv=args.input,
            out_csv=args.csv_out,
            out_summary=args.summary_out,
            api_url=args.api_url,
            limit=args.limit,
            timeout=args.timeout,
            pause=args.pause,
            out_report=args.report_out,
        )


if __name__ == "__main__":
    main()
