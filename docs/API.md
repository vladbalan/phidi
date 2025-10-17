# API Documentation

FastAPI-based company matching service that finds and ranks company records from Elasticsearch using fuzzy matching and configurable scoring algorithms.

## Overview

The API accepts company information (name, website, phone, social URLs) and returns the best matching company record from the database with a confidence score. It uses a two-stage pipeline:

1. **Candidate Retrieval**: Elasticsearch queries with boosted fields
2. **Reranking**: Weighted scoring algorithm with fuzzy matching

## Quick Start

### Start the API

```bash
# Using Docker Compose (recommended)
make up

# Verify the service is running
curl http://localhost:8000/healthz
```

The API runs on **port 8000** by default.

### Basic Usage

```bash
curl -X POST http://localhost:8000/match \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Arnby",
    "website": "arnby.com"
  }'
```

## Endpoints

### `GET /healthz`

Health check endpoint.

**Response** (200 OK):
```json
{
  "status": "ok"
}
```

---

### `GET /metrics`

Prometheus-compatible metrics endpoint for monitoring.

**Response** (200 OK):
```
# TYPE api_requests_total counter
api_requests_total 142
# TYPE match_confidence_distribution histogram
match_confidence_distribution_bucket{le="0.5"} 12
...
```

**Metrics exposed**:
- `api_requests_total`: Total API requests
- `match_confidence_distribution`: Histogram of match confidence scores
- `matches_found_total{confidence_level}`: Matches by confidence level (high/medium/low)
- `es_query_duration`: Elasticsearch query latency
- `es_candidates_retrieved`: Number of candidates retrieved per query

---

### `POST /match`

Find and rank matching company records.

**Request Body**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `company_name` | string | Yes | Company name (cannot be empty) |
| `website` | string | No | Company website or domain |
| `phone_number` | string | No | Phone number (any format) |
| `facebook_url` | string | No | Facebook page URL |
| `instagram_url` | string | No | Instagram page URL |

**Validation Rules**:
- `company_name` must not be empty or whitespace-only
- At least one field must have meaningful data

**Example Request**:
```json
{
  "company_name": "Acme Corporation",
  "website": "acme.com",
  "phone_number": "+1-555-0123",
  "facebook_url": "https://facebook.com/acmecorp",
  "instagram_url": "https://instagram.com/acmecorp"
}
```

**Response** (200 OK):

| Field | Type | Description |
|-------|------|-------------|
| `match_found` | boolean | Whether a match was found above confidence threshold |
| `confidence` | float | Match confidence score (0.0-1.0) |
| `company` | object\|null | Matched company data (null if no match) |
| `score_breakdown` | object | Detailed scoring breakdown by field |

**Company Object** (when `match_found: true`):

| Field | Type | Description |
|-------|------|-------------|
| `domain` | string\|null | Primary domain |
| `company_name` | string\|null | Company name |
| `phones` | array | Phone numbers in E.164 format |
| `facebook` | string\|null | Canonical Facebook URL |
| `linkedin` | string\|null | LinkedIn URL |
| `twitter` | string\|null | Twitter URL |
| `instagram` | string\|null | Canonical Instagram URL |
| `address` | object\|null | Physical address (street, city, state, zip) |

**Example Response (Match Found)**:
```json
{
  "match_found": true,
  "confidence": 0.92,
  "company": {
    "domain": "acme.com",
    "company_name": "Acme Corporation",
    "phones": ["+15550123"],
    "facebook": "https://facebook.com/acmecorp",
    "linkedin": "https://linkedin.com/company/acme",
    "twitter": "https://twitter.com/acmecorp",
    "instagram": "https://instagram.com/acmecorp",
    "address": {
      "street": "123 Main St",
      "city": "San Francisco",
      "state": "CA",
      "zip": "94102"
    }
  },
  "score_breakdown": {
    "domain": 1.0,
    "name": 0.95,
    "phone": 1.0,
    "social": 0.75
  }
}
```

**Example Response (No Match)**:
```json
{
  "match_found": false,
  "confidence": 0.0,
  "company": null,
  "score_breakdown": {}
}
```

