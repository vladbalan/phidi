"""
Basic smoke test for Scrapy crawler implementation.
Validates that the crawler can be imported and configured correctly.
"""
import sys
from pathlib import Path

# Add Scrapy crawler directory to path to import phidi_spider
_scrapy_dir = Path(__file__).resolve().parents[3] / "src" / "crawlers" / "scrapy"
if str(_scrapy_dir) not in sys.path:
    sys.path.insert(0, str(_scrapy_dir))


def test_scrapy_settings_load():
    """Test that Scrapy settings load correctly with config."""
    from phidi_spider import settings
    
    # Verify essential settings are present
    assert hasattr(settings, 'BOT_NAME')
    assert hasattr(settings, 'ROBOTSTXT_OBEY')
    assert hasattr(settings, 'CONCURRENT_REQUESTS')
    assert hasattr(settings, 'DOWNLOAD_TIMEOUT')
    
    # Verify settings have reasonable values
    assert settings.CONCURRENT_REQUESTS > 0
    assert settings.DOWNLOAD_TIMEOUT > 0
    assert isinstance(settings.ROBOTSTXT_OBEY, bool)


def test_middlewares_import():
    """Test that custom middlewares can be imported."""
    from phidi_spider.middlewares import UserAgentRotationMiddleware, HttpFallbackMiddleware
    
    # Verify middleware classes exist
    assert UserAgentRotationMiddleware is not None
    assert HttpFallbackMiddleware is not None
    
    # Verify middleware can be instantiated
    ua_middleware = UserAgentRotationMiddleware()
    http_middleware = HttpFallbackMiddleware()
    
    assert ua_middleware is not None
    assert http_middleware is not None


def test_pipeline_import():
    """Test that custom pipeline can be imported."""
    from phidi_spider.pipelines import JsonLinesExportPipeline
    
    assert JsonLinesExportPipeline is not None
    
    # Verify pipeline can be instantiated
    pipeline = JsonLinesExportPipeline()
    assert pipeline is not None


def test_spider_import():
    """Test that company spider can be imported."""
    from phidi_spider.spiders.company import CompanySpider
    
    assert CompanySpider is not None
    assert CompanySpider.name == 'company'


def test_extraction_utils_integration():
    """Test that spider can import and use extraction utilities."""
    from src.crawlers.python.extract import (
        extract_phones,
        extract_address
    )
    from src.common.domain_utils import clean_domain
    
    # Verify extraction functions are available
    assert callable(extract_phones)
    assert callable(extract_address)
    assert callable(clean_domain)
    
    # Quick smoke test of extraction functions
    test_html = '<html><body>Call us at 555-1234</body></html>'
    phones = extract_phones(test_html)
    assert isinstance(phones, list)


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
