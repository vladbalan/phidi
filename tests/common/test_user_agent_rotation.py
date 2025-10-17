"""
Tests for user-agent rotation module.

Tests cover:
- Random selection from pool
- Identification suffix handling
- Custom agent lists
- Thread safety (basic verification)
"""
import pytest
from src.common.user_agent_rotation import UserAgentRotator


class TestUserAgentRotatorBasics:
    """Test basic functionality of UserAgentRotator."""
    
    def test_default_initialization(self):
        """Test rotator initializes with default agents."""
        rotator = UserAgentRotator()
        
        # Should have default agents
        assert len(rotator._agents) > 0
        assert all(isinstance(agent, str) for agent in rotator._agents)
    
    def test_custom_agents(self):
        """Test rotator accepts custom agent list."""
        custom_agents = [
            "CustomAgent/1.0",
            "CustomAgent/2.0",
            "CustomAgent/3.0"
        ]
        rotator = UserAgentRotator(agents=custom_agents, identify=False)
        
        # Should use custom agents only
        for _ in range(20):
            ua = rotator.get_random()
            assert ua in custom_agents


class TestUserAgentIdentification:
    """Test identification suffix handling."""
    
    def test_identify_enabled_by_default(self):
        """Test identification is enabled by default."""
        rotator = UserAgentRotator()
        ua = rotator.get_random()
        
        # Should contain identification suffix
        assert "(SpaceCrawler/1.0)" in ua
    
    def test_identify_disabled(self):
        """Test identification can be disabled."""
        rotator = UserAgentRotator(identify=False)
        ua = rotator.get_random()
        
        # Should NOT contain identification suffix
        assert "(SpaceCrawler/1.0)" not in ua
        # Should still be valid user-agent
        assert "Mozilla" in ua or "CustomAgent" in ua
    
    def test_custom_identifier(self):
        """Test custom identifier string."""
        custom_id = "MyCrawler/2.0; +https://example.com"
        rotator = UserAgentRotator(identify=True, identifier=custom_id)
        ua = rotator.get_random()
        
        # Should contain custom identifier
        assert f"({custom_id})" in ua
    
    def test_get_all_with_identification(self):
        """Test get_all() includes identification when enabled."""
        rotator = UserAgentRotator(identify=True)
        all_agents = rotator.get_all()
        
        # All should have identification
        assert all("(SpaceCrawler/1.0)" in ua for ua in all_agents)
    
    def test_get_all_without_identification(self):
        """Test get_all() excludes identification when disabled."""
        rotator = UserAgentRotator(identify=False)
        all_agents = rotator.get_all()
        
        # None should have identification
        assert not any("(SpaceCrawler/1.0)" in ua for ua in all_agents)


class TestUserAgentRandomness:
    """Test random selection behavior."""
    
    def test_returns_different_agents(self):
        """Test that multiple calls return varied agents (probabilistic)."""
        rotator = UserAgentRotator(identify=False)
        
        # Get 50 samples
        samples = [rotator.get_random() for _ in range(50)]
        
        # Should have at least 3 different agents (very high probability)
        unique_agents = set(samples)
        assert len(unique_agents) >= 3, f"Only {len(unique_agents)} unique agents in 50 samples"
    
    def test_all_agents_eventually_selected(self):
        """Test all agents get selected over many samples."""
        custom_agents = ["Agent1", "Agent2", "Agent3"]
        rotator = UserAgentRotator(agents=custom_agents, identify=False)
        
        # Sample many times
        samples = [rotator.get_random() for _ in range(100)]
        unique_samples = set(samples)
        
        # Should have seen all agents
        assert unique_samples == set(custom_agents)


class TestUserAgentRealism:
    """Test that default user-agents are realistic."""
    
    def test_default_agents_look_realistic(self):
        """Test default agents contain expected browser signatures."""
        rotator = UserAgentRotator(identify=False)
        all_agents = rotator.get_all()
        
        # Should have agents from major browsers
        has_chrome = any("Chrome" in ua for ua in all_agents)
        has_firefox = any("Firefox" in ua for ua in all_agents)
        has_safari = any("Safari" in ua for ua in all_agents)
        
        assert has_chrome, "Missing Chrome user-agents"
        assert has_firefox, "Missing Firefox user-agents"
        assert has_safari, "Missing Safari user-agents"
    
    def test_agents_have_modern_versions(self):
        """Test agents contain recent version numbers (not ancient)."""
        rotator = UserAgentRotator(identify=False)
        all_agents = rotator.get_all()
        
        # Check for modern OS versions
        has_modern_windows = any("Windows NT 10.0" in ua for ua in all_agents)
        has_modern_macos = any("Mac OS X 10_15" in ua for ua in all_agents)
        
        assert has_modern_windows, "Missing modern Windows versions"
        assert has_modern_macos, "Missing modern macOS versions"


class TestUserAgentThreadSafety:
    """Test basic thread safety (random module is thread-safe)."""
    
    def test_concurrent_calls(self):
        """Test multiple concurrent calls don't raise exceptions."""
        import concurrent.futures
        
        rotator = UserAgentRotator()
        
        def get_ua():
            return rotator.get_random()
        
        # Run 100 concurrent calls
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_ua) for _ in range(100)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All should succeed and return valid strings
        assert len(results) == 100
        assert all(isinstance(ua, str) for ua in results)
        assert all(len(ua) > 0 for ua in results)


class TestUserAgentEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_custom_agents_uses_defaults(self):
        """Test empty custom agent list falls back to defaults."""
        rotator = UserAgentRotator(agents=None)  # Explicit None
        ua = rotator.get_random()
        
        # Should use defaults
        assert len(ua) > 0
        assert "Mozilla" in ua
    
    def test_single_agent_list(self):
        """Test rotator works with single agent."""
        single_agent = ["OnlyAgent/1.0"]
        rotator = UserAgentRotator(agents=single_agent, identify=False)
        
        # Should always return the same agent
        for _ in range(10):
            assert rotator.get_random() == "OnlyAgent/1.0"
    
    def test_get_all_returns_copy(self):
        """Test get_all() returns a copy (mutations don't affect original)."""
        rotator = UserAgentRotator(identify=False)
        agents1 = rotator.get_all()
        agents2 = rotator.get_all()
        
        # Should be equal but not same object
        assert agents1 == agents2
        
        # Mutating returned list shouldn't affect rotator
        agents1.append("MutatedAgent")
        agents3 = rotator.get_all()
        assert "MutatedAgent" not in agents3
