"""
User-Agent rotation for ethical web crawling.

Provides realistic browser user-agent strings with random selection
to mimic diverse traffic patterns while maintaining crawler identification
for transparency.
"""
import random
from typing import List, Optional


class UserAgentRotator:
    """
    Manages user-agent rotation with realistic browser strings.
    
    Features:
    - Realistic user-agents from major browsers (Chrome, Firefox, Safari, Edge)
    - Optional identification suffix for ethical crawling transparency
    - Thread-safe random selection
    
    Example:
        >>> rotator = UserAgentRotator(identify=True)
        >>> ua = rotator.get_random()
        >>> print(ua)
        Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... (SpaceCrawler/1.0)
    """
    
    # Realistic user-agents from major browsers (updated Oct 2025)
    DEFAULT_AGENTS = [
        # Chrome on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        # Chrome on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        # Firefox on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
        # Firefox on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0",
        # Safari on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
        # Edge on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
        # Chrome on Linux
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    ]
    
    def __init__(
        self, 
        agents: Optional[List[str]] = None, 
        identify: bool = True,
        identifier: str = "SpaceCrawler/1.0"
    ):
        """
        Initialize user-agent rotator.
        
        Args:
            agents: Custom user-agent list (uses DEFAULT_AGENTS if None)
            identify: If True, appends identifier for transparency
            identifier: Identification string (e.g., "SpaceCrawler/1.0")
        """
        self._agents = agents if agents else self.DEFAULT_AGENTS
        self._identify = identify
        self._identifier = identifier
    
    def get_random(self) -> str:
        """
        Get random user-agent string.
        
        Returns:
            User-agent string, optionally with crawler identification
        """
        agent = random.choice(self._agents)
        
        # Ethical crawling: identify ourselves for transparency
        if self._identify:
            agent = f"{agent} ({self._identifier})"
        
        return agent
    
    def get_all(self) -> List[str]:
        """
        Get all available user-agents (with identification if enabled).
        
        Returns:
            List of all user-agent strings
        """
        if self._identify:
            return [f"{agent} ({self._identifier})" for agent in self._agents]
        return self._agents.copy()
