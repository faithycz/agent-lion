"""Async Playwright crawler."""

from __future__ import annotations

import asyncio
import logging
import random
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Literal
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from fake_useragent import UserAgent
from markdownify import markdownify
from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright.async_api import Error as PlaywrightError

from agent_lion.crawler.config import CrawlConfig, Seed
from agent_lion.crawler.content import remove_preamble
from agent_lion.crawler.policy import content_skip_reason, manual_interaction_reason
from agent_lion.crawler.urls import article_id, is_same_host, is_skipped, normalize_url

LOGGER = logging.getLogger("agent_lion")


@dataclass(frozen=True, slots=True)
class CrawlItem:
    """A URL and its depth in one seed's crawl tree."""

    url: str
    depth: int


@dataclass(frozen=True, slots=True)
class VisitResult:
    """Outcome and extracted links for one frontier URL."""

    item: CrawlItem
    links: list[str]
    status: Literal["visited", "skipped", "failed"]
    fetched: bool = False
    saved: bool = False


@dataclass(slots=True)
class CrawlStats:
    """High-level counts for a seed or a complete crawl run."""

    discovered: int = 0
    fetched: int = 0
    saved: int = 0
    skipped: int = 0
    failed: int = 0

    def record(self, result: VisitResult) -> None:
        """Add one URL outcome to these crawl totals."""
        self.fetched += result.fetched
        self.saved += result.saved
        self.skipped += result.status == "skipped"
        self.failed += result.status == "failed"


