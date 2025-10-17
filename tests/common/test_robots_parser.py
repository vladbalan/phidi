"""
Tests for robots.txt parser and cache.

Covers:
- URL allowability checking
- Crawl-delay extraction
- Cache behavior (TTL, expiration)
- Error handling (fail-open policy)
- Domain extraction edge cases
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from urllib.robotparser import RobotFileParser

from src.common.robots_parser import RobotsCache, AsyncRobotsCache


class TestRobotsCacheBasics:
    """Test basic functionality of RobotsCache."""
    
    def test_init_default_values(self):
        """Test initialization with default values."""
        cache = RobotsCache()
        assert cache._ttl == 86400  # 24 hours
        assert "SpaceCrawler" in cache._default_user_agent
        assert len(cache._cache) == 0
    
    def test_init_custom_values(self):
        """Test initialization with custom values."""
        cache = RobotsCache(ttl_seconds=3600, user_agent="CustomBot/1.0")
        assert cache._ttl == 3600
        assert cache._default_user_agent == "CustomBot/1.0"
    
    def test_extract_domain_full_url(self):
        """Test domain extraction from full URLs."""
        cache = RobotsCache()
        
        assert cache._extract_domain("https://example.com/path") == "example.com"
        assert cache._extract_domain("http://www.example.com") == "www.example.com"
        assert cache._extract_domain("https://sub.example.com:8080/") == "sub.example.com:8080"
    
    def test_extract_domain_bare_domain(self):
        """Test domain extraction from bare domains."""
        cache = RobotsCache()
        
        assert cache._extract_domain("example.com") == "example.com"
        assert cache._extract_domain("www.example.com") == "www.example.com"
    
    def test_clear_cache(self):
        """Test cache clearing."""
        cache = RobotsCache()
        # Manually add entry
        cache._cache["example.com"] = (RobotFileParser(), time.time())
        assert len(cache._cache) == 1
        
        cache.clear_cache()
        assert len(cache._cache) == 0
    
    def test_get_cache_stats(self):
        """Test cache statistics."""
        cache = RobotsCache(ttl_seconds=3600)
        cache._cache["example.com"] = (RobotFileParser(), time.time())
        cache._cache["test.com"] = (RobotFileParser(), time.time())
        
        stats = cache.get_cache_stats()
        assert stats["cached_domains"] == 2
        assert stats["ttl_seconds"] == 3600


class TestRobotsCacheFetching:
    """Test robots.txt fetching and parsing."""
    
    @patch('src.common.robots_parser.RobotFileParser')
    def test_fetch_robots_success(self, mock_parser_class):
        """Test successful robots.txt fetch."""
        # Setup mock
        mock_parser = Mock()
        mock_parser.read = Mock()
        mock_parser_class.return_value = mock_parser
        
        cache = RobotsCache()
        parser = cache._fetch_robots("example.com")
        
        # Verify parser was configured correctly
        mock_parser.set_url.assert_called_once_with("https://example.com/robots.txt")
        mock_parser.read.assert_called_once()
        assert parser == mock_parser
    
    @patch('src.common.robots_parser.RobotFileParser')
    def test_fetch_robots_failure_fail_open(self, mock_parser_class):
        """Test that fetch failures result in fail-open (allow all)."""
        # Setup mock to fail
        mock_parser = Mock()
        mock_parser.read = Mock(side_effect=Exception("Network error"))
        mock_parser_class.return_value = mock_parser
        
        cache = RobotsCache()
        parser = cache._fetch_robots("example.com")
        
        # Should return parser (even though read failed)
        # Parser with no rules allows everything (fail-open)
        assert parser == mock_parser
    
    @patch('src.common.robots_parser.RobotFileParser')
    def test_can_fetch_allowed_url(self, mock_parser_class):
        """Test checking URL that is allowed by robots.txt."""
        # Setup mock parser that allows the URL
        mock_parser = Mock()
        mock_parser.read = Mock()
        mock_parser.can_fetch = Mock(return_value=True)
        mock_parser.crawl_delay = Mock(return_value=None)
        mock_parser_class.return_value = mock_parser
        
        cache = RobotsCache(user_agent="TestBot/1.0")
        can_fetch, delay = cache.can_fetch("https://example.com/products")
        
        assert can_fetch is True
        assert delay is None
        mock_parser.can_fetch.assert_called_once_with("TestBot/1.0", "https://example.com/products")
    
    @patch('src.common.robots_parser.RobotFileParser')
    def test_can_fetch_disallowed_url(self, mock_parser_class):
        """Test checking URL that is disallowed by robots.txt."""
        # Setup mock parser that disallows the URL
        mock_parser = Mock()
        mock_parser.read = Mock()
        mock_parser.can_fetch = Mock(return_value=False)
        mock_parser.crawl_delay = Mock(return_value=None)
        mock_parser_class.return_value = mock_parser
        
        cache = RobotsCache()
        can_fetch, delay = cache.can_fetch("https://example.com/admin")
        
        assert can_fetch is False
        assert delay is None
    
    @patch('src.common.robots_parser.RobotFileParser')
    def test_can_fetch_with_crawl_delay(self, mock_parser_class):
        """Test extracting crawl-delay directive."""
        # Setup mock parser with crawl-delay
        mock_parser = Mock()
        mock_parser.read = Mock()
        mock_parser.can_fetch = Mock(return_value=True)
        mock_parser.crawl_delay = Mock(return_value=5.0)  # 5 seconds
        mock_parser_class.return_value = mock_parser
        
        cache = RobotsCache()
        can_fetch, delay = cache.can_fetch("https://example.com/api")
        
        assert can_fetch is True
        assert delay == 5.0
    
    @patch('src.common.robots_parser.RobotFileParser')
    def test_can_fetch_custom_user_agent(self, mock_parser_class):
        """Test using custom user-agent override."""
        mock_parser = Mock()
        mock_parser.read = Mock()
        mock_parser.can_fetch = Mock(return_value=True)
        mock_parser.crawl_delay = Mock(return_value=None)
        mock_parser_class.return_value = mock_parser
        
        cache = RobotsCache(user_agent="DefaultBot/1.0")
        cache.can_fetch("https://example.com/", user_agent="CustomBot/2.0")
        
        # Should use custom user-agent, not default
        mock_parser.can_fetch.assert_called_once_with("CustomBot/2.0", "https://example.com/")
    
    def test_can_fetch_error_fail_open(self):
        """Test that errors in can_fetch result in fail-open (allow crawl)."""
        cache = RobotsCache()
        
        # Force an error by using invalid domain
        with patch.object(cache, '_get_parser', side_effect=Exception("Test error")):
            can_fetch, delay = cache.can_fetch("https://invalid")
            
            # Should fail-open (allow crawling)
            assert can_fetch is True
            assert delay is None


class TestRobotsCacheCaching:
    """Test caching behavior and TTL."""
    
    @patch('src.common.robots_parser.RobotFileParser')
    def test_cache_hit(self, mock_parser_class):
        """Test that second request uses cached parser."""
        mock_parser = Mock()
        mock_parser.read = Mock()
        mock_parser.can_fetch = Mock(return_value=True)
        mock_parser.crawl_delay = Mock(return_value=None)
        mock_parser_class.return_value = mock_parser
        
        cache = RobotsCache()
        
        # First request - should fetch
        cache.can_fetch("https://example.com/page1")
        assert mock_parser_class.call_count == 1
        
        # Second request to same domain - should use cache
        cache.can_fetch("https://example.com/page2")
        assert mock_parser_class.call_count == 1  # No additional fetch
    
    @patch('src.common.robots_parser.RobotFileParser')
    @patch('time.time')
    def test_cache_expiration(self, mock_time, mock_parser_class):
        """Test that cache expires after TTL."""
        mock_parser = Mock()
        mock_parser.read = Mock()
        mock_parser.can_fetch = Mock(return_value=True)
        mock_parser.crawl_delay = Mock(return_value=None)
        mock_parser_class.return_value = mock_parser
        
        # Start at time 0
        mock_time.return_value = 0
        
        cache = RobotsCache(ttl_seconds=10)  # 10 second TTL
        
        # First request at time 0
        cache.can_fetch("https://example.com/")
        assert mock_parser_class.call_count == 1
        
        # Second request at time 5 (within TTL)
        mock_time.return_value = 5
        cache.can_fetch("https://example.com/")
        assert mock_parser_class.call_count == 1  # Cache hit
        
        # Third request at time 11 (after TTL)
        mock_time.return_value = 11
        cache.can_fetch("https://example.com/")
        assert mock_parser_class.call_count == 2  # Cache miss, refetch
    
    @patch('src.common.robots_parser.RobotFileParser')
    def test_different_domains_cached_separately(self, mock_parser_class):
        """Test that different domains have separate cache entries."""
        mock_parser = Mock()
        mock_parser.read = Mock()
        mock_parser.can_fetch = Mock(return_value=True)
        mock_parser.crawl_delay = Mock(return_value=None)
        mock_parser_class.return_value = mock_parser
        
        cache = RobotsCache()
        
        # Fetch from two different domains
        cache.can_fetch("https://example.com/")
        cache.can_fetch("https://test.com/")
        
        # Should fetch twice (different domains)
        assert mock_parser_class.call_count == 2
        assert len(cache._cache) == 2


class TestAsyncRobotsCache:
    """Test async wrapper around RobotsCache."""
    
    @pytest.mark.asyncio
    async def test_async_can_fetch(self):
        """Test async wrapper delegates to sync cache."""
        async_cache = AsyncRobotsCache()
        
        with patch.object(async_cache._cache, 'can_fetch', return_value=(True, 2.0)) as mock_can_fetch:
            can_fetch, delay = await async_cache.can_fetch("https://example.com/")
            
            assert can_fetch is True
            assert delay == 2.0
            mock_can_fetch.assert_called_once_with("https://example.com/", None)
    
    @pytest.mark.asyncio
    async def test_async_clear_cache(self):
        """Test async cache clearing."""
        async_cache = AsyncRobotsCache()
        
        with patch.object(async_cache._cache, 'clear_cache') as mock_clear:
            async_cache.clear_cache()
            mock_clear.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_async_get_cache_stats(self):
        """Test async cache statistics."""
        async_cache = AsyncRobotsCache()
        
        with patch.object(async_cache._cache, 'get_cache_stats', return_value={"cached_domains": 5}) as mock_stats:
            stats = async_cache.get_cache_stats()
            assert stats["cached_domains"] == 5
            mock_stats.assert_called_once()


class TestRealWorldScenarios:
    """Test realistic scenarios and edge cases."""
    
    @patch('src.common.robots_parser.RobotFileParser')
    def test_typical_robots_txt_with_disallow(self, mock_parser_class):
        """Test typical robots.txt that disallows /admin."""
        mock_parser = Mock()
        mock_parser.read = Mock()
        
        # Simulate robots.txt:
        # User-agent: *
        # Disallow: /admin
        # Crawl-delay: 1
        def can_fetch_impl(ua, url):
            return "/admin" not in url
        
        mock_parser.can_fetch = Mock(side_effect=can_fetch_impl)
        mock_parser.crawl_delay = Mock(return_value=1.0)
        mock_parser_class.return_value = mock_parser
        
        cache = RobotsCache()
        
        # Should allow public pages
        can_fetch, delay = cache.can_fetch("https://example.com/products")
        assert can_fetch is True
        assert delay == 1.0
        
        # Should disallow admin pages
        can_fetch, delay = cache.can_fetch("https://example.com/admin")
        assert can_fetch is False
        assert delay == 1.0
    
    @patch('src.common.robots_parser.RobotFileParser')
    def test_no_robots_txt_allows_all(self, mock_parser_class):
        """Test that missing robots.txt allows all (fail-open)."""
        mock_parser = Mock()
        mock_parser.read = Mock(side_effect=Exception("404 Not Found"))
        mock_parser.can_fetch = Mock(return_value=True)  # Empty parser allows all
        mock_parser.crawl_delay = Mock(return_value=None)
        mock_parser_class.return_value = mock_parser
        
        cache = RobotsCache()
        can_fetch, delay = cache.can_fetch("https://norobots.com/anything")
        
        # Should allow (fail-open)
        assert can_fetch is True
    
    @patch('src.common.robots_parser.RobotFileParser')
    def test_multiple_user_agents(self, mock_parser_class):
        """Test handling multiple user-agent rules."""
        mock_parser = Mock()
        mock_parser.read = Mock()
        
        # Simulate robots.txt with different rules for different bots
        def can_fetch_impl(ua, url):
            if "BadBot" in ua:
                return False
            return True
        
        mock_parser.can_fetch = Mock(side_effect=can_fetch_impl)
        mock_parser.crawl_delay = Mock(return_value=None)
        mock_parser_class.return_value = mock_parser
        
        cache = RobotsCache()
        
        # Good bot should be allowed
        can_fetch, _ = cache.can_fetch("https://example.com/", user_agent="GoodBot/1.0")
        assert can_fetch is True
        
        # Bad bot should be blocked
        can_fetch, _ = cache.can_fetch("https://example.com/", user_agent="BadBot/1.0")
        assert can_fetch is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
