# Scrapy Crawler for Phidi

## Overview

Scrapy-based implementation of the company data crawler using industry-standard web scraping framework.

## Features

- **Industry Standard**: Uses Scrapy, the most popular Python web scraping framework
- **Built-in Best Practices**: Robots.txt compliance, auto-throttling, retry logic, DNS caching
- **Config Integration**: Reuses existing `configs/crawl.policy.yaml` configuration
- **DRY Principle**: Reuses extraction logic from `src/common/` utilities
- **Same Interface**: Drop-in replacement for Python/Node crawlers (same input/output format)

## Installation

```bash
# Install Scrapy and dependencies
pip install -r src/crawlers/scrapy/requirements.txt
```

## Usage

### Basic Usage

```bash
python src/crawlers/scrapy/main.py \
  --input data/inputs/sample-websites.csv \
  --output data/outputs/scrapy_results.ndjson
```

### With Makefile

```bash
# Run Scrapy crawler
make crawl-scrapy

# Run all crawlers for comparison
make crawl-all
```

## Architecture

### File Structure

```
src/crawlers/scrapy/
├── scrapy.cfg              # Scrapy project configuration
├── main.py                 # CLI entry point (consistent with other crawlers)
├── requirements.txt        # Dependencies
├── phidi_spider/
│   ├── __init__.py
│   ├── settings.py         # Scrapy settings (loads from crawl.policy.yaml)
│   ├── middlewares.py      # Custom middleware (UA rotation, HTTP fallback)
│   ├── pipelines.py        # NDJSON export pipeline
│   └── spiders/
│       └── company.py      # Main spider (reuses common extraction utils)
```

### Integration Points

1. **Config Reuse**: Loads settings from `configs/crawl.policy.yaml`
   - `http.concurrency` → `CONCURRENT_REQUESTS`
   - `http.timeout_seconds` → `DOWNLOAD_TIMEOUT`
   - `robots.enabled` → `ROBOTSTXT_OBEY`
   - User-agent rotation settings

2. **Extraction Reuse**: Uses shared utilities from `src/common/`
   - `phone_utils.extract_phones()`
   - `social_utils.extract_social_links()`
   - `address_utils.extract_addresses()`
   - `domain_utils.clean_domain()`

3. **Output Compatibility**: Produces identical NDJSON format
   ```json
   {"domain": "example.com", "phones": [...], "facebook": "...", ...}
   ```

## Configuration

Settings are loaded from `configs/crawl.policy.yaml`. Scrapy-specific overrides:

- **Auto-throttling**: Enabled (adapts speed based on server response)
- **DNS Caching**: 10,000 entries (improves performance)
- **Cookie Handling**: Disabled (most business sites don't need it)
- **Max Download Size**: 10MB (avoids large file downloads)

## Comparison with Existing Crawlers

| Feature | Python (httpx) | Node (undici) | Scrapy |
|---------|----------------|---------------|--------|
| Framework | Custom | Custom | Industry Standard |
| Robots.txt | Manual implementation | Manual implementation | Built-in |
| Auto-throttling | No | No | Yes |
| DNS Caching | No | No | Yes (10k entries) |
| Retry Logic | Custom exponential backoff | Custom exponential backoff | Built-in + backoff |
| HTTP/2 Support | Yes | Yes | Via Twisted |
| Code Complexity | ~400 lines | ~450 lines | ~150 lines |
| Learning Curve | Low | Low | Medium |
| Scalability | Good | Good | Excellent |

## Expected Results

Based on Scrapy's mature optimization:

- **Coverage**: 75-85% (better redirect/retry handling)
- **Speed**: 2-5x faster (Twisted reactor, connection pooling)
- **Code**: 60% less code than custom implementation
- **Maintenance**: Framework handles HTTP/2, TLS updates upstream

## Testing

```bash
# Run with debug logging
python src/crawlers/scrapy/main.py \
  --input data/inputs/test-sample.csv \
  --output data/outputs/scrapy_test.ndjson \
  --log-level DEBUG

# Compare results with existing crawlers
make crawl-all
make evaluate
```

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError`, ensure:
1. Scrapy is installed: `pip install scrapy`
2. You're running from repo root
3. Virtual environment is activated

### No Output File

Check that:
1. Output directory exists and is writable
2. Input CSV is valid (domains, one per line)
3. Check logs for errors

### Low Coverage

Adjust settings in `configs/crawl.policy.yaml`:
- Increase `http.timeout_seconds` (default: 12)
- Increase `retry.max_attempts` (default: 3)
- Enable HTTP fallback: `protocol.fallback_to_http: true`

## Performance Tips

1. **Increase Concurrency**: Set `http.concurrency: 100` for faster crawls
2. **Disable Robots.txt**: Set `robots.enabled: false` for testing (not recommended for production)
3. **Reduce Timeout**: Set `http.timeout_seconds: 8` to fail faster on slow sites
4. **Use SSD**: Faster I/O improves DNS caching and output writing

## License

Same as parent project.
