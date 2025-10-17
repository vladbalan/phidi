# Crawler Configuration

Configuration system for tuning crawler performance, politeness, and extraction behavior across all implementations (Python, Node.js, Scrapy, Scrapy-lite).

## Quick Start

```bash
# Use a profile
python src/crawlers/python/main.py --profile aggressive
make crawl-scrapy PROFILE=balanced

# Benchmark multiple configurations
make benchmark BENCH_CONFIGS="python:aggressive scrapy:conservative"
```

## Configuration Files

### Base Configuration
**`configs/crawl.policy.yaml`** - Default settings for all crawlers

Contains all configuration options with inline documentation. Profiles override these defaults.

### Profiles
**`configs/profiles/*.yaml`** - Performance presets

| Profile | Use Case | Settings |
|---------|----------|----------|
| `aggressive.yaml` | Speed benchmarks, large-scale crawls | 100 concurrency, 8s timeout, 2 retries |
| `balanced.yaml` | Production default | 50 concurrency, 12s timeout, 3 retries |
| `conservative.yaml` | High-value targets, comprehensive coverage | 30 concurrency, 20s timeout, 5 retries |

**How profiles work**: Profiles are merged on top of `crawl.policy.yaml`. Only specify settings you want to override.

## Configuration Sections

### HTTP Settings

```yaml
http:
  timeout_seconds: 12          # Request timeout (10-15s recommended)
  concurrency: 50              # Parallel requests (30-100 recommended)
  user_agent: "..."            # Fallback UA (if rotation disabled)
  follow_redirects: true       # Follow 301/302 redirects
  max_redirects: 5             # Max redirect chain length
```

**Tuning tips**:
- **Low concurrency** (10-30): More respectful, avoids rate limiting
- **High concurrency** (50-100): Faster but may trigger anti-bot measures
- **Timeout**: Balance coverage (higher) vs speed (lower)

### User-Agent Rotation

```yaml
user_agent_rotation:
  enabled: true                # Rotate through realistic browser UAs
  identify: true               # Append crawler ID for transparency
```

**Behavior**:
- When enabled: Rotates through 7 realistic browser user-agents
- `identify: true` appends `(SpaceCrawler/1.0)` to each UA
- When disabled: Uses `http.user_agent` for all requests

**Example UAs**:
```
Mozilla/5.0 (Windows NT 10.0; Win64; x64)... (SpaceCrawler/1.0)
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)... (SpaceCrawler/1.0)
```

See `src/common/user_agent_rotation.py` for full list.

### Retry Policy

```yaml
retry:
  max_attempts: 3              # Total attempts (1 initial + 2 retries)
  backoff_base_seconds: 0.5    # Exponential backoff base
  jitter_max_seconds: 0.5      # Random jitter to avoid thundering herd
  
  retry_on:                    # Retry these errors
    - timeout
    - connection_reset
    - connection_refused
    - temporary_error
  
  skip_retry_on:               # Don't retry these (terminal errors)
    - dns_error
    - invalid_domain
```

**Backoff formula**: `delay = base * (2 ^ attempt) + random(0, jitter)`

**Examples**:
- Attempt 0: 0.5s + jitter
- Attempt 1: 1.0s + jitter
- Attempt 2: 2.0s + jitter

### Protocol Fallback

```yaml
protocol:
  try_https_first: true        # Always try HTTPS first
  fallback_to_http: true       # Try HTTP if HTTPS fails
  
  http_fallback_on:            # Trigger fallback on these errors
    - ssl_error
    - certificate_error
    - handshake_error
```

**Why this matters**: Many small businesses lack SSL certificates. Fallback ensures better coverage.

**Behavior**:
1. Try `https://example.com`
2. If SSL error → try `http://example.com`
3. If HTTP succeeds → return result

### Robots.txt Compliance

```yaml
robots:
  enabled: true                # Check robots.txt before crawling
  cache_ttl_seconds: 86400     # Cache for 24 hours
  respect_crawl_delay: true    # Honor crawl-delay directive
  fail_open: true              # Allow crawling if robots.txt fetch fails
```

**Fail-open strategy**: If `robots.txt` is unreachable, allow crawling (avoids false negatives).

See [ROBOTS_TXT_IMPLEMENTATION.md](ROBOTS_TXT_IMPLEMENTATION.md) for details.

### Logging

```yaml
logging:
  level: "info"                # debug, info, warning, error
  show_progress: true          # Show batch progress bar
  show_fallbacks: true         # Log HTTPS→HTTP fallbacks
  colorize: true               # Colored output (auto-detect TTY)
```

## Creating Custom Profiles

Create a new profile in `configs/profiles/`:

```yaml
# configs/profiles/my-custom.yaml
name: "my-custom"
description: "Custom settings for X use case"

http:
  timeout_seconds: 15
  concurrency: 75

retry:
  max_attempts: 4

# Only specify settings that differ from crawl.policy.yaml
# All other settings are inherited
```

Use it:
```bash
python src/crawlers/python/main.py --profile my-custom
make crawl-node PROFILE=my-custom
```

