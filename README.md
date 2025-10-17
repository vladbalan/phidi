# Phidi - Web Crawler Benchmarking & Comparison

An objective comparison framework for web crawling implementations. Benchmarks Python (httpx), Node.js (undici), Scrapy, and Scrapy-lite across performance profiles to identify the optimal crawler for company data extraction.

## Why This Project?

**Core Question**: Which web crawler performs best for extracting structured data from websites?

This project provides:
- 🔬 **Objective benchmarks** across 4 crawler implementations
- ⚙️ **Profile-based testing** (aggressive, balanced, conservative)
- 📊 **Automated reporting** with side-by-side metrics

## Crawler Implementations

| Crawler | Runtime | HTTP Client | Lines of Code | Tests | Status |
|---------|---------|-------------|---------------|-------|--------|
| **Python** | Python 3.11+ | httpx (async) | 400 | 99 | ✅ Complete |
| **Node.js** | Node.js 20+ | undici | 450 | 59 | ✅ Complete |
| **Scrapy** | Python 3.11+ | Twisted | 150 | Framework | ✅ Complete |
| **Scrapy-lite** | Python 3.11+ | Twisted | 150 | Framework | ✅ Complete |

All crawlers extract: phones (E.164), social media URLs, physical addresses, with robots.txt compliance and user-agent rotation.

## Quick Start - Run Benchmarks

**Prerequisites**: [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)

### Compare All Crawlers
```bash
make demo                                                         # Spins up services and runs python crawler pipeline end to end with reports
make benchmark                                                    # Run all crawlers with default profile
make benchmark BENCH_CONFIGS="python:balanced scrapy:aggressive"  # Compare specific configurations
make evaluate                                                     # Generate comparison reports
```

### Run Individual Crawlers
```bash
make crawl-python PROFILE=aggressive    # Python httpx implementation
make crawl-node PROFILE=balanced        # Node.js undici implementation  
make crawl-scrapy PROFILE=conservative  # Scrapy native extraction
make crawl-scrapy-lite PROFILE=balanced # Scrapy with shared regex utils
```

### Performance Profiles

Profiles control timeout, concurrency, retry logic, and crawl delay:

- **`aggressive`**: Fast, high concurrency (50 workers), minimal delays
- **`balanced`**: Default, respectful crawling (25 workers)  
- **`conservative`**: Slow, very polite (10 workers), maximum delays

Defined in `configs/profiles/*.yaml`

## Benchmark Results

After running benchmarks, compare crawlers side-by-side:

```bash
make evaluate  # Generates reports in data/reports/
```

**Key Metrics**:
- Coverage: % of sites successfully crawled
- Speed: Total runtime and sites/second
- Data Quality: Extraction accuracy for phones, social links, addresses
- Politeness: Robots.txt compliance, request spacing

Results help identify the optimal crawler for your use case (speed vs. politeness tradeoff).

## Architecture

![Architecture Diagram](docs/diagrams/architecture.png)

### Data Extraction Pipeline
```
Input (CSV) → Crawler → Extraction → Output (NDJSON)
```

**Shared Components** (ensures fair comparison):
- Extraction logic: `src/common/extraction_utils.py` (regex-based)
- Robots.txt: `src/common/robots_parser.py` (24h cache)
- User-agent rotation: `src/common/user_agent_rotation.py` (7 browser UAs)
- Configuration: `src/common/config_loader.py` (YAML profiles)

**Crawler-Specific**:
- HTTP client implementation
- Concurrency model (asyncio, threads, Twisted)
- Error handling strategies
- Retry logic

### Full System (Optional)
```
Crawl → ETL → Elasticsearch → Matching API
```

The project includes a complete data pipeline, but the **core focus is crawler benchmarking**.

## Project Structure

