"""
Configuration module for centralized settings and crawler registry.

Single source of truth for:
- Available crawlers
- Default output paths
- Environment variables
- System-wide constants
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class CrawlerConfig:
    """Configuration for a single crawler."""
    name: str
    output_path: str  # Relative to project root
    profile: str = "default"  # Configuration profile name
    
    @property
    def full_name(self) -> str:
        """
        Return crawler name with profile suffix if not default.
        
        Examples:
            python (default) -> "python"
            python (aggressive) -> "python-aggressive"
        """
        if self.profile == "default":
            return self.name
        return f"{self.name}-{self.profile}"


# Single source of truth for all available crawlers
CRAWLERS: List[CrawlerConfig] = [
    CrawlerConfig(name="python", output_path="data/outputs/python_results.ndjson"),
    CrawlerConfig(name="node", output_path="data/outputs/node_results.ndjson"),
    CrawlerConfig(name="scrapy", output_path="data/outputs/scrapy_results.ndjson"),
    CrawlerConfig(name="scrapy-lite", output_path="data/outputs/scrapy_lite_results.ndjson"),
]


def get_crawler_names() -> List[str]:
    """Return list of all registered crawler names."""
    return [c.name for c in CRAWLERS]


def get_crawler_outputs() -> Dict[str, str]:
    """Return mapping of crawler name to output path."""
    return {c.name: c.output_path for c in CRAWLERS}


def get_results_args() -> List[str]:
    """Return list of name:path pairs for CLI arguments (e.g., --results)."""
    return [f"{c.name}:{c.output_path}" for c in CRAWLERS]


def get_crawler_by_name(name: str) -> CrawlerConfig:
    """Get crawler config by name. Raises ValueError if not found."""
    for c in CRAWLERS:
        if c.name == name:
            return c
    raise ValueError(f"Unknown crawler: {name}. Available: {get_crawler_names()}")
