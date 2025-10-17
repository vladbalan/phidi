# Configuration Profiles

Configuration profiles allow you to test different crawler settings for benchmarking and comparison without modifying the base `crawl.policy.yaml`.

## Available Profiles

### `aggressive.yaml` - Speed-Focused
**Use for:** Performance benchmarking, large-scale crawls where some data loss is acceptable

- High concurrency (100 parallel requests)
- Short timeout (8 seconds)
- Minimal retries (2 attempts)
- **Trade-off:** Faster but lower coverage

### `conservative.yaml` - Coverage-Focused
**Use for:** High-value targets, comprehensive data collection, respectful crawling

- Low concurrency (30 parallel requests)
- Long timeout (20 seconds)
- More retries (5 attempts)
- **Trade-off:** Better coverage but slower

### `balanced.yaml` - Production Default
**Use for:** Most production scenarios

- Medium concurrency (50 parallel requests)
- Standard timeout (12 seconds)
- Standard retries (3 attempts)
- **Trade-off:** Good balance

## Usage

### Python Crawler
```bash
python src/crawlers/python/main.py --profile aggressive
python src/crawlers/python/main.py --profile conservative
```

### Node Crawler
```bash
cd src/crawlers/node
npm start -- --profile aggressive
```

### Scrapy Crawler
```bash
python src/crawlers/scrapy/main.py --profile aggressive
```

## Benchmarking Workflow

Compare different profiles to find optimal settings:

```bash
# Quick start with default crawlers and profiles
make benchmark

# Custom benchmark with specific profiles
make benchmark BENCH_CONFIGS="python:aggressive scrapy:balanced"

# Run with different profiles
python src/crawlers/python/main.py --profile aggressive \
  --output data/outputs/python_aggressive.ndjson

python src/crawlers/python/main.py --profile conservative \
  --output data/outputs/python_conservative.ndjson

# Compare results
python src/eval/evaluate.py \
  --results \
    python-aggressive:data/outputs/python_aggressive.ndjson \
    python-conservative:data/outputs/python_conservative.ndjson
```

## Creating Custom Profiles

Create a new YAML file in `configs/profiles/`:

```yaml
# configs/profiles/my-custom.yaml
name: "my-custom"
description: "Custom settings for specific use case"

http:
  timeout_seconds: 15
  concurrency: 75

# Only include settings that differ from base config
# All other settings inherit from crawl.policy.yaml
```

Then use it:
```bash
python src/crawlers/python/main.py --profile my-custom
```

## Profile Inheritance

Profiles are **merged on top of** the base `crawl.policy.yaml`:

1. Base config is loaded from `crawl.policy.yaml`
2. Profile values override base values
3. Unspecified settings keep their base values

Example:
- Base config has `robots.enabled: false`
- Profile only specifies `http.concurrency: 100`
- Result: `concurrency=100`, `robots.enabled=false` (inherited)