**Example Response (Below Threshold)**:
```json
{
  "match_found": false,
  "confidence": 0.25,
  "company": null,
  "score_breakdown": {
    "domain": 0.0,
    "name": 0.6,
    "phone": 0.0,
    "social": 0.0
  }
}
```

**Error Response** (422 Validation Error):
```json
{
  "detail": [
    {
      "loc": ["body", "company_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## Matching Algorithm

### 1. Input Normalization

All input fields are normalized before matching:

- **Domain**: Extracted from URL, lowercased (e.g., `https://Acme.COM` → `acme.com`)
- **Phone**: Converted to E.164 format (e.g., `(555) 123-4567` → `+15551234567`)
- **Company Name**: Trimmed, lowercased
- **Social URLs**: Canonicalized to standard format
  - Facebook: `facebook.com/username` format
  - Instagram: `instagram.com/username` format

### 2. Candidate Retrieval (Elasticsearch)

Query uses boosted `should` clauses (top 10 candidates):

| Field | Boost | Match Type |
|-------|-------|------------|
| Domain | 10.0 | Exact (term) |
| Company Name | 5.0 | Fuzzy (match) |
| Phone | 3.0 | Exact (term) |
| Facebook | 2.0 | Exact (term) |
| Instagram | 2.0 | Exact (term) |

**Minimum Match**: At least 1 clause must match.

### 3. Reranking Algorithm

Candidates are scored using weighted fuzzy matching:

**Default Weights** (configurable in `configs/weights.yaml`):
- Domain: 40%
- Company Name: 35%
- Phone: 15%
- Social (Facebook + Instagram): 10%

**Scoring Rules**:

| Field | Algorithm | Score |
|-------|-----------|-------|
| Domain | Fuzzy ratio | 0.0-1.0 (1.0 for exact match) |
| Name | Max of ratio/token_sort/partial | 0.0-1.0 (handles word order, substrings) |
| Phone | Exact match in array | 1.0 if found, else 0.0 |
| Social | Exact match (FB or IG) | 1.0 if any match, else 0.0 |

**Final Score** = Σ(field_score × field_weight)

**Confidence Threshold**: 0.3 (default, configurable)
- Matches below threshold are rejected (`match_found: false`)
- Threshold prevents low-quality matches from being returned

### 4. Confidence Levels

| Range | Level | Interpretation |
|-------|-------|----------------|
| 0.9-1.0 | High | Strong match, multiple fields agree |
| 0.7-0.89 | Medium | Good match, some uncertainty |
| 0.3-0.69 | Low | Weak match, requires verification |
| 0.0-0.29 | Rejected | Below threshold, no match returned |

## Configuration

### Scoring Weights

Edit `configs/weights.yaml` to adjust the matching algorithm:

```yaml
domain_weight: 0.40
name_weight: 0.35
phone_weight: 0.15
social_weight: 0.10

# Minimum confidence score to return a match (0.0-1.0)
min_confidence_threshold: 0.3
```

**Notes**:
- Weights are automatically normalized to sum to 1.0
- Higher weight = more importance in final score
- `min_confidence_threshold` is independent of weights

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ES_URL` | `http://localhost:9200` | Elasticsearch URL |
| `ES_INDEX` | `companies_v1` | Elasticsearch index name |
| `ES_ALIAS` | `companies` | Elasticsearch alias (overrides ES_INDEX) |
| `API_DEBUG` | `false` | Enable debug logging (1/true/yes/on) |

**Debug Mode**: Set `API_DEBUG=1` to log:
- Normalized input fields
- Elasticsearch query details
- Candidate preview (top 3)
- Reranking scores and breakdowns
- Match decisions

## Examples

### Exact Domain Match
```bash
curl -X POST http://localhost:8000/match \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Example Inc", "website": "example.com"}'
```
**Expected**: High confidence (0.9+) if domain exists in database.

### Fuzzy Name Match
```bash
curl -X POST http://localhost:8000/match \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Acme Corp", "website": "acme-corporation.com"}'
```
**Expected**: Medium confidence (0.7-0.9) with name variations handled.

### Phone Number Match
```bash
curl -X POST http://localhost:8000/match \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Unknown", "phone_number": "(555) 123-4567"}'
```
**Expected**: Match if phone exists, regardless of input format.

