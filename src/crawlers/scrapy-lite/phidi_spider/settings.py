"""
Scrapy settings for Phidi spider.
Loads configuration from configs/crawl.policy.yaml to maintain DRY principle.
Falls back to sensible defaults if config file unavailable.
"""
import os
import sys
import platform
from pathlib import Path

# Add repo root to path for imports
_repo_root = Path(__file__).resolve().parents[4]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# Load centralized config (reuses existing config infrastructure)
try:
    from src.common.crawler_config import load_crawler_config
    # Support profile via environment variable (set by main.py)
    _profile = os.getenv('SCRAPY_CONFIG_PROFILE')
    _config = load_crawler_config(profile=_profile)
    _CONFIG_LOADED = True
except Exception:
    _config = None  # type: ignore
    _CONFIG_LOADED = False


def _safe_concurrency(value: int) -> int:
    """Clamp concurrency to avoid platform-specific limits (e.g., Windows select())."""
    print("Platform:", platform.system())
    if platform.system() == "Windows":
        return max(1, min(value, 4))
    return max(1, min(value, 20))

# Scrapy project name
BOT_NAME = "phidi_spider"

# Spider modules
SPIDER_MODULES = ["phidi_spider.spiders"]
NEWSPIDER_MODULE = "phidi_spider.spiders"

# Robots.txt compliance (from shared config)
ROBOTSTXT_OBEY = _config.robots.enabled if (_CONFIG_LOADED and _config) else True

# Concurrent requests (from shared config)
_RAW_CONCURRENCY = _config.http.concurrency if (_CONFIG_LOADED and _config) else 50
CONCURRENT_REQUESTS = _safe_concurrency(_RAW_CONCURRENCY)

# Download timeout (from shared config)
DOWNLOAD_TIMEOUT = _config.http.timeout_seconds if (_CONFIG_LOADED and _config) else 12

# Retry settings (from shared config)
RETRY_ENABLED = True
RETRY_TIMES = (_config.retry.max_attempts - 1) if (_CONFIG_LOADED and _config) else 2  # Scrapy counts retries, not total attempts

# HTTP settings
DOWNLOAD_DELAY = 0  # No artificial delay; respect crawl-delay from robots.txt
COOKIES_ENABLED = False  # Most company sites don't need cookies
DOWNLOAD_MAXSIZE = 10 * 1024 * 1024  # 10MB max (avoid downloading large files)
DOWNLOAD_WARNSIZE = 5 * 1024 * 1024  # Warn at 5MB

# Redirect settings (from shared config)
REDIRECT_ENABLED = _config.http.follow_redirects if (_CONFIG_LOADED and _config) else True
REDIRECT_MAX_TIMES = _config.http.max_redirects if (_CONFIG_LOADED and _config) else 5

# User-agent (will be overridden by rotation middleware if enabled)
USER_AGENT = _config.http.user_agent if (_CONFIG_LOADED and _config) else "Mozilla/5.0 (compatible; SpaceCrawler/1.0)"

# AutoThrottle (smart rate limiting based on server load)
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.5
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = max(1.0, CONCURRENT_REQUESTS / 2)
AUTOTHROTTLE_DEBUG = False

# Smaller threadpool keeps async reactor handle count below Windows FD cap
REACTOR_THREADPOOL_MAXSIZE = max(4, min(CONCURRENT_REQUESTS, 16))

# DNS caching (improves performance for sites with multiple pages)
DNSCACHE_ENABLED = True
DNSCACHE_SIZE = 10000

# Disable telemetry
TELNETCONSOLE_ENABLED = False

# Configure item pipelines
ITEM_PIPELINES = {
    "phidi_spider.pipelines.JsonLinesExportPipeline": 100,
}

# Middleware configuration
DOWNLOADER_MIDDLEWARES = {
    # Disable default user-agent middleware
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
    # Add custom user-agent rotation middleware
    "phidi_spider.middlewares.UserAgentRotationMiddleware": 400,
    # HTTP/HTTPS fallback middleware
    "phidi_spider.middlewares.HttpFallbackMiddleware": 550,
}

# Logging
LOG_LEVEL = os.getenv("SCRAPY_LOG_LEVEL", "INFO")
LOG_FORMAT = "%(levelname)s: %(message)s"
LOG_DATEFORMAT = "%Y-%m-%d %H:%M:%S"

# Request fingerprinter (deduplication)
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"

# Use Proactor reactor on Windows to avoid select() FD cap

# Feed export settings (used by pipelines)
FEEDS = {}  # Configured per-spider via custom pipeline
