"""Configuration loading and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Self


@dataclass(frozen=True, slots=True)
class Seed:
    """A crawl starting point and its depth limit."""

    url: str
    max_depth: int
    skip: bool = False


@dataclass(frozen=True, slots=True)
class CrawlConfig:
    """Validated settings for a crawler run."""

    seeds: tuple[Seed, ...]
    skip_urls: tuple[str, ...] = ()
    output_dir: Path = Path("crawled")
    delay_min_seconds: float = 1.0
    delay_max_seconds: float = 3.0
    concurrency: int = 3
    timeout_seconds: float = 30.0
    scroll_attempts: int = 10000

    @classmethod
    def from_file(cls, path: Path) -> Self:
        """Load settings from a JSON file."""
        config_path = path.expanduser().resolve()
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        seeds = tuple(
            Seed(
                url=str(item["url"]),
                max_depth=int(item["max_depth"]),
                skip=bool(item.get("skip", False)),
            )
            for item in raw["seeds"]
        )
        output_dir = Path(raw.get("output_dir", "crawled"))
        if not output_dir.is_absolute():
            output_dir = config_path.parent / output_dir
        config = cls(
            seeds=seeds,
            skip_urls=tuple(str(url) for url in raw.get("skip_urls", ())),
            output_dir=output_dir,
            delay_min_seconds=float(raw.get("delay_min_seconds", 1)),
            delay_max_seconds=float(raw.get("delay_max_seconds", 3)),
            concurrency=int(raw.get("concurrency", 3)),
            timeout_seconds=float(raw.get("timeout_seconds", 30)),
            scroll_attempts=int(raw.get("scroll_attempts", 10000)),
        )
        config.validate()
        return config

    def validate(self) -> None:
        """Raise ``ValueError`` when settings cannot drive a crawl."""
        if not self.seeds:
            raise ValueError("At least one seed is required")
        for seed in self.seeds:
            if seed.max_depth < 0 or not seed.url.startswith(("http://", "https://")):
                raise ValueError(f"Invalid seed: {seed.url}")
        if (
            self.delay_min_seconds < 0
            or self.delay_max_seconds < self.delay_min_seconds
        ):
            raise ValueError("Delay bounds must be non-negative and ordered")
        if (
            self.concurrency < 1
            or self.timeout_seconds <= 0
            or self.scroll_attempts < 0
        ):
            raise ValueError("Concurrency and timeout must be positive")