class Crawler:
    """Crawl configured seed trees with isolated browser contexts."""

    def __init__(self, config: CrawlConfig) -> None:
        """Create a crawler for validated settings."""
        config.validate()
        self.config = config
        self._semaphore = asyncio.Semaphore(config.concurrency)
        self._ua = UserAgent()
        self._robots: dict[str, RobotFileParser] = {}
        self._robots_lock = asyncio.Lock()
        self._totals = CrawlStats()

    async def run(self) -> None:
        """Crawl each non-skipped seed and close the browser cleanly."""
        self._totals = CrawlStats()
        seeds = tuple(seed for seed in self.config.seeds if not seed.skip)
        skipped_seeds = len(self.config.seeds) - len(seeds)
        started_at = monotonic()
        LOGGER.info(
            "CRAWL START seeds=%d skipped_seeds=%d concurrency=%d output=%s",
            len(seeds),
            skipped_seeds,
            self.config.concurrency,
            self.config.output_dir,
        )
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                await asyncio.gather(
                    *(self._crawl_seed(browser, seed) for seed in seeds)
                )
            finally:
                await browser.close()
        LOGGER.info(
            "CRAWL COMPLETE duration=%.1fs discovered=%d fetched=%d saved=%d "
            "skipped=%d failed=%d",
            monotonic() - started_at,
            self._totals.discovered,
            self._totals.fetched,
            self._totals.saved,
            self._totals.skipped,
            self._totals.failed,
        )

    async def _crawl_seed(self, browser: Browser, seed: Seed) -> None:
        seed_url = normalize_url(seed.url)
        if seed_url is None:
            LOGGER.warning("SKIPPED depth=0 invalid seed: %s", seed.url)
            self._totals.discovered += 1
            self._totals.skipped += 1
            return
        queue: deque[CrawlItem] = deque([CrawlItem(seed_url, 0)])
        seen = {seed_url}
        stats = CrawlStats(discovered=1)
        self._totals.discovered += 1
        LOGGER.info("SEED START depth=0 max_depth=%d url=%s", seed.max_depth, seed_url)
        while queue:
            batch = [
                queue.popleft() for _ in range(min(len(queue), self.config.concurrency))
            ]
            results = await asyncio.gather(
                *(self._visit(browser, seed_url, seed, item) for item in batch)
            )
            for result in results:
                stats.record(result)
                self._totals.record(result)
                for link in result.links:
                    if link not in seen:
                        seen.add(link)
                        queue.append(CrawlItem(link, result.item.depth + 1))
                        LOGGER.info(
                            "DISCOVERED depth=%d from=%s link=%s",
                            result.item.depth + 1,
                            result.item.url,
                            link,
                        )
                        stats.discovered += 1
                        self._totals.discovered += 1
        LOGGER.info(
            "SEED SUMMARY discovered=%d fetched=%d saved=%d skipped=%d failed=%d url=%s",
            stats.discovered,
            stats.fetched,
            stats.saved,
            stats.skipped,
            stats.failed,
            seed_url,
        )

    async def _visit(
        self, browser: Browser, seed_url: str, seed: Seed, item: CrawlItem
    ) -> VisitResult:
        url, depth = item.url, item.depth
        if depth > seed.max_depth:
            LOGGER.info("SKIPPED depth=%d max depth: %s", depth, url)
            return VisitResult(item, [], "skipped")
        if not is_same_host(url, seed_url):
            LOGGER.info("SKIPPED depth=%d external host: %s", depth, url)
            return VisitResult(item, [], "skipped")
        if is_skipped(url, self.config.skip_urls):
            LOGGER.info("SKIPPED depth=%d skip list: %s", depth, url)
            return VisitResult(item, [], "skipped")
        if depth > 0 and (reason := content_skip_reason(url)):
            LOGGER.info("SKIPPED depth=%d %s: %s", depth, reason, url)
            return VisitResult(item, [], "skipped")
        async with self._semaphore:
            await asyncio.sleep(
                random.uniform(
                    self.config.delay_min_seconds, self.config.delay_max_seconds
                )
            )
            if not await self._allowed_by_robots(browser, url):
                LOGGER.info("SKIPPED depth=%d robots.txt: %s", depth, url)
                return VisitResult(item, [], "skipped")
            context: BrowserContext = await browser.new_context(
                user_agent=self._ua.random
            )
            try:
                page = await context.new_page()
                try:
                    LOGGER.info("CRAWLING depth=%d: %s", depth, url)
                    response = await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=self.config.timeout_seconds * 1000,
                    )
                except PlaywrightError as error:
                    LOGGER.warning("FAILED depth=%d %s: %s", depth, url, error)
                    return VisitResult(item, [], "failed")
                if response is not None and response.status >= 400:
                    LOGGER.info(
                        "SKIPPED depth=%d HTTP %d: %s", depth, response.status, url
                    )
                    return VisitResult(item, [], "skipped", fetched=True)
                links = await self._scroll(page, url)
                links.extend(await self._extract_links(page, url))
                links = list(dict.fromkeys(links))
                if depth == 0:
                    LOGGER.info("VISITED depth=0 seed (links only): %s", url)
                    return VisitResult(item, links, "visited", fetched=True)
                barrier = await self._barrier_reason(page, url)
                if barrier:
                    LOGGER.info("SKIPPED depth=%d %s (%s)", depth, url, barrier)
                    return VisitResult(item, [], "skipped", fetched=True)
                if not await self._save(page, url):
                    LOGGER.info("SKIPPED depth=%d no Markdown heading: %s", depth, url)
                    return VisitResult(item, links, "skipped", fetched=True)
                LOGGER.info("VISITED depth=%d saved: %s", depth, url)
                return VisitResult(item, links, "visited", fetched=True, saved=True)
            finally:
                await context.close()

    async def _allowed_by_robots(self, browser: Browser, url: str) -> bool:
        """Check cached robots.txt rules for this host."""
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        async with self._robots_lock:
            parser = self._robots.get(origin)
            if parser is None:
                parser = RobotFileParser(f"{origin}/robots.txt")
                context = await browser.new_context(user_agent=self._ua.random)
                try:
                    response = await context.request.get(
                        f"{origin}/robots.txt",
                        timeout=self.config.timeout_seconds * 1000,
                    )
                    parser.parse(
                        (await response.text()).splitlines() if response.ok else []
                    )
                except PlaywrightError:
                    parser.parse([])
                finally:
                    await context.close()
                self._robots[origin] = parser
        return parser.can_fetch("*", url)

    async def _scroll(self, page: Page, base_url: str) -> list[str]:
        """Scroll each page region to its end while collecting discovered links."""
        if self.config.scroll_attempts == 0:
            return await self._extract_links(page, base_url)
        selectors = ["body", "section.sp-scroll"]
        links: dict[str, None] = {}
        for selector in selectors:
            locator = page.locator(selector).first
            if await locator.count() == 0:
                continue
            try:
                await locator.click(force=True, timeout=1000)
                await locator.evaluate(
                    "element => { if (element !== document.body) { "
                    "element.tabIndex = -1; element.focus(); } }"
                )
            except PlaywrightError as error:
                LOGGER.debug("Could not focus scroll target %s: %s", selector, error)
            no_progress = 0
            attempts = 0
            while no_progress < 3 and attempts < self.config.scroll_attempts:
                before = await locator.evaluate(
                    "element => { const root = element === document.body "
                    "? document.scrollingElement : element; "
                    "return { top: root.scrollTop, height: root.scrollHeight, "
                    "client: root.clientHeight }; }"
                )
                if before["top"] + before["client"] >= before["height"]:
                    # Give lazy loaders a chance to append content at the bottom.
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    after = await locator.evaluate(
                        "element => { const root = element === document.body "
                        "? document.scrollingElement : element; "
                        "return { top: root.scrollTop, height: root.scrollHeight, "
                        "client: root.clientHeight }; }"
                    )
                    if after["height"] <= before["height"]:
                        break
                for link in await self._extract_links(page, base_url):
                    links[link] = None
                try:
                    await page.keyboard.press("PageDown")
                except PlaywrightError as error:
                    LOGGER.debug("Could not scroll page with PageDown: %s", error)
                    break
                await asyncio.sleep(random.uniform(0.5, 1.5))
                attempts += 1
                after = await locator.evaluate(
                    "element => { const root = element === document.body "
                    "? document.scrollingElement : element; "
                    "return { top: root.scrollTop, height: root.scrollHeight }; }"
                )
                if (
                    after["top"] <= before["top"]
                    and after["height"] <= before["height"]
                ):
                    no_progress += 1
                else:
                    no_progress = 0
            for link in await self._extract_links(page, base_url):
                links[link] = None
        return list(links)

    async def _extract_links(self, page: Page, base_url: str) -> list[str]:
        """Collect normalized links from the rendered document."""
        raw_links = await page.locator("a[href]").evaluate_all(
            "nodes => nodes.map(node => node.href)"
        )
        return [
            link
            for raw in raw_links
            if (link := normalize_url(raw, base_url)) is not None
        ]

    async def _barrier_reason(self, page: Page, url: str) -> str | None:
        """Detect login forms, CAPTCHA widgets, and continue prompts."""
        has_password = await page.locator('input[type="password"]').count() > 0
        has_captcha = (
            await page.locator(
                'iframe[src*="recaptcha"], .g-recaptcha, #captcha'
            ).count()
            > 0
        )
        has_continue = (
            await page.get_by_role(
                "button",
                name=re.compile(r"continue|verify you are human", re.IGNORECASE),
            ).count()
            > 0
        )
        body_text = (await page.locator("body").inner_text()).lower()
        has_paywall = await page.locator(
            '.paywall, [class*="paywall"]'
        ).count() > 0 or any(
            marker in body_text
            for marker in (
                "subscription required",
                "subscribe to continue",
                "purchase required",
            )
        )
        return manual_interaction_reason(
            url, has_password, has_captcha, has_continue, has_paywall
        )

    async def _save(self, page: Page, url: str) -> bool:
        """Convert rendered HTML and store content starting at its first heading."""
        identifier = article_id(url)
        if identifier is None:
            return False
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", identifier)
        destination: Path = self.config.output_dir / f"{safe_name}.md"
        destination.parent.mkdir(parents=True, exist_ok=True)
        html = await page.locator("body").inner_html()
        markdown = remove_preamble(markdownify(html, heading_style="ATX"))
        if not markdown:
            return False
        destination.write_text(markdown, encoding="utf-8")
        LOGGER.info("SAVED %s", destination)
        return True
