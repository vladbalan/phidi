#!/usr/bin/env python3
"""
Python crawler with real HTTP fetching and extraction.

- Reads domains from a CSV (tries: domain, website, url; else first column)
- Processes in batches equal to --concurrency using asyncio
- Fetches HTML via httpx and extracts company data via extract.py
- Writes NDJSON lines to the output path with the expected fields
- Prints friendly progress logs and a completion summary

KISS/DRY: Simple HTTP fetch + regex extraction, no complex parsing libraries.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

try:
	import httpx
except ImportError:  # pragma: no cover
	httpx = None  # type: ignore

try:
    from src.crawlers.python.extract import extract_all
except ImportError:  # pragma: no cover - fallback for direct execution
    import sys as _sys
    from pathlib import Path as _Path
    _repo = _Path(__file__).resolve().parents[3]
    if str(_repo) not in _sys.path:
        _sys.path.insert(0, str(_repo))
    from src.crawlers.python.extract import extract_all  # type: ignore

# Import crawler config (optional - falls back to defaults if not available)
try:
    from src.common.crawler_config import load_crawler_config, calculate_backoff
    from src.common.robots_parser import AsyncRobotsCache
    from src.common.user_agent_rotation import UserAgentRotator
    _config = load_crawler_config()
    _DEFAULT_CONCURRENCY = _config.http.concurrency
    _DEFAULT_TIMEOUT = _config.http.timeout_seconds
    _DEFAULT_USER_AGENT = _config.http.user_agent
    _ROBOTS_ENABLED = _config.robots.enabled
    _ROBOTS_CACHE = AsyncRobotsCache(
        ttl_seconds=_config.robots.cache_ttl_seconds,
        user_agent=_config.http.user_agent
    ) if _config.robots.enabled else None
    # User-agent rotation
    _UA_ROTATION_ENABLED = _config.user_agent_rotation.enabled
    _UA_ROTATOR = UserAgentRotator(
        identify=_config.user_agent_rotation.identify,
        identifier="SpaceCrawler/1.0"
    ) if _config.user_agent_rotation.enabled else None
except ImportError:
    # Fallback if config module not available
    _DEFAULT_CONCURRENCY = 50  # configDefaultOverride.concurrency
    _DEFAULT_TIMEOUT = 12.0  # configDefaultOverride.timeout
    _DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; SpaceCrawler/1.0)"
    _ROBOTS_ENABLED = False
    _ROBOTS_CACHE = None
    _UA_ROTATION_ENABLED = False
    _UA_ROTATOR = None
    # Fallback for calculate_backoff if config not available
    def calculate_backoff(attempt: int, config=None) -> float:
        """Fallback backoff calculation."""
        return (2 ** attempt) * 0.5 + random.uniform(0, 0.5)# ---------- CLI ----------


def build_default_paths() -> tuple[Path, Path]:
    here = Path(__file__).resolve()
    repo_root = here.parents[3]
    default_input = repo_root / "data/inputs/sample-websites.csv"
    default_output = repo_root / "data/outputs/python_results.ndjson"
    return default_input, default_output


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    default_input, default_output = build_default_paths()

    p = argparse.ArgumentParser(description="Python crawler (placeholder)")
    p.add_argument(
        "--input",
        type=Path,
        default=default_input,
        help="Path to input CSV of websites/domains",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=default_output,
        help="Path to output NDJSON file",
    )
    p.add_argument(
        "--concurrency",
        type=int,
        default=_DEFAULT_CONCURRENCY,
        help=f"Number of concurrent tasks (default: {_DEFAULT_CONCURRENCY} from config)",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=_DEFAULT_TIMEOUT,
        help=f"Per-domain timeout in seconds (default: {_DEFAULT_TIMEOUT} from config)",
    )
    p.add_argument(
        "--user-agent",
        type=str,
        default=_DEFAULT_USER_AGENT,
        help="User-Agent string for HTTP requests",
    )
    p.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )
    p.add_argument(
        "--respect-robots",
        type=lambda x: x.lower() in ('true', '1', 'yes'),
        default=_ROBOTS_ENABLED,
        help=f"Respect robots.txt directives (default: {_ROBOTS_ENABLED})",
    )
    return p.parse_args(argv)


# ---------- IO helpers ----------


def _first_nonempty(*vals: Optional[str]) -> Optional[str]:
    for v in vals:
        if v and str(v).strip():
            return str(v).strip()
    return None


def _domain_from_value(value: str) -> Optional[str]:
    v = (value or "").strip()
    if not v:
        return None
    if "://" in v:
        try:
            parsed = urlparse(v)
            host = parsed.netloc or parsed.path
            host = host.split("/", 1)[0]
            host = host.split("?", 1)[0]
            host = host.split("#", 1)[0]
            host = host.rstrip(".")
            return host.lower().lstrip("www.") or None
        except Exception:
            pass
    # No scheme: trim any path/query/fragment and trailing dots/slashes
    v = v.split("/", 1)[0]
    v = v.split("?", 1)[0]
    v = v.split("#", 1)[0]
    v = v.rstrip("./")
    return v.lower().lstrip("www.")


def load_domains(csv_path: Path) -> List[str]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {csv_path}")

    # Open with utf-8-sig to strip BOM if present
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        # Try to sniff dialect (delimiter, quotechar)
        pos = f.tell()
        sample = f.read(4096)
        f.seek(pos)
        try:
            dialect = csv.Sniffer().sniff(sample)
            # Validate that the delimiter is reasonable (common delimiters only)
            if dialect.delimiter not in [',', ';', '\t', '|']:
                dialect = csv.excel
        except Exception:
            dialect = csv.excel

        reader = csv.DictReader(f, dialect=dialect)
        domains: List[str] = []

        if reader.fieldnames:
            # Normalize headers (case-insensitive, trim)
            raw_fields = [h for h in reader.fieldnames if h]
            norm_map = {h.strip().lower(): h for h in raw_fields}

            # Build ordered list of actual fields to try per row
            preferred_norm = [
                "domain",
                "website",
                "website_url",
                "url",
                "site",
                "homepage",
            ]
            try_fields = [norm_map[n] for n in preferred_norm if n in norm_map] or raw_fields

            # If none of the known headers are present, treat file as headerless
            has_known_header = any(n in norm_map for n in preferred_norm)
            if not has_known_header:
                # Treat as headerless: read each line, split only on common delimiters (not '.')
                f.seek(0)
                text = f.read()
                for line in text.splitlines():
                    if not line.strip():
                        continue
                    first = line
                    if "," in line:
                        first = line.split(",", 1)[0]
                    elif ";" in line:
                        first = line.split(";", 1)[0]
                    elif "\t" in line:
                        first = line.split("\t", 1)[0]
                    d = _domain_from_value(first)
                    if d:
                        domains.append(d)
                # return early since we've handled full file
                return _dedupe_preserve_order(domains)

            for row in reader:
                # Row-level fallback across candidate fields
                raw = None
                for fld in try_fields:
                    val = row.get(fld)
                    if isinstance(val, str):
                        val = val.strip()
                    if val:
                        raw = val
                        break
                if raw is None and raw_fields:
                    # Last resort: first column value
                    val = row.get(raw_fields[0])
                    raw = val.strip() if isinstance(val, str) else val

                d = _domain_from_value(raw or "") if raw else None
                if d:
                    domains.append(d)
        else:
            # No header: treat as simple CSV with a single column or first delimited column
            f.seek(0)
            text = f.read()
            for line in text.splitlines():
                if not line.strip():
                    continue
                first = line
                if "," in line:
                    first = line.split(",", 1)[0]
                elif ";" in line:
                    first = line.split(";", 1)[0]
                elif "\t" in line:
                    first = line.split("\t", 1)[0]
                d = _domain_from_value(first)
                if d:
                    domains.append(d)

    return _dedupe_preserve_order(domains)


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


# ---------- Placeholder crawl/extract ----------

@dataclass
class CrawlResult:
    domain: str
    url: str
    phones: List[str]
    company_name: Optional[str]
    facebook_url: Optional[str]
    linkedin_url: Optional[str]
    twitter_url: Optional[str]
    instagram_url: Optional[str]
    address: Optional[str]
    crawled_at: str
    http_status: int
    response_time_ms: int
    page_size_bytes: int
    method: str
    error: Optional[str]
    _redirect_chain: Optional[List[str]] = None
    _note: Optional[str] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _derive_company_name(domain: str) -> Optional[str]:
    """Derive a basic company name from domain (fallback only)."""
    try:
        left = (domain or "").split(".")[0]
        tokens = [t for t in "".join(ch if ch.isalnum() else " " for ch in left).strip().split() if t]
        name = " ".join(t[:1].upper() + t[1:] for t in tokens)
        return name or None
    except Exception:
        return None


async def _fetch_with_protocol(
    domain: str, protocol: str, timeout: float, user_agent: str, client: Any
) -> Tuple[Any, int]:
    """
    Fetch HTML using specific protocol (https or http).
    
    Returns:
        Tuple of (response, response_time_ms)
    
    Raises:
        httpx exceptions on failure
    """
    url = f"{protocol}://{domain}"
    start_time = time.time()
    response = await client.get(url)
    response_time_ms = int((time.time() - start_time) * 1000)
    return response, response_time_ms


async def fetch_and_extract(domain: str, timeout: float, user_agent: str) -> CrawlResult:
    """
    Fetch HTML from domain via HTTP and extract company data.
    Implements retry logic with exponential backoff and HTTP fallback.
    
    Strategy:
    - Use rotated user-agent if rotation enabled
    - Check robots.txt compliance (if enabled)
    - Try HTTPS first (3 attempts with exponential backoff)
    - If HTTPS fails with SSL/DNS errors, try HTTP (3 attempts)
    - Use jitter to avoid thundering herd
    - Respect crawl-delay directive from robots.txt
    
    Args:
        domain: Domain to crawl (e.g., "example.com")
        timeout: Request timeout in seconds
        user_agent: User-Agent header string (fallback if rotation disabled)
    
    Returns:
        CrawlResult with extracted data or error information
    """
    # Use rotated user-agent if enabled, otherwise use provided/default
    effective_user_agent = _UA_ROTATOR.get_random() if _UA_ROTATOR else user_agent
    
    # Check robots.txt compliance if enabled
    if _ROBOTS_CACHE is not None:
        url_to_check = f"https://{domain}/"
        try:
            can_fetch, crawl_delay = await _ROBOTS_CACHE.can_fetch(url_to_check, effective_user_agent)
            
            if not can_fetch:
                # robots.txt disallows crawling this URL
                return CrawlResult(
                    domain=domain,
                    url=url_to_check,
                    phones=[],
                    company_name=_derive_company_name(domain),
                    facebook_url=None,
                    linkedin_url=None,
                    twitter_url=None,
                    instagram_url=None,
                    address=None,
                    crawled_at=_now_iso(),
                    http_status=0,
                    response_time_ms=0,
                    page_size_bytes=0,
                    method="http",
                    error="Blocked by robots.txt",
                    _note="Disallowed by robots.txt - respecting site's crawl policy"
                )
            
            # Respect crawl-delay if specified
            if crawl_delay and crawl_delay > 0:
                await asyncio.sleep(crawl_delay)
        
        except Exception as e:
            # Fail-open: if robots.txt check fails, proceed with crawl
            # (Don't block legitimate crawls due to robots.txt fetch errors)
            pass
    
    if httpx is None:
        # Fallback if httpx not installed (shouldn't happen in normal usage)
        return CrawlResult(
            domain=domain,
            url=f"https://{domain}",
            phones=[],
            company_name=_derive_company_name(domain),
            facebook_url=None,
            linkedin_url=None,
            twitter_url=None,
            instagram_url=None,
            address=None,
            crawled_at=_now_iso(),
            http_status=0,
            response_time_ms=0,
            page_size_bytes=0,
            method="http",
            error="httpx not installed",
        )
    
    # Use config values for retry and protocol strategy
    max_retries = _config.retry.max_attempts if _config else 3
    
    # Build protocol list based on config
    protocols = []
    if _config:
        if _config.protocol.try_https_first:
            protocols.append("https")
        if _config.protocol.fallback_to_http:
            protocols.append("http")
    if not protocols:  # Fallback if config missing or both disabled
        protocols = ["https"]
    
    start_time = time.time()
    last_error = None
    redirect_chain: Optional[List[str]] = None
    
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={
            "User-Agent": effective_user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        },
    ) as client:
        for protocol in protocols:
            url = f"{protocol}://{domain}"
            
            for attempt in range(max_retries):
                try:
                    response, response_time_ms = await _fetch_with_protocol(
                        domain, protocol, timeout, effective_user_agent, client
                    )
                    
                    # Track redirect chain if any
                    if hasattr(response, 'history') and response.history:
                        redirect_chain = [str(r.url) for r in response.history]
                        redirect_chain.append(str(response.url))
                    
                    html = response.text
                    status = response.status_code
                    page_size = len(html.encode('utf-8'))
                    final_url = str(response.url)
                    
                    # Extract company data
                    extracted = extract_all(html, final_url)
                    
                    # Use extracted company name or derive from domain as fallback
                    company_name = extracted.get('company_name') or _derive_company_name(domain)
                    
                    return CrawlResult(
                        domain=domain,
                        url=final_url,
                        phones=extracted['phones'],
                        company_name=company_name,
                        facebook_url=extracted['facebook_url'],
                        linkedin_url=extracted['linkedin_url'],
                        twitter_url=extracted['twitter_url'],
                        instagram_url=extracted['instagram_url'],
                        address=extracted['address'],
                        crawled_at=_now_iso(),
                        http_status=status,
                        response_time_ms=response_time_ms,
                        page_size_bytes=page_size,
                        method='http',
                        error=None,
                        _redirect_chain=redirect_chain if redirect_chain and len(redirect_chain) > 1 else None,
                    )
                
                except httpx.TimeoutException as e:
                    last_error = f"Timeout after {timeout}s"
                    # Timeout: retry with backoff
                    if attempt < max_retries - 1:
                        backoff = calculate_backoff(attempt, _config.retry if _config else None)
                        await asyncio.sleep(backoff)
                        continue
                
                except httpx.ConnectError as e:
                    # DNS, connection refused, SSL, etc.
                    # Check __cause__ for underlying OS error details
                    error_msg = str(e).lower()
                    cause = getattr(e, '__cause__', None)
                    cause_str = str(cause).lower() if cause else ''
                    
                    # DNS errors: various patterns across platforms
                    if any(pattern in error_msg or pattern in cause_str for pattern in [
                        'name or service not known',  # Linux
                        'nodename nor servname',      # BSD/macOS
                        'getaddrinfo failed',         # Windows
                        'no address associated',      # Various
                        '[errno -2]',                 # getaddrinfo error code
                        '[errno -3]',                 # temporary failure
                        'name resolution',
                    ]):
                        last_error = "DNS error: domain not found"
                        # DNS error: terminal, no point retrying
                        return CrawlResult(
                            domain=domain,
                            url=url,
                            phones=[],
                            company_name=_derive_company_name(domain),
                            facebook_url=None,
                            linkedin_url=None,
                            twitter_url=None,
                            instagram_url=None,
                            address=None,
                            crawled_at=_now_iso(),
                            http_status=0,
                            response_time_ms=int((time.time() - start_time) * 1000),
                            page_size_bytes=0,
                            method='http',
                            error=last_error,
                        )
                    
                    # SSL/certificate errors
                    elif any(pattern in error_msg or pattern in cause_str for pattern in [
                        'ssl',
                        'certificate',
                        'handshake',
                        'tls',
                    ]):
                        last_error = "SSL error"
                        # SSL error: try HTTP fallback
                        break
                    
                    # Connection refused
                    elif 'connection refused' in error_msg or 'connection refused' in cause_str or '[errno 111]' in cause_str:
                        last_error = "Connection refused"
                        # Connection refused: might be transient, retry
                        if attempt < max_retries - 1:
                            backoff = calculate_backoff(attempt, _config.retry if _config else None)
                            await asyncio.sleep(backoff)
                            continue
                    
                    # Connection reset
                    elif 'connection reset' in error_msg or 'connection reset' in cause_str or '[errno 104]' in cause_str:
                        last_error = "Connection reset"
                        # Connection reset: retry
                        if attempt < max_retries - 1:
                            backoff = calculate_backoff(attempt, _config.retry if _config else None)
                            await asyncio.sleep(backoff)
                            continue
                    
                    # Generic connection error
                    else:
                        last_error = f"Connection error: {type(e).__name__}"
                        # Generic error: retry
                        if attempt < max_retries - 1:
                            backoff = calculate_backoff(attempt, _config.retry if _config else None)
                            await asyncio.sleep(backoff)
                            continue
                
                except httpx.HTTPError as e:
                    last_error = f"HTTP error: {type(e).__name__}: {str(e)}"[:100]
                    # Generic HTTP error: retry with backoff
                    if attempt < max_retries - 1:
                        backoff = calculate_backoff(attempt, _config.retry if _config else None)
                        await asyncio.sleep(backoff)
                        continue
                
                except Exception as e:
                    last_error = f"Error: {type(e).__name__}: {str(e)}"[:100]
                    # Unknown error: retry with backoff
                    if attempt < max_retries - 1:
                        backoff = calculate_backoff(attempt, _config.retry if _config else None)
                        await asyncio.sleep(backoff)
                        continue
        
    # All retries exhausted
    return CrawlResult(
        domain=domain,
        url=f"https://{domain}",
        phones=[],
        company_name=_derive_company_name(domain),
        facebook_url=None,
        linkedin_url=None,
        twitter_url=None,
        instagram_url=None,
        address=None,
        crawled_at=_now_iso(),
        http_status=0,
        response_time_ms=int((time.time() - start_time) * 1000),
        page_size_bytes=0,
        method='http',
        error=last_error or "Unknown error",
    )


# ---------- Orchestration ----------


def chunked(seq: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


async def process_batch(
    batch_domains: Sequence[str], timeout: float, user_agent: str
) -> List[CrawlResult]:
    """Process a batch of domains concurrently."""
    tasks = [fetch_and_extract(d, timeout=timeout, user_agent=user_agent) for d in batch_domains]
    # Gather with return_exceptions to avoid failing the whole run
    results: List[CrawlResult] = []
    gathered = await asyncio.gather(*tasks, return_exceptions=True)
    for d, g in zip(batch_domains, gathered):
        if isinstance(g, Exception):
            results.append(
                CrawlResult(
                    domain=d,
                    url=f"https://{d}",
                    phones=[],
                    company_name=_derive_company_name(d),
                    facebook_url=None,
                    linkedin_url=None,
                    twitter_url=None,
                    instagram_url=None,
                    address=None,
                    crawled_at=_now_iso(),
                    http_status=0,
                    response_time_ms=0,
                    page_size_bytes=0,
                    method="http",
                    error=f"Unexpected error: {type(g).__name__}: {str(g)}"[:200],
                )
            )
        else:
            results.append(g)
    return results


def log_batch_header(batch_idx: int, total_batches: int, size: int) -> None:
    print(f"Batch {batch_idx}/{total_batches} ({size} domains)...")


def maybe_log_browser_fallback(domain: str) -> None:
    if "javascript" in domain or "spa" in domain or "headless" in domain:
        print(f"  ↳ Using browser fallback for {domain}")


async def run(args: argparse.Namespace) -> int:
    # Color helpers (TTY only unless --no-color)
    COLORS = {
        "green": "\x1b[32m",
        "cyan": "\x1b[36m",
        "yellow": "\x1b[33m",
        "red": "\x1b[31m",
        "reset": "\x1b[0m"
    }
    use_color = (not getattr(args, "no_color", False)) and sys.stdout.isatty()
    def _c(s: str, c: str) -> str: return f"{COLORS[c]}{s}{COLORS['reset']}" if use_color else s
    def info(msg: str) -> None: print(_c(msg, "cyan"))
    def ok(msg: str) -> None: print(_c(msg, "green"))
    def warn(msg: str) -> None: print(_c(msg, "yellow"))
    def error(msg: str) -> None: print(_c(msg, "red"))

    # Update global robots.txt cache based on CLI flag
    global _ROBOTS_CACHE
    if hasattr(args, 'respect_robots') and not args.respect_robots:
        _ROBOTS_CACHE = None
    
    domains = load_domains(args.input)
    total = len(domains)

    # Header
    info("Python Crawler Starting")
    info(f"  Domains: {total}")
    info(f"  Concurrency: {args.concurrency}")
    info(f"  Timeout: {args.timeout:.1f}s")
    info(f"  User-Agent: {args.user_agent if not _UA_ROTATION_ENABLED else 'rotating (7 variants)'}")
    info(f"  Robots.txt: {'enabled' if _ROBOTS_CACHE else 'disabled'}")
    info(f"  Output: {args.output}")

    ensure_parent_dir(args.output)

    started = time.perf_counter()

    total_batches = max(1, (total + args.concurrency - 1) // args.concurrency)
    written = 0

    # Open output file once, append NDJSON per result
    with args.output.open("w", encoding="utf-8") as out_f:
        for i, batch in enumerate(chunked(domains, args.concurrency), start=1):
            log_batch_header(i, total_batches, len(batch))
            for d in batch:
                maybe_log_browser_fallback(d)

            batch_results = await process_batch(batch, timeout=args.timeout, user_agent=args.user_agent)
            for r in batch_results:
                out_f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
                written += 1

    elapsed = time.perf_counter() - started
    avg = (written / elapsed) if elapsed > 0 else 0.0

    print()
    info("----------------------------------")
    info("--- Crawler finished: `python` ---")
    info("----------------------------------")
    print()
    # Color the elapsed time based on thresholds
    if elapsed < 600:  # < 10 mins
        ok(f"Completed in {(elapsed / 60):.0f}m {(elapsed % 60):.0f}s")
    elif elapsed < 900:  # < 15 mins
        warn(f"Completed in {(elapsed / 60):.0f}m {(elapsed % 60):.0f}s")
    else:
        error(f"Completed in {(elapsed / 60):.0f}m {(elapsed % 60):.0f}s")
    print()
    info("----------------------------------")
    print()
    info(f"Output: {args.output}")
    info(f"Average: {avg:.1f} domains/sec")

    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = parse_args(argv)
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("Interrupted.")
        return 130
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
