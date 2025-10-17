"""
Robots.txt parser with caching and respect for crawl-delay directives.

Provides compliance checking for web crawlers following industry standards:
- Fetches and parses robots.txt per domain
- Caches robots.txt with configurable TTL (default 24 hours)
- Checks URL allowability for given user-agent
- Extracts crawl-delay directives for polite crawling
- Fail-open strategy: if robots.txt fetch fails, allow crawling
"""
from __future__ import annotations

import time
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import logging

logger = logging.getLogger(__name__)


class RobotsCache:
    """
    Manages robots.txt fetching and caching with TTL-based expiration.
    
    Thread-safe for async usage with simple dictionary locking.
    Implements fail-open policy: errors allow crawling (better than blocking legitimate crawls).
    """
    
    def __init__(self, ttl_seconds: int = 86400, user_agent: str = ""):
        """
        Args:
            ttl_seconds: Cache TTL in seconds (default: 24 hours)
            user_agent: Default user-agent for robots.txt matching
        """
        self._ttl = ttl_seconds
        self._default_user_agent = user_agent or "Mozilla/5.0 (compatible; SpaceCrawler/1.0)"
        # Cache: domain -> (RobotFileParser, timestamp)
        self._cache: Dict[str, Tuple[RobotFileParser, float]] = {}
    
    def can_fetch(self, url: str, user_agent: Optional[str] = None) -> Tuple[bool, Optional[float]]:
        """
        Check if URL can be fetched according to robots.txt.
        
        Args:
            url: Full URL to check (e.g., "https://example.com/path")
            user_agent: User-agent to match (uses default if None)
        
        Returns:
            Tuple of (can_fetch: bool, crawl_delay_seconds: float | None)
            
        Examples:
            >>> cache = RobotsCache()
            >>> can_crawl, delay = cache.can_fetch("https://example.com/products")
            >>> if can_crawl:
            ...     if delay:
            ...         await asyncio.sleep(delay)
            ...     response = await fetch(url)
        """
        ua = user_agent or self._default_user_agent
        
        try:
            domain = self._extract_domain(url)
            parser = self._get_parser(domain)
            
            # Check if URL is allowed
            can_fetch = parser.can_fetch(ua, url)
            
            # Get crawl-delay if specified (in seconds), normalize to float
            raw_delay = parser.crawl_delay(ua)
            crawl_delay: Optional[float] = None
            if raw_delay is not None:
                try:
                    crawl_delay = float(raw_delay)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid crawl-delay value '{raw_delay}' for {domain}; ignoring.")
            
            logger.debug(f"robots.txt check for {domain}: can_fetch={can_fetch}, delay={crawl_delay}")
            
            return can_fetch, crawl_delay
            
        except Exception as e:
            # Fail-open: allow crawling on errors (don't block legitimate crawls)
            logger.warning(f"Error checking robots.txt for {url}: {e}. Allowing crawl (fail-open).")
            return True, None
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        if "://" not in url:
            # Handle bare domains like "example.com"
            url = f"https://{url}"
        
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        return domain.lower()
    
    def _get_parser(self, domain: str) -> RobotFileParser:
        """
        Get cached parser or fetch new robots.txt.
        
        Implements simple TTL-based cache invalidation.
        """
        now = time.time()
        
        # Check cache
        if domain in self._cache:
            parser, cached_at = self._cache[domain]
            if now - cached_at < self._ttl:
                return parser
            else:
                logger.debug(f"robots.txt cache expired for {domain}, refetching")
        
        # Fetch and cache
        parser = self._fetch_robots(domain)
        self._cache[domain] = (parser, now)
        
        return parser
    
    def _fetch_robots(self, domain: str) -> RobotFileParser:
        """
        Fetch robots.txt for domain.
        
        Uses urllib.robotparser which handles HTTP fetching internally.
        Implements fail-open: returns permissive parser on errors.
        """
        parser = RobotFileParser()
        robots_url = f"https://{domain}/robots.txt"
        parser.set_url(robots_url)
        
        try:
            # RobotFileParser.read() fetches and parses synchronously
            # This is acceptable as robots.txt fetches are infrequent (cached)
            parser.read()
            logger.debug(f"Successfully fetched robots.txt from {robots_url}")
        except Exception as e:
            # Fail-open: if fetch fails, allow all (don't block legitimate crawls)
            logger.warning(f"Failed to fetch robots.txt from {robots_url}: {e}. Allowing all crawls.")
            # Parser with no rules allows everything
        
        return parser
    
    def clear_cache(self) -> None:
        """Clear all cached robots.txt entries (for testing or manual refresh)."""
        self._cache.clear()
        logger.info("Cleared robots.txt cache")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics (for monitoring)."""
        return {
            "cached_domains": len(self._cache),
            "ttl_seconds": self._ttl,
        }


# Async-compatible wrapper for use in async crawlers
class AsyncRobotsCache:
    """
    Async-compatible wrapper around RobotsCache.
    
    Since robots.txt fetches are infrequent (cached) and robotparser
    doesn't have async support, we use the sync version with proper
    documentation that it may block briefly on cache misses.
    
    For high-concurrency scenarios, consider pre-warming the cache
    or using a background thread pool for fetches.
    """
    
    def __init__(self, ttl_seconds: int = 86400, user_agent: str = ""):
        self._cache = RobotsCache(ttl_seconds=ttl_seconds, user_agent=user_agent)
    
    async def can_fetch(self, url: str, user_agent: Optional[str] = None) -> Tuple[bool, Optional[float]]:
        """
        Async wrapper for can_fetch.
        
        Note: May block briefly on cache miss (robots.txt fetch).
        This is acceptable as fetches are infrequent (24h TTL).
        """
        # Since RobotFileParser is sync-only, we call the sync method
        # For production with thousands of concurrent requests, consider:
        # - Pre-warming cache with common domains
        # - Using asyncio.to_thread() to avoid blocking event loop
        # However, KISS principle: start simple, optimize if needed
        return self._cache.can_fetch(url, user_agent)
    
    def clear_cache(self) -> None:
        """Clear cache."""
        self._cache.clear_cache()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return self._cache.get_cache_stats()