## Profile Comparison

| Setting | Aggressive | Balanced | Conservative |
|---------|-----------|----------|--------------|
| **Concurrency** | 100 | 50 | 30 |
| **Timeout** | 8s | 12s | 20s |
| **Max Retries** | 2 | 3 | 5 |
| **Backoff Base** | 0.3s | 0.5s | 1.0s |
| **Trade-off** | Speed > Coverage | Balanced | Coverage > Speed |

**When to use each**:
- **Aggressive**: Benchmarking, large-scale crawls, speed testing
- **Balanced**: Production default, most use cases
- **Conservative**: High-value targets, respectful crawling, maximum data quality

## Benchmarking Workflow

Compare profiles to find optimal settings:

```bash
# Default benchmark (all crawlers, balanced profile)
make benchmark

# Compare specific configurations
make benchmark BENCH_CONFIGS="python:aggressive python:conservative"

# Multi-crawler comparison
make benchmark BENCH_CONFIGS="python:balanced scrapy:balanced node:balanced"

# Generate comparison report
make evaluate
```

**Benchmark output**: `data/reports/benchmark_comparison.md`

## Environment Variables

Override configuration via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `CRAWLER_TIMEOUT` | `12` | Request timeout (seconds) |
| `CRAWLER_CONCURRENCY` | `50` | Parallel requests |
| `CRAWLER_LOG_LEVEL` | `info` | Log level |
| `ROBOTS_ENABLED` | `true` | Enable robots.txt checking |

**Example**:
```bash
export CRAWLER_CONCURRENCY=100
export CRAWLER_TIMEOUT=8
python src/crawlers/python/main.py
```

## Configuration Loading

All crawlers use `src/common/config_loader.py`:

```python
from src.common.config_loader import load_config

# Load with profile
config = load_config(profile="aggressive")

# Access settings
timeout = config["http"]["timeout_seconds"]
concurrency = config["http"]["concurrency"]
```

**Merge order** (later overrides earlier):
1. `crawl.policy.yaml` (base)
2. Profile YAML (e.g., `aggressive.yaml`)
3. Environment variables

## Performance Tuning Guide

### Maximize Speed
```yaml
http:
  timeout_seconds: 6
  concurrency: 100
retry:
  max_attempts: 1
```
**Trade-off**: ~20% faster, ~15% lower coverage

### Maximize Coverage
```yaml
http:
  timeout_seconds: 20
  concurrency: 20
retry:
  max_attempts: 5
  backoff_base_seconds: 1.0
```
**Trade-off**: ~30% slower, ~10% better coverage

### Avoid Rate Limiting
```yaml
http:
  concurrency: 30              # Lower concurrency
retry:
  backoff_base_seconds: 1.0    # Longer delays
robots:
  enabled: true                # Respect robots.txt
  respect_crawl_delay: true    # Honor crawl-delay
```

### Debug Failed Requests
```yaml
logging:
  level: "debug"
  show_fallbacks: true
output:
  include_errors: true
```

## Common Issues

### Too many timeouts
**Solution**: Increase `timeout_seconds` to 15-20

### Rate limiting / 429 errors
**Solution**: 
- Reduce `concurrency` to 20-30
- Increase `backoff_base_seconds` to 1.0
- Enable `robots.respect_crawl_delay`

### Low coverage on small business sites
**Solution**: 
- Enable `protocol.fallback_to_http` (many lack SSL)
- Increase `timeout_seconds` (slower servers)
- Increase `max_attempts` (unreliable hosting)

### Crawling too slow
**Solution**:
- Increase `concurrency` to 75-100
- Reduce `timeout_seconds` to 8-10
- Reduce `max_attempts` to 2

## Best Practices

**Production Settings**:
- Start with `balanced` profile
- Enable `robots.enabled: true`
- Enable `user_agent_rotation.identify: true` for transparency
- Use `timeout_seconds: 12-15` for reliable coverage
- Set `concurrency: 30-50` to avoid rate limiting

**Benchmarking Settings**:
- Use `aggressive` profile for speed tests
- Use `conservative` profile for coverage tests
- Compare multiple profiles to find optimal configuration
- Run on same dataset for fair comparison

**Respectful Crawling**:
- Keep `concurrency` ≤ 50 for smaller sites
- Enable `robots.enabled: true`
- Enable `user_agent_rotation.identify: true`
- Use `backoff_base_seconds ≥ 0.5`

## Related Documentation

- **[Robots.txt Implementation](ROBOTS_TXT_IMPLEMENTATION.md)**: Compliance details
- **[User-Agent Rotation](USER_AGENT_ROTATION.md)**: UA rotation implementation
- **[Crawler Improvements](CRAWLER_IMPROVEMENTS.md)**: Coverage optimization techniques
- **[Architecture](ARCHITECTURE.md)**: System design overview

---

**TL;DR**: Use `configs/profiles/balanced.yaml` for production. Override with `aggressive` for speed or `conservative` for coverage. Profiles merge on top of `crawl.policy.yaml`.
