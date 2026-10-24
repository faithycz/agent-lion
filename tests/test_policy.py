"""Content policy tests."""

from agent_lion.crawler.policy import content_skip_reason, manual_interaction_reason


def test_detects_manual_interaction_barriers() -> None:
    """Identify sensitive path, form, and CAPTCHA barriers."""
    assert manual_interaction_reason("https://example.com/login", False, False, False)
    assert (
        manual_interaction_reason("https://example.com/kb", True, False, False)
        == "password field"
    )
    assert (
        manual_interaction_reason("https://example.com/kb", False, True, False)
        == "CAPTCHA"
    )


def test_requires_article_path_and_identifier() -> None:
    """Only eligible article URLs can be saved."""
    assert content_skip_reason("https://example.com/other?sysparm_article=KB1")
    assert content_skip_reason("https://example.com/kb")
    assert content_skip_reason("https://example.com/kb?sysparm_article=KB1") is None
