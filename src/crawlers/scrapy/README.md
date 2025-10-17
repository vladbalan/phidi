# Scrapy Crawler for Phidi (Native Extraction)

## Overview

Scrapy-based implementation using **native Scrapy extraction** (CSS/XPath selectors, ItemLoaders).
This crawler demonstrates Scrapy's built-in extraction capabilities for comparison with regex-based approaches.

## Key Features

- **Native Scrapy Extraction**: Uses CSS selectors, XPath, and ItemLoaders
- **Field Processors**: Automatic data normalization via item processors
- **Schema.org Support**: Extracts structured data from microdata markup
- **Best Practices**: Follows Scrapy conventions and patterns
- **DRY Normalization**: Reuses existing phone/social/address utilities

## Extraction Strategy

### Company Name
- Meta tags: `og:site_name`
- HTML title tag
- H1 headings

### Phone Numbers
- `tel:` links (href attributes)
- Text patterns in contact sections

### Social Media
- Links containing platform domains (facebook.com, linkedin.com, etc.)
- Canonicalized using existing social utilities

### Address
- Schema.org markup (`itemprop="address"`, `itemprop="streetAddress"`)
- `<address>` HTML tags
- Common CSS classes (address, location, contact)
- Text patterns containing street indicators

## Installation

```bash
# Install Scrapy and dependencies
pip install -r src/crawlers/scrapy/requirements.txt
```

## Usage

### Direct Execution

```bash
python src/crawlers/scrapy/main.py \
  --input data/inputs/sample-websites.csv \
  --output data/outputs/scrapy_results.ndjson
```

### With Makefile

```bash
# Run Scrapy crawler (if configured)
make crawl-scrapy
```

### With Profile

```bash
python src/crawlers/scrapy/main.py \
  -i data/inputs/sample-websites.csv \
  -o data/outputs/scrapy_results.ndjson \
  --profile aggressive
```

## Project Structure

```
src/crawlers/scrapy/
├── scrapy.cfg              # Scrapy project configuration
├── requirements.txt        # Python dependencies
├── main.py                 # CLI entry point
└── phidi_spider/
    ├── __init__.py
    ├── settings.py         # Scrapy settings (loads from crawl.policy.yaml)
    ├── items.py            # Item definitions with field processors
    ├── middlewares.py      # User-agent rotation, HTTP fallback
    ├── pipelines.py        # NDJSON export pipeline
    └── spiders/
        ├── __init__.py
        └── company.py      # Main spider with CSS/XPath extraction
```

## Configuration

Settings are loaded from `configs/crawl.policy.yaml`. Scrapy-specific overrides:

- `CONCURRENT_REQUESTS`: Controlled by `http.concurrency`
- `DOWNLOAD_TIMEOUT`: From `http.timeout_seconds`
- `ROBOTSTXT_OBEY`: From `robots.enabled`
- `AUTOTHROTTLE_ENABLED`: Always true for smart rate limiting

## Comparison: Native vs Regex

| Aspect | Scrapy Native (this) | Scrapy-Lite (regex) |
|--------|---------------------|---------------------|
| Extraction | CSS/XPath selectors | Regex patterns |
| Method | Structured parsing | Pattern matching |
| Dependencies | ItemLoaders, processors | extract.py module |
| Maintainability | Scrapy conventions | Custom regex |
| Schema.org | Native support | Manual parsing |

## Performance Expectations

Based on Scrapy's mature optimization:
- Concurrent requests: 4-20 (platform-dependent)
- Auto-throttling based on server response times
- Efficient connection pooling
- Smart DNS caching

## Development

To modify extraction logic:

1. Edit `phidi_spider/spiders/company.py` - update CSS/XPath selectors
2. Edit `phidi_spider/items.py` - adjust field processors
3. Test with sample data:

```bash
python src/crawlers/scrapy/main.py \
  -i data/inputs/test-maz.csv \
  -o data/outputs/scrapy_test.ndjson \
  --log-level DEBUG
```

## Notes

- Extraction methodology differs from `scrapy-lite` for benchmarking purposes
- Reuses existing normalization utilities (phone_utils, social_utils, normalize_utils)
- Compatible with existing output format and evaluation tools
- Designed to test CSS/XPath extraction vs regex for accuracy comparison
