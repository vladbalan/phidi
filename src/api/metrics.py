"""
Prometheus metrics for API monitoring.
Integrates with Grafana dashboards.
"""

from prometheus_client import Counter, Histogram, Gauge
from functools import wraps
import time

# Request metrics
api_requests_total = Counter(
    'phidi_api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status']
)

api_request_duration = Histogram(
    'phidi_api_request_duration_seconds',
    'API request latency',
    ['method', 'endpoint']
)

# Matching metrics
match_confidence_distribution = Histogram(
    'phidi_match_confidence',
    'Distribution of match confidence scores',
    buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]
)

matches_found_total = Counter(
    'phidi_matches_found_total',
    'Total matches found',
    ['confidence_level']
)

# ES metrics
es_query_duration = Histogram(
    'phidi_es_query_duration_seconds',
    'Elasticsearch query latency'
)

es_candidates_retrieved = Histogram(
    'phidi_es_candidates_count',
    'Number of candidates retrieved from ES',
    buckets=[1, 5, 10, 20, 50, 100]
)

def track_request(func):
    """Decorator to track API request metrics."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            status = 200
            return result
        except Exception as e:
            status = 500
            # Fail safe: return a 200 response with no-match instead of raising
            try:
                from fastapi.responses import JSONResponse  # local import to avoid hard dep
                return JSONResponse(content={"match_found": False, "confidence": 0.0, "company": None, "score_breakdown": {}})
            except Exception:
                return {"match_found": False, "confidence": 0.0, "company": None, "score_breakdown": {}}
        finally:
            duration = time.time() - start_time
            api_request_duration.labels(
                method='POST',
                endpoint='/match'
            ).observe(duration)
            
            api_requests_total.labels(
                method='POST',
                endpoint='/match',
                status=status
            ).inc()
    
    return wrapper