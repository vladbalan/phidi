# Architecture

System architecture for the Phidi web crawler benchmarking and company data matching platform.

## Overview

Phidi is a **modular data extraction pipeline** with two main use cases:

1. **Crawler Benchmarking** (primary focus): Compare 4 crawler implementations objectively
2. **Company Matching Pipeline** (optional): Full ETL → Elasticsearch → API workflow

## System Diagram

![Architecture Diagram](diagrams/architecture.png)


## Components

### 1. Crawler Layer

Four implementations for objective comparison:

#### Python Crawler
- **Runtime**: Python 3.11+
- **HTTP Client**: httpx (async/await)
- **Concurrency**: asyncio
- **Location**: `src/crawlers/python/`
- **Entry**: `main.py`

**Characteristics**:
- Native async/await syntax
- Good performance for I/O-bound tasks
- ~400 lines of code

#### Node.js Crawler
- **Runtime**: Node.js 20+
- **HTTP Client**: undici (official Node.js client)
- **Concurrency**: Promises with concurrency control
- **Location**: `src/crawlers/node/`
- **Entry**: `dist/index.js` (TypeScript compiled)

**Characteristics**:
- TypeScript for type safety
- undici 5-10× faster than axios
- ~450 lines of code

#### Scrapy Crawler
- **Runtime**: Python 3.11+
- **Framework**: Scrapy (Twisted engine)
- **Concurrency**: Twisted reactor
- **Location**: `src/crawlers/scrapy/`
- **Entry**: `main.py`

**Characteristics**:
- Battle-tested at scale
- Built-in robots.txt, rate limiting
- Native extraction logic
- ~150 lines (framework does heavy lifting)

#### Scrapy-lite Crawler
- **Runtime**: Python 3.11+
- **Framework**: Scrapy (Twisted engine)
- **Concurrency**: Twisted reactor
- **Location**: `src/crawlers/scrapy-lite/`
- **Entry**: `main.py`

**Characteristics**:
- Same as Scrapy but uses shared utilities (`phone_utils`, `social_utils`)
- Fair comparison with Python/Node crawlers
- ~150 lines

### 2. Shared Components

Located in `src/common/`, ensures **fair benchmarking**:

#### phone_utils.py
Phone number extraction and normalization:
- Strip extensions (e.g., "ext 123", "x456")
- E.164 format conversion
- Default country handling (US)

**Used by**: All crawlers

#### social_utils.py
Social media URL canonicalization:
- Facebook: Normalize fb.com → facebook.com
- Instagram: Remove www, lowercase
- LinkedIn, Twitter: Canonical URL format

**Used by**: All crawlers

#### normalize_utils.py
Address parsing and normalization:
- Parse free-form address strings
- Extract street, city, state, zip
- Minimal heuristic-based parsing

**Used by**: ETL pipeline, crawlers

#### robots_parser.py
Robots.txt compliance:
- 24-hour cache per domain
- Fail-open strategy (allow if unreachable)
- Respects `crawl-delay` directive

**Used by**: All crawlers

#### user_agent_rotation.py
Ethical user-agent rotation:
- 7 realistic browser UAs
- Appends crawler ID: `(SpaceCrawler/1.0)`
- Random selection per request

**Used by**: All crawlers

#### crawler_config.py
Configuration management:
- Loads `configs/crawl.policy.yaml` (base)
- Merges profile overrides (e.g., `aggressive.yaml`)
- Environment variable support

**Used by**: All crawlers

#### domain_utils.py
Domain extraction and normalization:
- Extract domain from URLs
- Normalize to lowercase
- Handle www removal

**Used by**: All crawlers

### 3. ETL Pipeline

Optional pipeline for full company matching workflow:

#### normalize.py
Standardize extracted data:
- Phone → E.164 format
- URLs → lowercase, canonical
- Address → structured fields

**Input**: Raw NDJSON from crawlers  
**Output**: `data/staging/normalized.ndjson`

#### merge_names.py
Enrich with company names:
- Join website data with company name mappings
- Handle missing names gracefully

**Input**: Normalized data + name mappings  
**Output**: `data/staging/merged.ndjson`

#### dedupe.py
Remove duplicate records:
- Dedupe by domain (primary key)
- Merge multiple records per domain
- Preserve all phones/social URLs

**Input**: Merged data  
**Output**: `data/staging/deduped.ndjson`

#### load_es.py
Load into Elasticsearch:
- Bulk insert with batching
- Create index with mappings
- Update alias for zero-downtime

**Input**: Deduped data  
**Output**: Elasticsearch `companies_v1` index

### 4. Elasticsearch

