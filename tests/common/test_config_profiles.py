"""
Tests for configuration profile loading and merging.
"""
from pathlib import Path
import pytest

try:
    from src.common.crawler_config import CrawlerConfig, load_crawler_config
    HAS_CONFIG = True
except ImportError:
    HAS_CONFIG = False


@pytest.mark.skipif(not HAS_CONFIG, reason="Config module not available")
class TestConfigProfiles:
    """Test configuration profile loading and merging."""
    
    def test_load_default_config(self):
        """Default config loads without profile."""
        config = load_crawler_config()
        assert config is not None
        assert config.http.timeout_seconds > 0
        assert config.http.concurrency > 0
    
    def test_load_aggressive_profile(self):
        """Aggressive profile overrides concurrency and timeout."""
        config = load_crawler_config(profile="aggressive")
        assert config is not None
        # Aggressive profile should have higher concurrency
        assert config.http.concurrency == 100
        assert config.http.timeout_seconds == 8
        assert config.retry.max_attempts == 2
    
    def test_load_conservative_profile(self):
        """Conservative profile overrides with slower, more thorough settings."""
        config = load_crawler_config(profile="conservative")
        assert config is not None
        # Conservative profile should have lower concurrency, higher timeout
        assert config.http.concurrency == 30
        assert config.http.timeout_seconds == 20
        assert config.retry.max_attempts == 5
    
    def test_load_balanced_profile(self):
        """Balanced profile matches base config defaults."""
        config = load_crawler_config(profile="balanced")
        assert config is not None
        assert config.http.concurrency == 50
        assert config.http.timeout_seconds == 12
        assert config.retry.max_attempts == 3
    
    def test_profile_inherits_unspecified_values(self):
        """Profile only overrides specified values, inherits rest from base."""
        config = load_crawler_config(profile="aggressive")
        assert config is not None
        # Aggressive profile doesn't specify robots settings
        # These should inherit from base config
        assert hasattr(config, 'robots')
        assert hasattr(config, 'user_agent_rotation')
        assert hasattr(config, 'protocol')
    
    def test_nonexistent_profile_uses_default(self):
        """Non-existent profile falls back to base config."""
        config = load_crawler_config(profile="nonexistent-profile")
        assert config is not None
        # Should use base config values since profile doesn't exist
        # This is graceful degradation - no error thrown
    
    def test_deep_merge_preserves_nested_structure(self):
        """Deep merge correctly handles nested dictionaries."""
        # Test the internal merge logic
        base = {
            "http": {"timeout": 10, "concurrency": 50},
            "retry": {"max_attempts": 3},
        }
        override = {
            "http": {"concurrency": 100},  # Override one nested value
        }
        result = CrawlerConfig._deep_merge_dicts(base, override)
        
        # concurrency should be overridden
        assert result["http"]["concurrency"] == 100
        # timeout should be preserved from base
        assert result["http"]["timeout"] == 10
        # retry should be untouched
        assert result["retry"]["max_attempts"] == 3
    
    def test_profile_path_construction(self):
        """Profile path is correctly constructed relative to base config."""
        # This test verifies the internal path logic
        # Navigate from test file: tests/common/test_config_profiles.py -> project root
        repo_root = Path(__file__).resolve().parents[2]  # tests/common -> tests -> repo_root
        profile_path = repo_root / "configs" / "profiles" / "aggressive.yaml"
        assert profile_path.exists(), f"Profile file should exist: {profile_path}"
