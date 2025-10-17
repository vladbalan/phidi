"""Tests for format adapters."""

from __future__ import annotations

from src.eval.format_adapters import (
    AutoDetectAdapter,
    PythonNodeFormatAdapter,
    ScrapyFormatAdapter,
    get_adapter_for_crawler,
    get_default_adapter,
)


def test_python_node_adapter():
    """Test PythonNodeFormatAdapter extracts fields correctly."""
    adapter = PythonNodeFormatAdapter()
    obj = {
        "domain": "example.com",
        "http_status": 200,
        "response_time_ms": 500.5,
        "phones": ["+1234567890", "+0987654321"],
        "facebook_url": "https://facebook.com/example",
        "linkedin_url": "https://linkedin.com/company/example",
        "twitter_url": None,
        "instagram_url": "https://instagram.com/example",
        "address": "123 Main St",
        "error": None,
    }
    
    assert adapter.get_domain(obj) == "example.com"
    assert adapter.get_http_status(obj) == 200
    assert adapter.get_response_time_ms(obj) == 500.5
    assert adapter.get_phones(obj) == ["+1234567890", "+0987654321"]
    
    social = adapter.get_social_urls(obj)
    assert social["facebook_url"] == "https://facebook.com/example"
    assert social["linkedin_url"] == "https://linkedin.com/company/example"
    assert social["twitter_url"] is None
    assert social["instagram_url"] == "https://instagram.com/example"
    
    assert adapter.get_address(obj) == "123 Main St"
    assert adapter.get_error(obj) is None


def test_scrapy_adapter():
    """Test ScrapyFormatAdapter extracts fields correctly."""
    adapter = ScrapyFormatAdapter()
    obj = {
        "domain": "example.com",
        "status_code": 200,
        "response_time_ms": 1200.0,
        "phones": ["+1234567890"],
        "facebook": "https://facebook.com/example",
        "linkedin": "https://linkedin.com/company/example",
        "twitter": "https://twitter.com/example",
        "instagram": None,
        "address": "456 Oak Ave",
        "error": None,
        "error_message": None,
    }
    
    assert adapter.get_domain(obj) == "example.com"
    assert adapter.get_http_status(obj) == 200  # Maps from status_code
    assert adapter.get_response_time_ms(obj) == 1200.0
    assert adapter.get_phones(obj) == ["+1234567890"]
    
    social = adapter.get_social_urls(obj)
    assert social["facebook_url"] == "https://facebook.com/example"
    assert social["linkedin_url"] == "https://linkedin.com/company/example"
    assert social["twitter_url"] == "https://twitter.com/example"
    assert social["instagram_url"] is None
    
    assert adapter.get_address(obj) == "456 Oak Ave"
    assert adapter.get_error(obj) is None


def test_scrapy_adapter_error_message():
    """Test ScrapyFormatAdapter handles error_message field."""
    adapter = ScrapyFormatAdapter()
    obj = {
        "domain": "failed.com",
        "error": "DNSLookupError",
        "error_message": "DNS lookup failed: no results",
        "crawled": False,
    }
    
    # Should prefer error_message over error
    assert adapter.get_error(obj) == "DNS lookup failed: no results"


def test_scrapy_adapter_error_fallback():
    """Test ScrapyFormatAdapter falls back to error field."""
    adapter = ScrapyFormatAdapter()
    obj = {
        "domain": "failed.com",
        "error": "TimeoutError",
        "crawled": False,
    }
    
    assert adapter.get_error(obj) == "TimeoutError"


def test_auto_detect_adapter_python_format():
    """Test AutoDetectAdapter correctly detects Python/Node format."""
    adapter = AutoDetectAdapter()
    obj = {
        "domain": "example.com",
        "http_status": 200,
        "facebook_url": "https://facebook.com/example",
    }
    
    assert adapter.get_http_status(obj) == 200
    social = adapter.get_social_urls(obj)
    assert social["facebook_url"] == "https://facebook.com/example"


def test_auto_detect_adapter_scrapy_format():
    """Test AutoDetectAdapter correctly detects Scrapy format."""
    adapter = AutoDetectAdapter()
    obj = {
        "domain": "example.com",
        "status_code": 200,
        "facebook": "https://facebook.com/example",
    }
    
    assert adapter.get_http_status(obj) == 200
    social = adapter.get_social_urls(obj)
    assert social["facebook_url"] == "https://facebook.com/example"


def test_auto_detect_adapter_mixed_format():
    """Test AutoDetectAdapter handles mixed format with fallback."""
    adapter = AutoDetectAdapter()
    obj = {
        "domain": "example.com",
        "http_status": 200,  # Python/Node style
        "facebook": "https://facebook.com/example",  # Scrapy style
        "linkedin_url": "https://linkedin.com/company/example",  # Python/Node style
    }
    
    assert adapter.get_http_status(obj) == 200
    social = adapter.get_social_urls(obj)
    assert social["facebook_url"] == "https://facebook.com/example"
    assert social["linkedin_url"] == "https://linkedin.com/company/example"


def test_auto_detect_adapter_empty_phones():
    """Test AutoDetectAdapter handles missing phones list."""
    adapter = AutoDetectAdapter()
    obj = {"domain": "example.com", "phones": None}
    
    assert adapter.get_phones(obj) == []


def test_get_adapter_for_crawler_python():
    """Test get_adapter_for_crawler returns correct adapter for python."""
    adapter = get_adapter_for_crawler("python")
    assert isinstance(adapter, PythonNodeFormatAdapter)


def test_get_adapter_for_crawler_node():
    """Test get_adapter_for_crawler returns correct adapter for node."""
    adapter = get_adapter_for_crawler("node")
    assert isinstance(adapter, PythonNodeFormatAdapter)


def test_get_adapter_for_crawler_scrapy():
    """Test get_adapter_for_crawler returns correct adapter for scrapy."""
    adapter = get_adapter_for_crawler("scrapy")
    assert isinstance(adapter, ScrapyFormatAdapter)


def test_get_adapter_for_crawler_unknown():
    """Test get_adapter_for_crawler returns AutoDetectAdapter for unknown."""
    adapter = get_adapter_for_crawler("unknown")
    assert isinstance(adapter, AutoDetectAdapter)


def test_get_adapter_for_crawler_case_insensitive():
    """Test get_adapter_for_crawler is case-insensitive."""
    adapter1 = get_adapter_for_crawler("Python")
    adapter2 = get_adapter_for_crawler("SCRAPY")
    assert isinstance(adapter1, PythonNodeFormatAdapter)
    assert isinstance(adapter2, ScrapyFormatAdapter)


def test_get_default_adapter():
    """Test get_default_adapter returns AutoDetectAdapter."""
    adapter = get_default_adapter()
    assert isinstance(adapter, AutoDetectAdapter)


def test_adapter_domain_whitespace_handling():
    """Test adapters handle domain whitespace correctly."""
    adapter = PythonNodeFormatAdapter()
    obj = {"domain": "  example.com  "}
    assert adapter.get_domain(obj) == "example.com"


def test_adapter_missing_domain():
    """Test adapters handle missing domain."""
    adapter = PythonNodeFormatAdapter()
    obj = {}
    assert adapter.get_domain(obj) == ""
