"""Configuration tests."""

import json
from pathlib import Path

import pytest

from agent_lion.crawler.config import CrawlConfig, Seed


def test_loads_and_validates_config(tmp_path: Path) -> None:
    """Read defaults and configured values from JSON."""
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "seeds": [{"url": "https://example.com", "max_depth": 2}],
                "output_dir": "markdown",
            }
        )
    )

    config = CrawlConfig.from_file(path)

    assert config.seeds[0].url == "https://example.com"
    assert config.concurrency == 3
    assert config.output_dir == tmp_path / "markdown"


def test_rejects_empty_seeds() -> None:
    """Require at least one seed before a run."""
    with pytest.raises(ValueError, match="At least one seed"):
        CrawlConfig(seeds=()).validate()


def test_rejects_invalid_delay_bounds() -> None:
    """Reject negative or reversed delay bounds."""
    config = CrawlConfig(
        seeds=(Seed(url="https://example.com", max_depth=1),),
        delay_min_seconds=2,
        delay_max_seconds=1,
    )

    with pytest.raises(ValueError, match="Delay bounds"):
        config.validate()