**Version**: 8.11.1  
**Port**: 9200  
**Index**: `companies_v1`  
**Alias**: `companies`

**Schema** (see `configs/es.mappings.json`):
```json
{
  "domain": "keyword",
  "company_name": "text",
  "phones": "keyword[]",
  "facebook": "keyword",
  "instagram": "keyword",
  "linkedin": "keyword",
  "twitter": "keyword",
  "address": {
    "street": "text",
    "city": "keyword",
    "state": "keyword",
    "zip": "keyword"
  }
}
```

**Query Strategy**:
- Boosted multi-match on domain, name, phone, social
- Top 10 candidates retrieved
- Reranked by weighted fuzzy matching

### 5. Matching API

**Framework**: FastAPI  
**Port**: 8000  
**Location**: `src/api/`

#### Endpoints

**`POST /match`**: Find matching company record
- Input: Company name, website, phone, social URLs
- Output: Best match with confidence score (0.0-1.0)
- Algorithm: Elasticsearch + weighted fuzzy reranking

**`GET /healthz`**: Health check  
**`GET /metrics`**: Prometheus metrics

See [API.md](API.md) for full documentation.

### 6. Evaluation & Benchmarking

**Location**: `src/eval/`

#### evaluate.py
Compare crawler performance:
- Coverage: % sites successfully crawled
- Speed: Total time, sites/second
- Data quality: Extraction accuracy
- Side-by-side comparison reports

**Usage**:
```bash
make benchmark  # Run all crawlers
make evaluate   # Generate comparison report
```

**Output**: `data/reports/benchmark_comparison.md`

## Data Flow

### Benchmarking Workflow (Primary)

```
1. Input CSV (websites)
   ↓
2. Run crawlers (python/node/scrapy)
   ↓
3. Output NDJSON (extracted data)
   ↓
4. Evaluate & compare
   ↓
5. Generate reports
```

**Commands**:
```bash
make benchmark BENCH_CONFIGS="python:aggressive scrapy:balanced"
make evaluate
```

### Full Pipeline Workflow (Optional)

```
1. Input CSV (websites)
   ↓
2. Crawl (any crawler)
   ↓
3. ETL Pipeline
   ├─ Normalize
   ├─ Merge names
   ├─ Dedupe
   └─ Load Elasticsearch
   ↓
4. Query via API
   ↓
5. Match companies
```

**Commands**:
```bash
make demo  # End-to-end with Python crawler
```

## Configuration

### Profile System

Profiles tune performance vs. coverage trade-offs:

| Profile | Concurrency | Timeout | Retries | Use Case |
|---------|-------------|---------|---------|----------|
| `aggressive` | 100 | 8s | 2 | Speed benchmarks |
| `balanced` | 50 | 12s | 3 | Production default |
| `conservative` | 30 | 20s | 5 | Maximum coverage |

**Files**:
- `configs/crawl.policy.yaml` - Base configuration
- `configs/profiles/*.yaml` - Profile overrides

See [CRAWLER_CONFIGURATION.md](CRAWLER_CONFIGURATION.md) for details.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ES_URL` | `http://localhost:9200` | Elasticsearch URL |
| `ES_INDEX` | `companies_v1` | Index name |
| `ES_ALIAS` | `companies` | Index alias |
| `API_DEBUG` | `false` | Enable debug logging |
| `CRAWLER_CONCURRENCY` | `50` | Override concurrency |
| `CRAWLER_TIMEOUT` | `12` | Override timeout |

## Deployment

### Local Development

```bash
# Start services (Elasticsearch + API)
make up

# Run crawler
make crawl-python

# Run full pipeline
make demo

# Stop services
make down
```

### Docker Services

Defined in `docker-compose.yml`:

**elasticsearch**: Single-node cluster, 512MB heap  
**kibana**: Web UI on port 5601  
**api**: FastAPI service, auto-restarts  
**runner**: Shared service for tests/workflows


## Testing

### Unit Tests

**Python**: pytest (300+ tests)
```bash
pytest tests/
```

**Node.js**: mocha (50+ tests)
```bash
cd src/crawlers/node && npm test
```

### Integration Tests

```bash
make test              # All tests in Docker
make test-python       # Python only
make test-node         # Node.js only
```

### Crawler Tests

```bash
# Test individual crawler
make crawl-python INPUT=data/inputs/sample-9-sites.csv

# Test specific crawler+profile combo
pytest tests/crawlers/test_python_crawler.py
```

## Performance

### Typical Throughput

Based on actual benchmark runs with 1001 sites:

