"""Page barrier checks and article content policy."""

from __future__ import annotations

from urllib.parse import urlsplit

from agent_lion.crawler.urls import article_id, has_content_path

LOGIN_TERMS = {"login", "signin", "sign-in", "signup", "logout", "account"}


def manual_interaction_reason(
    url: str,
    has_password: bool,
    has_captcha: bool,
    has_continue: bool,
    has_paywall: bool = False,
) -> str | None:
    """Describe a detected login or interaction barrier."""
    path = urlsplit(url).path.lower().replace("_", "-")
    if any(term in path for term in LOGIN_TERMS):
        return "login or account path"
    if has_password:
        return "password field"
    if has_captcha:
        return "CAPTCHA"
    if has_continue:
        return "manual continue prompt"
    if has_paywall:
        return "paywall"
    return None


def content_skip_reason(url: str) -> str | None:
    """Return why a non-seed URL cannot be stored as an article."""
    if not has_content_path(url):
        return "path does not contain /sp or /kb"
    if article_id(url) is None:
        return "missing sysparm_article or sys_kb_id query parameter"
    return None