### Social Media Match
```bash
curl -X POST http://localhost:8000/match \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Startup",
    "facebook_url": "https://www.facebook.com/startupcompany"
  }'
```
**Expected**: Match if Facebook URL exists in canonicalized form.

### No Match Scenario
```bash
curl -X POST http://localhost:8000/match \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Nonexistent Company XYZ"}'
```
**Expected**: `{"match_found": false, "confidence": 0.0, "company": null}`

## Testing

### Run API Tests
```bash
# All API tests
pytest tests/api/

# Specific test modules
pytest tests/api/test_api_match.py     # Endpoint tests
pytest tests/api/test_rerank.py        # Scoring algorithm tests
pytest tests/api/test_models.py        # Input validation tests
```

### Manual Testing
```bash
# Start services
make up

# Test health
curl http://localhost:8000/healthz

# Test match endpoint
curl -X POST http://localhost:8000/match \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Test", "website": "test.com"}'

# View metrics
curl http://localhost:8000/metrics
```

## Error Handling

The API follows a **fail-safe** strategy:

- **Input validation errors**: Return 422 with detailed error messages
- **Elasticsearch unavailable**: Return `match_found: false` (graceful degradation)
- **Unexpected exceptions**: Return `match_found: false` (never 500 errors)

This ensures the API remains available even during infrastructure issues.

## Performance

### Typical Latency
- **Elasticsearch query**: 10-50ms
- **Reranking (10 candidates)**: <5ms
- **Total request**: 20-100ms

### Optimization Tips
1. **Reduce candidate size**: Set `size=5` in `search_candidates()` if 10 candidates is excessive
2. **Index optimization**: Ensure Elasticsearch indices use appropriate sharding and replica settings
3. **Cache frequently matched companies**: Add Redis layer for hot companies
4. **Connection pooling**: Elasticsearch client reuses connections by default

### Monitoring
Use `/metrics` endpoint with Prometheus/Grafana:
- Track `api_requests_total` for throughput
- Monitor `match_confidence_distribution` for match quality
- Alert on `es_query_duration` p99 > 200ms

## Integration Guide

### Python Client Example
```python
import requests

def match_company(name: str, website: str = None) -> dict:
    """Match company using API."""
    response = requests.post(
        "http://localhost:8000/match",
        json={
            "company_name": name,
            "website": website,
        },
        timeout=5.0,
    )
    response.raise_for_status()
    return response.json()

# Usage
result = match_company("Acme Corp", "acme.com")
if result["match_found"]:
    print(f"Found: {result['company']['company_name']}")
    print(f"Confidence: {result['confidence']:.2f}")
else:
    print("No match found")
```

### JavaScript/Node.js Client Example
```javascript
async function matchCompany(companyName, website = null) {
  const response = await fetch('http://localhost:8000/match', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      company_name: companyName,
      website: website,
    }),
  });
  
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

// Usage
const result = await matchCompany('Acme Corp', 'acme.com');
if (result.match_found) {
  console.log(`Found: ${result.company.company_name}`);
  console.log(`Confidence: ${result.confidence.toFixed(2)}`);
} else {
  console.log('No match found');
}
```

### Batch Processing
For bulk matching, the project includes an async batch evaluation script with controlled concurrency:

**Basic Usage:**
```bash
# Async mode (default, requires aiohttp)
make api-batch-eval

# Or run directly with custom settings
python scripts/api_batch_eval.py \
  --input data/inputs/api-input-sample.csv \
  --concurrency 10

# Sync mode (fallback)
python scripts/api_batch_eval.py --sync
```

**Performance:**
- **Async mode**: 314 req/s with concurrency=10 (default)
- **Sync mode**: 253 req/s (sequential processing)
- **19% faster** wall-clock time for batch operations

**Command-line Options:**
```bash
python scripts/api_batch_eval.py \
  --input INPUT.csv \
  --csv-out results.csv \
  --summary-out summary.json \
  --report-out report.md \
  --concurrency 20 \
  --timeout 10.0 \
  --api-url http://localhost:8000
```

