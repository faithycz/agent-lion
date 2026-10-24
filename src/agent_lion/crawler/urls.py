"""URL normalization and crawl policy helpers."""

from __future__ import annotations

import fnmatch
from urllib.parse import parse_qs, urldefrag, urljoin, urlsplit, urlunsplit


def normalize_url(url: str, base_url: str | None = None) -> str | None:
    """Resolve a URL, remove its fragment, and retain query parameters."""
    absolute = urljoin(base_url, url) if base_url else url
    parts = urlsplit(urldefrag(absolute).url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return None
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, "")
    )


def is_same_host(candidate: str, seed: str) -> bool:
    """Return whether candidate belongs to the seed's exact host."""
    return urlsplit(candidate).netloc.lower() == urlsplit(seed).netloc.lower()


def is_skipped(url: str, patterns: tuple[str, ...]) -> bool:
    """Match an exact skip URL or a shell-style URL pattern."""
    return any(
        url == pattern or fnmatch.fnmatchcase(url, pattern) for pattern in patterns
    )


def article_id(url: str) -> str | None:
    """Return an article identifier required for Markdown filenames."""
    query = parse_qs(urlsplit(url).query)
    for key in ("sysparm_article", "sys_kb_id"):
        values = query.get(key)
        if values and values[0].strip():
            return values[0].strip()
    return None


def has_content_path(url: str) -> bool:
    """Return whether the path contains a Service Portal or knowledge segment."""
    return any(
        segment in {"sp", "kb"} for segment in urlsplit(url).path.lower().split("/")
    )
