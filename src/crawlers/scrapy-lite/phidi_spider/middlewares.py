"""Custom Scrapy middlewares for Phidi crawler."""
import sys
from pathlib import Path

# Add repo root to path
_repo_root = Path(__file__).resolve().parents[4]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))


class UserAgentRotationMiddleware:
    """
    Rotates user-agents per request using existing UserAgentRotator.
    Maintains DRY principle by reusing shared user-agent rotation logic.
    """
    
    def __init__(self):
        self.rotator = None
        try:
            from src.common.user_agent_rotation import UserAgentRotator
            from src.common.crawler_config import load_crawler_config
            
            config = load_crawler_config()
            if config and config.user_agent_rotation.enabled:
                self.rotator = UserAgentRotator(
                    identify=config.user_agent_rotation.identify,
                    identifier="SpaceCrawler/1.0"
                )
        except Exception:
            # Fallback: no rotation
            pass
    
    def process_request(self, request, spider):
        """Inject rotated user-agent into each request."""
        if self.rotator:
            request.headers['User-Agent'] = self.rotator.get_random()
        return None


class HttpFallbackMiddleware:
    """
    Falls back to HTTP if HTTPS fails with SSL errors.
    Implements same protocol fallback logic as existing crawlers.
    """
    
    def __init__(self):
        self.fallback_enabled = True
        self.ssl_error_codes = {'certificate', 'ssl', 'handshake', 'tls'}
        try:
            from src.common.crawler_config import load_crawler_config
            config = load_crawler_config()
            if config:
                self.fallback_enabled = config.protocol.fallback_to_http
        except Exception:
            pass
    
    def process_response(self, request, response, spider):
        """Normal response, no fallback needed."""
        return response
    
    def process_exception(self, request, exception, spider):
        """
        If HTTPS fails with SSL error and fallback enabled,
        retry with HTTP protocol.
        """
        if not self.fallback_enabled:
            return None
        
        # Check if this is an SSL-related error
        error_msg = str(exception).lower()
        is_ssl_error = any(code in error_msg for code in self.ssl_error_codes)
        
        if is_ssl_error and request.url.startswith('https://'):
            # Convert to HTTP and retry
            http_url = request.url.replace('https://', 'http://', 1)
            spider.logger.debug(f"SSL error on {request.url}, retrying with HTTP: {http_url}")
            
            return request.replace(
                url=http_url,
                dont_filter=True,  # Allow retry even if URL was seen
                meta={**request.meta, 'fallback_attempted': True}
            )
        
        return None