| Option | Default | Description |
|--------|---------|-------------|
| `--input` | `data/inputs/api-input-sample.csv` | Input CSV file |
| `--csv-out` | `data/reports/api_match_results.csv` | Output results CSV |
| `--summary-out` | `data/reports/api_match_summary.json` | Output summary JSON |
| `--report-out` | None | Output markdown report (optional) |
| `--api-url` | `http://localhost:8000` | API base URL |
| `--concurrency` | `10` | Max concurrent requests (async mode) |
| `--timeout` | `10.0` | Request timeout in seconds |
| `--sync` | False | Force synchronous mode |
| `--limit` | None | Process only first N rows (debug) |

**Async Implementation Details:**

The async version uses:
- **aiohttp** for concurrent HTTP requests
- **Semaphore** for concurrency control
- **Connection pooling** for efficiency
- **asyncio.gather** for parallel execution

**Production Recommendations:**
- Start with `--concurrency 10` (default)
- Increase to 20-50 for high-throughput APIs
- Monitor API response times and adjust accordingly
- Use `--timeout` to prevent hanging requests

**Programmatic Usage (Python):**
```python
import asyncio
import aiohttp

async def match_batch(companies: list[dict], concurrency: int = 10):
    """Match multiple companies with controlled concurrency."""
    semaphore = asyncio.Semaphore(concurrency)
    
    async def match_one(session, company):
        async with semaphore:
            async with session.post(
                "http://localhost:8000/match",
                json=company,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                return await resp.json()
    
    connector = aiohttp.TCPConnector(limit=concurrency)
    timeout = aiohttp.ClientTimeout(total=10)
    
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        tasks = [match_one(session, c) for c in companies]
        return await asyncio.gather(*tasks)

# Usage
companies = [
    {"company_name": "Acme", "website": "acme.com"},
    {"company_name": "Example", "website": "example.com"},
]
results = asyncio.run(match_batch(companies))
```

**Sync Fallback:**

If `aiohttp` is not installed, the script automatically falls back to synchronous mode:
```bash
[API-BATCH] aiohttp not available, falling back to sync mode
[API-BATCH] Install aiohttp for better performance: pip install aiohttp
```

Install aiohttp for async support:
```bash
pip install aiohttp
```

## Troubleshooting

### No matches returned
- **Check Elasticsearch**: Verify data exists with `curl http://localhost:9200/companies_v1/_count`
- **Enable debug mode**: Set `API_DEBUG=1` to see query details
- **Lower threshold**: Adjust `min_confidence_threshold` in `configs/weights.yaml`

### Low confidence scores
- **Adjust weights**: Increase weight for fields with good data quality
- **Check normalization**: Phone numbers must be E.164, domains lowercased
- **Review input data**: Ensure input matches database format

### Slow responses
- **Check Elasticsearch health**: `curl http://localhost:9200/_cluster/health`
- **Review metrics**: Monitor `es_query_duration` histogram
- **Reduce candidate size**: Lower `size` parameter in `search_candidates()`

### Elasticsearch connection errors
- **Verify network**: Ensure `ES_URL` is reachable from API container
- **Check credentials**: Add authentication if Elasticsearch security is enabled
- **Graceful degradation**: API returns `match_found: false` when ES unavailable

## Architecture

```
┌──────────────┐
│   Client     │
└──────┬───────┘
       │ POST /match
       ▼
┌──────────────────┐
│   FastAPI        │
│   (Port 8000)    │
└──────┬───────────┘
       │
       ├─► 1. Normalize input (domain, phone, social)
       │
       ├─► 2. Query Elasticsearch (top 10 candidates)
       │      ▼
       │   ┌──────────────────┐
       │   │ Elasticsearch    │
       │   │ (Port 9200)      │
       │   └──────────────────┘
       │
       ├─► 3. Rerank with fuzzy matching
       │      (weighted scoring algorithm)
       │
       └─► 4. Return best match (if above threshold)
```

## Related Documentation

- **[Configuration](CRAWLER_CONFIGURATION.md)**: Profile system for crawlers
- **[Architecture](ARCHITECTURE.md)**: Full system design overview
- **[Solution](SOLUTION.md)**: Design decisions and trade-offs

---

**TL;DR**: POST company data to `/match`, get best matching record with confidence score. Configurable scoring weights, graceful error handling, Prometheus metrics included.