| Crawler | Sites/sec | Runtime | Coverage | Datapoints/Site | Quality Score |
|---------|-----------|---------|----------|-----------------|---------------|
| **Scrapy** | **15.2** | **66s** | 64.9% | 1.6 | 0.336 |
| **Scrapy-lite** | 12.8 | 78s | 64.9% | **17.9** | **0.579** |
| **Python** | 3.1 | 319s | 65.2% | 17.7 | 0.571 |
| **Node.js** | 2.4 | 411s | **68.9%** | 6.4 | 0.297 |

**Key Insight**: Scrapy is **5× faster** but extracts **90% less data** than Python. Speed vs. data quality trade-off.

**Quality Score**: Average of phone, social, and address fill rates  
**Data source**: `data/reports/metrics.csv` (1001 site benchmark with aggressive profile)  
**Variables**: Network latency, target site speed, extraction logic differences

### Bottlenecks

1. **Network I/O**: Slowest target site determines batch time
2. **Data extraction**: Minimal overhead (<5ms per page)
3. **Robots.txt lookup**: Cached, negligible after warmup
4. **Elasticsearch indexing**: Bulk inserts, ~1000 docs/sec

### Optimization Tips

**For speed**:
- Use `aggressive` profile
- Increase concurrency to 100-150
- Reduce timeout to 8s
- Skip robots.txt (not recommended)

**For coverage**:
- Use `conservative` profile
- Enable HTTPS→HTTP fallback
- Increase retries to 5
- Respect robots.txt crawl-delay

## Design Decisions

### Why 4 Crawlers?

- **Python**: Ecosystem familiarity, async/await simplicity
- **Node.js**: JavaScript ecosystem, undici performance
- **Scrapy**: Industry standard, battle-tested
- **Scrapy-lite**: Fair comparison with shared extraction

### Why Shared Utility Functions?

- **Consistency**: All crawlers extract data the same way
- **Fair comparison**: Isolates HTTP client performance
- **Maintainability**: Single source of truth for extraction logic
- **Trade-off**: Less flexibility per crawler

### Why NDJSON Output?

- **Streaming**: Process large datasets without loading into memory
- **Append-friendly**: Easy to resume interrupted crawls
- **Line-oriented**: Simple to parse, filter, merge

### Why Elasticsearch?

- **Fuzzy matching**: Built-in fuzzy queries for company names
- **Scalability**: Handles millions of records
- **Relevance scoring**: Boost fields by importance
- **Trade-off**: More complex than PostgreSQL

## Monitoring

### Logs

**Crawler logs**: `stdout` (JSON structured logging planned)  
**API logs**: `stdout` (Uvicorn format)  
**Elasticsearch logs**: Docker logs

### Metrics

**API Metrics** (Prometheus format at `/metrics`):
- Request count: `api_requests_total`
- Match confidence: `match_confidence_distribution`
- ES query duration: `es_query_duration`

### Health Checks

```bash
# API health
curl http://localhost:8000/healthz

# Elasticsearch health
curl http://localhost:9200/_cluster/health

# Kibana
open http://localhost:5601
```

## Limitations

### Current Constraints

- **Single-page extraction**: No JavaScript rendering, no multi-page crawls
- **US-centric**: Address parsing optimized for US format
- **Regex limitations**: May miss complex page structures

### Known Issues

- **SSL errors**: Some sites fail HTTPS, fallback to HTTP helps
- **Rate limiting**: High concurrency may trigger 429 errors
- **Robots.txt delay**: Some sites specify very long delays (30s+)
- **Memory usage**: Large crawls (10k+ sites) may need memory tuning

## Future Enhancements

**Benchmarking**:
- Add Playwright crawler (JavaScript rendering)
- Add curl/libcurl crawler (C performance)
- Distributed crawling benchmarks

**Features**:
- JavaScript rendering support
- Multi-page crawling (follow links)
- Sitemap parsing
- API rate limiting per domain

**Pipeline**:
- Real-time streaming mode
- Incremental updates (delta crawls)
- Data versioning (track changes over time)

## Related Documentation

- **[API Reference](API.md)**: REST API endpoints and examples
- **[Configuration](CRAWLER_CONFIGURATION.md)**: Profile system and tuning
- **[Scalability](SCALABILITY.md)**: Billion-scale deployment
- **[Solution](SOLUTION.md)**: Design decisions and lessons learned
- **[Robots.txt](ROBOTS_TXT_IMPLEMENTATION.md)**: Compliance details
- **[User-Agent Rotation](USER_AGENT_ROTATION.md)**: UA rotation implementation

---

**TL;DR**: Modular crawler benchmarking system with optional ETL → Elasticsearch → API pipeline. Four crawler implementations share common extraction logic for fair comparison. Use `make benchmark` to compare crawlers, `make demo` for full pipeline.
