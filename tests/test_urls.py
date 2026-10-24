"""URL helper tests."""

from agent_lion.crawler.urls import (
    article_id,
    has_content_path,
    is_same_host,
    is_skipped,
    normalize_url,
)


def test_normalize_url_resolves_relative_and_removes_fragment() -> None:
    """Resolve relative hrefs and remove fragments."""
    assert (
        normalize_url("../kb?id=1#section", "https://example.com/sp/home")
        == "https://example.com/kb?id=1"
    )


def test_host_comparison_preserves_subdomain_boundary() -> None:
    """Require the exact same hostname and port."""
    assert is_same_host("https://support.example.com/a", "https://support.example.com")
    assert not is_same_host(
        "https://www.support.example.com/a", "https://support.example.com"
    )


def test_skip_patterns_support_exact_and_wildcard() -> None:
    """Match exact URLs and configured shell-style patterns."""
    assert is_skipped("https://example.com/logout", ("https://example.com/logout",))
    assert is_skipped(
        "https://example.com/account/settings", ("https://example.com/account/*",)
    )


def test_article_id_and_content_path() -> None:
    """Read supported identifiers and path segments."""
    assert article_id("https://example.com/kb?id=0&sys_kb_id=KB42") == "KB42"
    assert has_content_path("https://example.com/sp?id=article")
    assert not has_content_path("https://example.com/support")
