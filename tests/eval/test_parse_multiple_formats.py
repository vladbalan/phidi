"""Test parsing of multiple crawler output formats using adapters."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.eval.compute_metrics import parse_ndjson
from src.eval.format_adapters import (
    AutoDetectAdapter,
    PythonNodeFormatAdapter,
    ScrapyFormatAdapter,
)


def test_parse_python_node_format():
    """Test parsing Python/Node format with *_url suffixes."""
    data = {
        "domain": "example.com",
        "http_status": 200,
        "response_time_ms": 500.5,
        "phones": ["+1234567890"],
        "facebook_url": "https://facebook.com/example",
        "linkedin_url": "https://linkedin.com/company/example",
        "twitter_url": None,
        "instagram_url": None,
        "address": "123 Main St",
        "error": None,
    }
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
        f.write(json.dumps(data) + "\n")
        temp_path = Path(f.name)
    
    try:
        # Test with explicit adapter
        records = parse_ndjson(temp_path, PythonNodeFormatAdapter())
        assert len(records) == 1
        rec = records[0]
        assert rec.domain == "example.com"
        assert rec.http_status == 200
        assert rec.response_time_ms == 500.5
        assert len(rec.phones) == 1
        assert rec.social["facebook_url"] == "https://facebook.com/example"
        assert rec.social["linkedin_url"] == "https://linkedin.com/company/example"
        assert rec.address == "123 Main St"
        assert rec.is_success
        
        # Test with auto-detect adapter (default)
        records_auto = parse_ndjson(temp_path)
        assert len(records_auto) == 1
        assert records_auto[0].domain == "example.com"
    finally:
        temp_path.unlink()


def test_parse_scrapy_format():
    """Test parsing Scrapy format with status_code and no *_url suffixes."""
    data = {
        "domain": "example.com",
        "status_code": 200,
        "response_time_ms": None,
        "phones": ["+1234567890", "+0987654321"],
        "facebook": "https://facebook.com/example",
        "linkedin": "https://linkedin.com/company/example",
        "twitter": "https://twitter.com/example",
        "instagram": None,
        "address": "456 Oak Ave",
        "error": None,
        "error_message": None,
    }
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
        f.write(json.dumps(data) + "\n")
        temp_path = Path(f.name)
    
    try:
        # Test with explicit adapter
        records = parse_ndjson(temp_path, ScrapyFormatAdapter())
        assert len(records) == 1
        rec = records[0]
        assert rec.domain == "example.com"
        assert rec.http_status == 200  # Mapped from status_code
        assert len(rec.phones) == 2
        assert rec.social["facebook_url"] == "https://facebook.com/example"
        assert rec.social["linkedin_url"] == "https://linkedin.com/company/example"
        assert rec.social["twitter_url"] == "https://twitter.com/example"
        assert rec.address == "456 Oak Ave"
        assert rec.is_success
        
        # Test with auto-detect adapter (default)
        records_auto = parse_ndjson(temp_path)
        assert len(records_auto) == 1
        assert records_auto[0].http_status == 200
    finally:
        temp_path.unlink()


def test_parse_scrapy_failed_crawl():
    """Test parsing Scrapy format with failed crawl (crawled=false)."""
    data = {
        "domain": "example.com",
        "status_code": None,
        "phones": [],
        "facebook": None,
        "linkedin": None,
        "twitter": None,
        "instagram": None,
        "address": None,
        "error": "DNSLookupError",
        "error_message": "DNS lookup failed",
        "crawled": False,
    }
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
        f.write(json.dumps(data) + "\n")
        temp_path = Path(f.name)
    
    try:
        # Test with explicit Scrapy adapter to verify error_message preference
        records = parse_ndjson(temp_path, ScrapyFormatAdapter())
        assert len(records) == 1
        rec = records[0]
        assert rec.domain == "example.com"
        assert rec.http_status is None
        assert not rec.is_success
        assert rec.error == "DNS lookup failed"  # Prefers error_message over error field
    finally:
        temp_path.unlink()


def test_parse_mixed_formats():
    """Test parsing file with mixed Python/Node and Scrapy formats."""
    py_data = {
        "domain": "python.example.com",
        "http_status": 200,
        "facebook_url": "https://facebook.com/py",
    }
    scrapy_data = {
        "domain": "scrapy.example.com",
        "status_code": 200,
        "facebook": "https://facebook.com/scrapy",
    }
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
        f.write(json.dumps(py_data) + "\n")
        f.write(json.dumps(scrapy_data) + "\n")
        temp_path = Path(f.name)
    
    try:
        records = parse_ndjson(temp_path)
        assert len(records) == 2
        
        py_rec = next(r for r in records if r.domain == "python.example.com")
        assert py_rec.http_status == 200
        assert py_rec.social["facebook_url"] == "https://facebook.com/py"
        
        scrapy_rec = next(r for r in records if r.domain == "scrapy.example.com")
        assert scrapy_rec.http_status == 200
        assert scrapy_rec.social["facebook_url"] == "https://facebook.com/scrapy"
    finally:
        temp_path.unlink()
