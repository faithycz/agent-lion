"""Markdown cleanup tests."""

from agent_lion.crawler.content import remove_preamble


def test_removes_content_before_first_heading() -> None:
    """Keep the first heading and all following Markdown content."""
    markdown = "Navigation and page chrome\n\n## Article title\n\nBody text"

    assert remove_preamble(markdown) == "## Article title\n\nBody text"


def test_returns_empty_when_markdown_has_no_heading() -> None:
    """Avoid saving pages that contain no heading-delimited article body."""
    assert remove_preamble("Navigation only\n\nSome page text") == ""
