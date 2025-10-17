"""
Centralized crawler configuration loader.
Reads settings from configs/crawl.policy.yaml and provides defaults.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


@dataclass
class HttpConfig:
    """HTTP request settings."""
    timeout_seconds: float = 12.0  # configDefaultOverride.timeout
    concurrency: int = 50  # configDefaultOverride.concurrency
    user_agent: str = "Mozilla/5.0 (compatible; SpaceCrawler/1.0)"
    follow_redirects: bool = True
    max_redirects: int = 5


@dataclass
class RetryConfig:
    """Retry policy with exponential backoff."""
    max_attempts: int = 3
    backoff_base_seconds: float = 0.5
    jitter_max_seconds: float = 0.5
    retry_on: Optional[List[str]] = None
    skip_retry_on: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.retry_on is None:
            self.retry_on = ["timeout", "connection_reset", "connection_refused", "temporary_error"]
        if self.skip_retry_on is None:
            self.skip_retry_on = ["dns_error", "invalid_domain"]


@dataclass
class ProtocolConfig:
    """Protocol fallback settings."""
    try_https_first: bool = True
    fallback_to_http: bool = True
    http_fallback_on: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.http_fallback_on is None:
            self.http_fallback_on = ["ssl_error", "certificate_error", "handshake_error"]


@dataclass
class RobotsConfig:
    """Robots.txt compliance settings."""
    enabled: bool = True
    cache_ttl_seconds: int = 86400  # 24 hours
    respect_crawl_delay: bool = True
    fail_open: bool = True


@dataclass
class UserAgentRotationConfig:
    """User-agent rotation settings."""
    enabled: bool = True
    identify: bool = True


@dataclass
class CrawlerConfig:
    """Complete crawler configuration."""
    http: HttpConfig
    retry: RetryConfig
    protocol: ProtocolConfig
    robots: RobotsConfig
    user_agent_rotation: UserAgentRotationConfig
    
    @staticmethod
    def _deep_merge_dicts(base: dict, override: dict) -> dict:
        """
        Deep merge two dictionaries.
        Values in override take precedence, but nested dicts are merged recursively.
        """
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = CrawlerConfig._deep_merge_dicts(result[key], value)
            else:
                result[key] = value
        return result
    
    @classmethod
    def from_yaml(cls, config_path: Optional[Path] = None, profile: Optional[str] = None) -> CrawlerConfig:
        """
        Load configuration from YAML file, optionally merging with a profile.
        Falls back to defaults if file doesn't exist or YAML not installed.
        
        Args:
            config_path: Path to base config file (defaults to configs/crawl.policy.yaml)
            profile: Profile name to load from configs/profiles/{profile}.yaml
        """
        if config_path is None:
            # Default: repo_root/configs/crawl.policy.yaml
            config_path = Path(__file__).resolve().parents[2] / "configs" / "crawl.policy.yaml"
        
        # Return defaults if YAML not available
        if yaml is None:
            return cls.default()
        
        # Return defaults if config file doesn't exist
        if not config_path.exists():
            return cls.default()
        
        try:
            with config_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            if not data:
                return cls.default()
            
            # If a profile is specified, load and merge it
            if profile:
                profile_path = config_path.parent / "profiles" / f"{profile}.yaml"
                if profile_path.exists():
                    try:
                        with profile_path.open("r", encoding="utf-8") as pf:
                            profile_data = yaml.safe_load(pf)
                        if profile_data:
                            # Deep merge: profile overrides base
                            data = cls._deep_merge_dicts(data, profile_data)
                    except Exception:
                        # If profile loading fails, continue with base config
                        pass
            
            # Extract sections with defaults
            http_data = data.get("http", {})
            retry_data = data.get("retry", {})
            protocol_data = data.get("protocol", {})
            robots_data = data.get("robots", {})
            ua_rotation_data = data.get("user_agent_rotation", {})
            
            return cls(
                http=HttpConfig(
                    timeout_seconds=http_data.get("timeout_seconds", 12.0),  # configDefaultOverride.timeout
                    concurrency=http_data.get("concurrency", 50),  # configDefaultOverride.concurrency
                    user_agent=http_data.get("user_agent", "Mozilla/5.0 (compatible; SpaceCrawler/1.0)"),
                    follow_redirects=http_data.get("follow_redirects", True),
                    max_redirects=http_data.get("max_redirects", 5),
                ),
                retry=RetryConfig(
                    max_attempts=retry_data.get("max_attempts", 3),
                    backoff_base_seconds=retry_data.get("backoff_base_seconds", 0.5),
                    jitter_max_seconds=retry_data.get("jitter_max_seconds", 0.5),
                    retry_on=retry_data.get("retry_on"),
                    skip_retry_on=retry_data.get("skip_retry_on"),
                ),
                protocol=ProtocolConfig(
                    try_https_first=protocol_data.get("try_https_first", True),
                    fallback_to_http=protocol_data.get("fallback_to_http", True),
                    http_fallback_on=protocol_data.get("http_fallback_on"),
                ),
                robots=RobotsConfig(
                    enabled=robots_data.get("enabled", True),
                    cache_ttl_seconds=robots_data.get("cache_ttl_seconds", 86400),
                    respect_crawl_delay=robots_data.get("respect_crawl_delay", True),
                    fail_open=robots_data.get("fail_open", True),
                ),
                user_agent_rotation=UserAgentRotationConfig(
                    enabled=ua_rotation_data.get("enabled", True),
                    identify=ua_rotation_data.get("identify", True),
                ),
            )
        except Exception:
            # If anything goes wrong, return defaults
            return cls.default()
    
    @classmethod
    def default(cls) -> CrawlerConfig:
        """Return default configuration."""
        return cls(
            http=HttpConfig(),
            retry=RetryConfig(),
            protocol=ProtocolConfig(),
            robots=RobotsConfig(),
            user_agent_rotation=UserAgentRotationConfig(),
        )


# Convenience function for quick access
def load_crawler_config(config_path: Optional[Path] = None, profile: Optional[str] = None) -> CrawlerConfig:
    """
    Load crawler configuration from YAML or return defaults.
    
    Args:
        config_path: Path to base config file (defaults to configs/crawl.policy.yaml)
        profile: Profile name to load from configs/profiles/{profile}.yaml
    """
    return CrawlerConfig.from_yaml(config_path, profile)


# Utility function for retry logic
def calculate_backoff(attempt: int, config: RetryConfig) -> float:
    """
    Calculate exponential backoff delay with jitter.
    
    Implements the formula: delay = base * (2 ^ attempt) + random_jitter
    This prevents thundering herd problems when many requests retry simultaneously.
    
    Args:
        attempt: Current retry attempt (0-indexed)
        config: RetryConfig with backoff_base_seconds and jitter_max_seconds
    
    Returns:
        Delay in seconds (float)
    
    Example:
        >>> config = RetryConfig(backoff_base_seconds=0.5, jitter_max_seconds=0.5)
        >>> calculate_backoff(0, config)  # First retry: 0.5s + jitter
        >>> calculate_backoff(1, config)  # Second retry: 1.0s + jitter
        >>> calculate_backoff(2, config)  # Third retry: 2.0s + jitter
    """
    base_delay = (2 ** attempt) * config.backoff_base_seconds
    jitter = random.uniform(0, config.jitter_max_seconds)
    return base_delay + jitter
