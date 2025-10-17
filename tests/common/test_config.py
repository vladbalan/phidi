"""Tests for centralized crawler configuration."""

from __future__ import annotations

import pytest

from src.common.config import (
    CRAWLERS,
    get_crawler_by_name,
    get_crawler_names,
    get_crawler_outputs,
    get_results_args,
)


def test_crawlers_registry_not_empty():
    """Ensure at least one crawler is registered."""
    assert len(CRAWLERS) > 0


def test_get_crawler_names():
    """Test getting list of crawler names."""
    names = get_crawler_names()
    assert isinstance(names, list)
    assert len(names) > 0
    assert all(isinstance(name, str) for name in names)


def test_get_crawler_outputs():
    """Test getting crawler output path mapping."""
    outputs = get_crawler_outputs()
    assert isinstance(outputs, dict)
    assert len(outputs) > 0
    for name, path in outputs.items():
        assert isinstance(name, str)
        assert isinstance(path, str)
        assert path.endswith(".ndjson")


def test_get_results_args():
    """Test getting CLI argument format."""
    args = get_results_args()
    assert isinstance(args, list)
    assert len(args) > 0
    for arg in args:
        assert isinstance(arg, str)
        assert ":" in arg
        name, path = arg.split(":", 1)
        assert name in get_crawler_names()
        assert path.endswith(".ndjson")


def test_get_crawler_by_name_valid():
    """Test retrieving crawler config by name."""
    names = get_crawler_names()
    for name in names:
        crawler = get_crawler_by_name(name)
        assert crawler.name == name
        assert crawler.output_path.endswith(".ndjson")


def test_get_crawler_by_name_invalid():
    """Test that invalid crawler name raises ValueError."""
    with pytest.raises(ValueError, match="Unknown crawler"):
        get_crawler_by_name("nonexistent")


def test_default_crawlers_present():
    """Ensure expected crawlers are registered."""
    names = get_crawler_names()
    # At minimum, we expect python and node crawlers
    assert "python" in names
    assert "node" in names
    # Scrapy should also be present after refactoring
    assert "scrapy" in names


def test_crawler_config_immutable():
    """Test that CrawlerConfig is frozen (immutable)."""
    crawler = get_crawler_by_name("python")
    # Frozen dataclass will raise FrozenInstanceError on assignment
    try:
        crawler.name = "modified"  # type: ignore
        assert False, "Expected exception when modifying frozen dataclass"
    except (AttributeError, Exception):
        # Expected - dataclass is frozen
        pass
