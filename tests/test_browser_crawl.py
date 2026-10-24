"""Local Chromium integration test for the crawler."""

from __future__ import annotations

import asyncio
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import pytest
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from agent_lion.crawler.config import CrawlConfig, Seed
from src.agent_lion.crawler import Crawler


class FixtureHandler(BaseHTTPRequestHandler):
    """Serve article pages and robots rules for a local crawl."""

    requests: ClassVar[list[str]] = []

    def do_GET(self) -> None:
        """Return deterministic fixture content."""
        self.requests.append(self.path)
        if self.path == "/robots.txt":
            body = b"User-agent: *\nDisallow: /kb/blocked\n"
            content_type = "text/plain"
        elif self.path == "/start":
            body = (
                b'<a href="/kb/article?sysparm_article=KB42">article</a>'
                b'<a href="/kb/no-id">no id</a>'
                b'<a href="/kb/blocked?sys_kb_id=KB43">blocked</a>'
                b'<a href="/kb/login?sys_kb_id=KB44">login</a>'
                b'<a href="/kb/hidden?sys_kb_id=KB45">hidden</a>'
            )
            content_type = "text/html"
        elif self.path == "/long":
            body = (
                b'<div style="height: 9000px"></div>'
                b'<a href="/kb/article?sysparm_article=KB46">last article</a>'
            )
            content_type = "text/html"
        elif self.path.startswith("/kb/article?"):
            body = (
                b"<div>Navigation junk</div>"
                b"<h1>Knowledge article</h1><p>Article body</p>"
            )
            content_type = "text/html"
        elif self.path.startswith("/kb/hidden?"):
            body = (
                b"<style>body { display: none; }</style>"
                b"<h1>Hidden article</h1><p>Article body</p>"
            )
            content_type = "text/html"
        elif self.path.startswith("/kb/login?"):
            body = b'<form><input type="password"></form>'
            content_type = "text/html"
        else:
            body = b"Not found"
            content_type = "text/plain"
            self.send_response(404)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """Keep fixture server output quiet."""


def test_crawls_local_articles_with_chromium(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Save eligible articles and avoid restricted or malformed URLs."""
    caplog.set_level(logging.INFO, logger="agent_lion")
    FixtureHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    async def crawl() -> None:
        async with async_playwright() as playwright:
            try:
                browser = await playwright.chromium.launch()
                await browser.close()
            except PlaywrightError as error:
                pytest.skip(f"Chromium is unavailable: {error}")
        origin = f"http://127.0.0.1:{server.server_port}"
        config = CrawlConfig(
            seeds=(Seed(url=f"{origin}/start", max_depth=1),),
            output_dir=tmp_path,
            delay_min_seconds=0,
            delay_max_seconds=0,
            concurrency=2,
            scroll_attempts=0,
        )
        await Crawler(config).run()

    try:
        asyncio.run(crawl())
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    markdown = (tmp_path / "KB42.md").read_text(encoding="utf-8")
    assert "Knowledge article" in markdown
    assert "Article body" in markdown
    assert "Navigation junk" not in markdown
    hidden_markdown = (tmp_path / "KB45.md").read_text(encoding="utf-8")
    assert "Hidden article" in hidden_markdown
    assert not (tmp_path / "KB43.md").exists()
    assert not (tmp_path / "KB44.md").exists()
    assert "/kb/no-id" not in FixtureHandler.requests
    assert "/kb/blocked?sys_kb_id=KB43" not in FixtureHandler.requests
    assert "CRAWL START seeds=1 skipped_seeds=0" in caplog.text
    assert (
        "SEED SUMMARY discovered=6 fetched=4 saved=2 skipped=3 failed=0" in caplog.text
    )
    assert "CRAWL COMPLETE" in caplog.text


def test_discovers_article_at_the_end_of_a_long_page(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scroll to the bottom and enqueue links that only appear there."""
    from src.agent_lion.crawler import engine

    monkeypatch.setattr(engine.random, "uniform", lambda _low, _high: 0)
    FixtureHandler.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    async def crawl() -> None:
        async with async_playwright() as playwright:
            try:
                browser = await playwright.chromium.launch()
                await browser.close()
            except PlaywrightError as error:
                pytest.skip(f"Chromium is unavailable: {error}")
        origin = f"http://127.0.0.1:{server.server_port}"
        config = CrawlConfig(
            seeds=(Seed(url=f"{origin}/long", max_depth=1),),
            output_dir=tmp_path,
            delay_min_seconds=0,
            delay_max_seconds=0,
            concurrency=1,
            scroll_attempts=30,
        )
        await Crawler(config).run()

    try:
        caplog.set_level(logging.INFO, logger="agent_lion")
        asyncio.run(crawl())
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    assert (tmp_path / "KB46.md").exists()
    assert "DISCOVERED depth=1" in caplog.text
    assert "sysparm_article=KB46" in caplog.text
