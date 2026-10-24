"""Command-line entry point."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from agent_lion.crawler.config import CrawlConfig
from src.agent_lion.crawler import Crawler


def main() -> None:
    """Load configuration and run the crawler."""
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Crawl knowledge articles from configured seeds."
    )
    parser.add_argument("--config", type=Path, default=project_root / "config.json")
    arguments = parser.parse_args()
    config_path: Path = arguments.config
    if not config_path.is_absolute() and not config_path.exists():
        config_path = project_root / config_path
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    asyncio.run(Crawler(CrawlConfig.from_file(config_path)).run())


if __name__ == "__main__":
    main()
