"""
Format adapters for parsing different crawler output formats.

Uses the Strategy pattern to handle multiple NDJSON formats in a clean,
extensible way. Each crawler's format is encapsulated in its own adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class CrawlerFormatAdapter(ABC):
    """Abstract base class for crawler format adapters."""
    
    @abstractmethod
    def get_http_status(self, obj: Dict[str, Any]) -> Optional[int]:
        """Extract HTTP status code from crawler output."""
        pass
    
    @abstractmethod
    def get_response_time_ms(self, obj: Dict[str, Any]) -> Optional[float]:
        """Extract response time in milliseconds."""
        pass
    
    @abstractmethod
    def get_phones(self, obj: Dict[str, Any]) -> List[str]:
        """Extract phone numbers list."""
        pass
    
    @abstractmethod
    def get_social_urls(self, obj: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """Extract social media URLs as a dict with standardized keys."""
        pass
    
    @abstractmethod
    def get_address(self, obj: Dict[str, Any]) -> Optional[str]:
        """Extract physical address."""
        pass
    
    @abstractmethod
    def get_error(self, obj: Dict[str, Any]) -> Optional[str]:
        """Extract error message if any."""
        pass
    
    def get_domain(self, obj: Dict[str, Any]) -> str:
        """Extract domain (common across all formats)."""
        return str(obj.get("domain", "")).strip()


class PythonNodeFormatAdapter(CrawlerFormatAdapter):
    """Adapter for Python and Node crawler format."""
    
    def get_http_status(self, obj: Dict[str, Any]) -> Optional[int]:
        return obj.get("http_status")
    
    def get_response_time_ms(self, obj: Dict[str, Any]) -> Optional[float]:
        return obj.get("response_time_ms")
    
    def get_phones(self, obj: Dict[str, Any]) -> List[str]:
        return list(obj.get("phones") or [])
    
    def get_social_urls(self, obj: Dict[str, Any]) -> Dict[str, Optional[str]]:
        return {
            "facebook_url": obj.get("facebook_url"),
            "linkedin_url": obj.get("linkedin_url"),
            "twitter_url": obj.get("twitter_url"),
            "instagram_url": obj.get("instagram_url"),
        }
    
    def get_address(self, obj: Dict[str, Any]) -> Optional[str]:
        return obj.get("address")
    
    def get_error(self, obj: Dict[str, Any]) -> Optional[str]:
        return obj.get("error")


class ScrapyFormatAdapter(CrawlerFormatAdapter):
    """Adapter for Scrapy crawler format."""
    
    def get_http_status(self, obj: Dict[str, Any]) -> Optional[int]:
        # Scrapy uses 'status_code' instead of 'http_status'
        return obj.get("status_code")
    
    def get_response_time_ms(self, obj: Dict[str, Any]) -> Optional[float]:
        return obj.get("response_time_ms")
    
    def get_phones(self, obj: Dict[str, Any]) -> List[str]:
        return list(obj.get("phones") or [])
    
    def get_social_urls(self, obj: Dict[str, Any]) -> Dict[str, Optional[str]]:
        # Scrapy uses 'facebook' instead of 'facebook_url', etc.
        return {
            "facebook_url": obj.get("facebook"),
            "linkedin_url": obj.get("linkedin"),
            "twitter_url": obj.get("twitter"),
            "instagram_url": obj.get("instagram"),
        }
    
    def get_address(self, obj: Dict[str, Any]) -> Optional[str]:
        return obj.get("address")
    
    def get_error(self, obj: Dict[str, Any]) -> Optional[str]:
        # Scrapy can have 'error' or 'error_message'
        return obj.get("error_message") or obj.get("error")


class AutoDetectAdapter(CrawlerFormatAdapter):
    """
    Auto-detecting adapter that tries multiple formats.
    
    Falls back through adapters in order until one yields valid data.
    Useful for mixed-format files or when format is unknown.
    """
    
    def __init__(self, adapters: Optional[List[CrawlerFormatAdapter]] = None):
        self.adapters = adapters or [
            PythonNodeFormatAdapter(),
            ScrapyFormatAdapter(),
        ]
    
    def _try_adapters(self, obj: Dict[str, Any], method_name: str) -> Any:
        """Try each adapter's method until one returns a non-None value."""
        for adapter in self.adapters:
            method = getattr(adapter, method_name)
            result = method(obj)
            if result is not None:
                return result
        return None
    
    def get_http_status(self, obj: Dict[str, Any]) -> Optional[int]:
        return self._try_adapters(obj, "get_http_status")
    
    def get_response_time_ms(self, obj: Dict[str, Any]) -> Optional[float]:
        return self._try_adapters(obj, "get_response_time_ms")
    
    def get_phones(self, obj: Dict[str, Any]) -> List[str]:
        return self._try_adapters(obj, "get_phones") or []
    
    def get_social_urls(self, obj: Dict[str, Any]) -> Dict[str, Optional[str]]:
        # Special handling for social URLs - merge results from all adapters
        result: Dict[str, Optional[str]] = {
            "facebook_url": None,
            "linkedin_url": None,
            "twitter_url": None,
            "instagram_url": None,
        }
        for adapter in self.adapters:
            social = adapter.get_social_urls(obj)
            for key, value in social.items():
                if value is not None and result[key] is None:
                    result[key] = value
        return result
    
    def get_address(self, obj: Dict[str, Any]) -> Optional[str]:
        return self._try_adapters(obj, "get_address")
    
    def get_error(self, obj: Dict[str, Any]) -> Optional[str]:
        return self._try_adapters(obj, "get_error")


# Format adapter registry for specific crawler types
FORMAT_ADAPTERS: Dict[str, CrawlerFormatAdapter] = {
    "python": PythonNodeFormatAdapter(),
    "node": PythonNodeFormatAdapter(),
    "scrapy": ScrapyFormatAdapter(),
}


def get_adapter_for_crawler(crawler_name: str) -> CrawlerFormatAdapter:
    """
    Get the appropriate format adapter for a crawler.
    
    Falls back to AutoDetectAdapter if crawler not registered.
    """
    return FORMAT_ADAPTERS.get(crawler_name.lower(), AutoDetectAdapter())


def get_default_adapter() -> CrawlerFormatAdapter:
    """Get the default adapter (auto-detecting)."""
    return AutoDetectAdapter()
