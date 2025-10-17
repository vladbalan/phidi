#!/usr/bin/env python3
"""
Main entry point for Scrapy-based Phidi crawler (native extraction).
Provides consistent CLI interface with existing Python/Node crawlers.

Usage:
    python main.py --input domains.csv --output results.ndjson
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add repo root to path
_repo_root = Path(__file__).resolve().parents[3]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))


def main(argv=None):
    """
    CLI entry point for Scrapy crawler.
    Maintains same interface as existing crawlers for drop-in compatibility.
    """
    parser = argparse.ArgumentParser(
        description="Scrapy-based web crawler with native extraction (CSS/XPath)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --input data/inputs/sample-websites.csv --output data/outputs/scrapy_results.ndjson
  python main.py -i domains.csv -o results.ndjson --log-level DEBUG
        """
    )
    
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Input CSV file with domains (one per line, optionally with header)'
    )
    
    parser.add_argument(
        '--output', '-o',
        required=True,
        help='Output NDJSON file for crawl results'
    )
    
    parser.add_argument(
        '--profile',
        type=str,
        default=None,
        help='Configuration profile (e.g., aggressive, conservative, balanced)'
    )
    
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logging level (default: INFO)'
    )
    
    args = parser.parse_args(argv)
    
    # Resolve paths to absolute BEFORE changing directories
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    
    # Validate input file exists
    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_path}", file=sys.stderr)
        return 1
    
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load config with profile support
    config = _load_config(args.profile)

    domains = _load_domains(input_path)
    total_domains = len(domains)
    del domains
    
    # Import Scrapy here (after arg parsing) to show usage errors quickly
    try:
        from scrapy.crawler import CrawlerProcess
        from scrapy.utils.project import get_project_settings
    except ImportError:
        print("[ERROR] Scrapy not installed. Install with: pip install scrapy", file=sys.stderr)
        return 2
    
    # Change to Scrapy project directory for settings to load correctly
    original_dir = Path.cwd()
    scrapy_dir = Path(__file__).parent
    
    try:
        os.chdir(scrapy_dir)
        
        # Pass profile to Scrapy settings via environment variable
        if args.profile:
            os.environ['SCRAPY_CONFIG_PROFILE'] = args.profile
        
        # Load Scrapy settings
        settings = get_project_settings()
        settings.set('LOG_LEVEL', args.log_level)
        
        # Configure simple colorized logging similar to Python crawler
        colors = {
            'green': '\x1b[32m',
            'cyan': '\x1b[36m',
            'yellow': '\x1b[33m',
            'red': '\x1b[31m',
            'reset': '\x1b[0m',
        }
        use_color = sys.stdout.isatty()

        def _c(message: str, color: str) -> str:
            return f"{colors[color]}{message}{colors['reset']}" if use_color else message

        def info(message: str) -> None:
            print(_c(message, 'cyan'))

        def ok(message: str) -> None:
            print(_c(message, 'green'))

        def warn(message: str) -> None:
            print(_c(message, 'yellow'))

        def error(message: str) -> None:
            print(_c(message, 'red'))

        # Create crawler process
        process = CrawlerProcess(settings)
        
        # Run spider with arguments (use absolute paths)
        process.crawl(
            'company',
            input_file=str(input_path),
            output_file=str(output_path)
        )

        concurrency = settings.getint('CONCURRENT_REQUESTS', settings.get('CONCURRENT_REQUESTS', 0))
        timeout = settings.getfloat('DOWNLOAD_TIMEOUT', settings.get('DOWNLOAD_TIMEOUT', 0.0))
        robots_enabled = bool(settings.getbool('ROBOTSTXT_OBEY')) if hasattr(settings, 'getbool') else bool(settings.get('ROBOTSTXT_OBEY', True))
        user_agent = settings.get('USER_AGENT', 'n/a')
        ua_display = 'rotating (7 variants)' if getattr(getattr(config, 'user_agent_rotation', None), 'enabled', False) else user_agent

        info("Scrapy Crawler Starting (Native Extraction)")
        info(f"  Extraction: CSS/XPath selectors + ItemLoaders")
        info(f"  Domains: {total_domains}")
        info(f"  Concurrency: {concurrency}")
        info(f"  Timeout: {timeout:.1f}s")
        info(f"  User-Agent: {ua_display}")
        info(f"  Robots.txt: {'enabled' if robots_enabled else 'disabled'}")
        info(f"  Output: {output_path}")
        info(f"  Config: {_config_status(config)}")
        
        start_time = time.perf_counter()
        
        # Start the crawler (blocks until complete)
        process.start()

        elapsed = time.perf_counter() - start_time
        processed = _count_records(output_path)
        avg = (processed / elapsed) if elapsed > 0 else 0.0

        # Write metadata file with total execution time
        meta_path = output_path.with_suffix(".meta.json")
        with meta_path.open("w", encoding="utf-8") as meta_f:
            json.dump({
                "total_time_seconds": round(elapsed, 2),
                "domains_processed": processed,
                "avg_domains_per_sec": round(avg, 2)
            }, meta_f, indent=2)

        print()
        info("----------------------------------")
        info("--- Crawler finished: `scrapy` ---")
        info("----------------------------------")
        print()
        if elapsed < 600:
            ok(f"Completed in {(elapsed / 60):.0f}m {(elapsed % 60):.0f}s")
        elif elapsed < 900:
            warn(f"Completed in {(elapsed / 60):.0f}m {(elapsed % 60):.0f}s")
        else:
            error(f"Completed in {(elapsed / 60):.0f}m {(elapsed % 60):.0f}s")
        print()
        info("----------------------------------")
        print()
        info(f"Output: {output_path}")
        info(f"Average: {avg:.1f} domains/sec")

        return 0
        
    finally:
        # Restore original directory
        os.chdir(original_dir)


def _config_status(config=None, profile=None):
    config = config if config is not None else _load_config(profile)
    return "yes" if config else "no (using defaults)"


def _load_config(profile=None):
    """Load crawler config with optional profile support."""
    try:
        from src.common.crawler_config import load_crawler_config
        return load_crawler_config(profile=profile)
    except Exception:
        return None


def _load_domains(csv_path: Path):
    try:
        from src.crawlers.python.main import load_domains
        return load_domains(csv_path)
    except Exception:
        domains = []
        try:
            import csv
            with csv_path.open('r', encoding='utf-8-sig', newline='') as f:
                reader = csv.reader(f)
                for idx, row in enumerate(reader):
                    if not row:
                        continue
                    value = row[0].strip()
                    if idx == 0 and value.lower() == 'domain':
                        continue
                    if value:
                        domains.append(value)
        except Exception:
            pass
        return domains


def _count_records(output_path: Path) -> int:
    try:
        with output_path.open('r', encoding='utf-8') as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


if __name__ == '__main__':
    sys.exit(main())