```
configs/
├── profiles/          # Performance profiles (aggressive/balanced/conservative)
├── crawl.policy.yaml  # Robots.txt, UA, timeout configs
└── weights.yaml       # Matching algorithm weights (for API)

src/
├── crawlers/
│   ├── python/        # httpx async implementation
│   ├── node/          # undici TypeScript implementation
│   ├── scrapy/        # Scrapy native extraction
│   └── scrapy-lite/   # Scrapy with shared regex utils
├── common/            # Shared utilities (extraction, robots.txt, UA rotation)
├── eval/              # Benchmark comparison and reporting
├── etl/               # ETL pipeline (normalize, merge, dedupe, load)
└── api/               # FastAPI matching service (optional)

data/
├── inputs/            # Sample CSV datasets
├── outputs/           # Crawler results (NDJSON)
└── reports/           # Benchmark comparison reports

tests/                 # pytest (Python) and mocha (Node.js) test suites
```

## Why These Crawlers?

**Python (httpx)**: Modern async/await, native Python ecosystem integration  
**Node.js (undici)**: Official Node.js HTTP client, 5-10× faster than axios  
**Scrapy**: Industry-standard framework, battle-tested at scale  
**Scrapy-lite**: Scrapy performance with shared extraction logic for fair comparison


## Shared Features

All crawler implementations include:

- ✅ **Robots.txt compliance**: 24h cache, fail-open strategy
- ✅ **User-agent rotation**: 7 realistic browser UAs with ethical ID
- ✅ **Data extraction**: Phones (E.164), social URLs, addresses (regex-based)
- ✅ **Error handling**: Exponential backoff, HTTP fallback, timeout management
- ✅ **Configurable profiles**: Tune performance/politeness tradeoffs
- ✅ **NDJSON output**: Streaming-friendly format for large datasets

## Development

### Running Tests
```bash
make test              # All tests in Docker
pytest                 # Python tests (native)
make test-node         # Node.js tests (native)
```

### Running Individual Crawlers
```bash
# Docker (recommended)
make crawl-python INPUT=data/inputs/sample.csv PROFILE=balanced

# Native
python src/crawlers/python/main.py --input data/inputs/sample.csv --profile configs/profiles/balanced.yaml
node src/crawlers/node/dist/index.js --input data/inputs/sample.csv --profile configs/profiles/balanced.yaml
```

### Adding a New Crawler

1. Create directory in `src/crawlers/<name>/`
2. Implement extraction logic using existing examples (TODO: To be implemented as a shared utility)
3. Output NDJSON format: `{"url": "...", "phones": [...], ...}`
4. Add Makefile target: `make crawl-<name>`
5. Add to benchmark configs in `Makefile`
6. Run comparative benchmark: `make benchmark`

## Full Pipeline Usage

The project includes ETL and API components for end-to-end demonstrations:

### Start Services
```bash
make up    # Elasticsearch + API
make down  # Stop services
```

### Match API Example
```bash
curl -X POST http://localhost:8000/match \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Acme Corp", "website": "acme.com"}'
```

See [API Documentation](docs/API.md) for details.

## Documentation

**Benchmarking & Comparison**:
- ⚙️ [Configuration](docs/CRAWLER_CONFIGURATION.md) - Profile system explained
- 🐛 [Improvements](docs/CRAWLER_IMPROVEMENTS.md) - Coverage optimization techniques

**Full Pipeline** (optional):
- 📐 [Architecture](docs/ARCHITECTURE.md) - System design overview
- 📊 [API Reference](docs/API.md) - REST API documentation
- 📈 [Scalability](docs/SCALABILITY.md) - Billion-scale deployment strategy

**Implementation Details**:
- 🤖 [Robots.txt](docs/ROBOTS_TXT_IMPLEMENTATION.md) - Compliance implementation
- 🔄 [User-Agent Rotation](docs/USER_AGENT_ROTATION.md) - UA rotation details
- 💡 [Solution](docs/SOLUTION.md) - Design decisions and lessons learned

## Contributing

**Benchmarking Focus**: New features should help compare crawler performance or improve extraction accuracy across all implementations.

Guidelines:
- Shared utilities go in `src/common/` 
- All features require tests (pytest or mocha)
- Keep it simple: regex over complex parsers

## License

MIT License - Copyright (c) 2025 Vlad Balan

---

**TL;DR**: Run `make demo` to start all services and run one crawler pipeline or `make up && make benchmark` to compare 4 web crawler implementations.