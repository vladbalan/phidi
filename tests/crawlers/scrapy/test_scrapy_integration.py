"""
Basic smoke test for Scrapy crawler implementation (native extraction).
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


def test_items_import():
    """Test that items and processors can be imported."""
    from phidi_spider.items import CompanyItem
    
    assert CompanyItem is not None
    
    # Verify item has expected fields
    item = CompanyItem()
    assert 'domain' in item.fields
    assert 'company_name' in item.fields
    assert 'phones' in item.fields
    assert 'facebook' in item.fields
    assert 'linkedin' in item.fields
    assert 'twitter' in item.fields
    assert 'instagram' in item.fields
    assert 'address' in item.fields


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


def test_spider_import():
    """Test that the company spider can be imported."""
    from phidi_spider.spiders.company import CompanySpider
    
    assert CompanySpider is not None
    assert CompanySpider.name == 'company'
