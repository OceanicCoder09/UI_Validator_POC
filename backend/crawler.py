"""
Playwright Crawler module for Web UI Quality Validation Engine.
Performs BFS website traversal, enforces origin boundaries, handles redirects and timeouts,
captures runtime console/JS errors, and takes high-resolution viewport screenshots.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Set
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

from config_manager import CrawlConfig
from element_analyzer import ElementAnalyzer
from page_analyzer import PageAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class CrawledPage:
    """
    Encapsulates state, DOM inventory, and runtime diagnostics for a single crawled webpage.
    """
    url: str
    depth: int
    final_url: str = ""
    title: str = ""
    status: int = 0
    duration_ms: int = 0
    screenshot_png: bytes = b""
    elements: List[dict] = field(default_factory=list)
    js_errors: List[str] = field(default_factory=list)
    console_errors: List[str] = field(default_factory=list)
    navigation_error: Optional[str] = None


def launch_browser(playwright_instance):
    """
    Launches headless Chromium with automatic installation fallback if missing.
    """
    try:
        return playwright_instance.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
    except Exception as exc:
        msg = str(exc)
        if "Executable doesn't exist" in msg or "playwright install" in msg:
            logger.info("Playwright Chromium executable missing. Running playwright install chromium...")
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            return playwright_instance.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
        raise exc


def extract_child_links(page, current_page_url: str, config: CrawlConfig) -> List[str]:
    """
    Extracts all candidate href URLs from anchor tags on the current page,
    resolves relative links against the current page URL, and returns normalized crawlable links.
    """
    try:
        raw_hrefs = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => e.getAttribute('href')).filter(Boolean)"
        ) or []
    except Exception as exc:
        logger.warning(f"Link extraction failed on {current_page_url}: {exc}")
        return []

    discovered: List[str] = []
    for raw in raw_hrefs:
        raw_str = (raw or "").strip()
        if not raw_str or raw_str.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        absolute_url = urljoin(current_page_url, raw_str)
        normalized = config.normalize_url(absolute_url)
        if normalized and config.is_crawlable(normalized):
            discovered.append(normalized)

    return discovered


class PlaywrightCrawler:
    """
    Automated crawler utilizing headless Chromium and Playwright.
    """

    def __init__(self, config: CrawlConfig):
        self.config = config

    def crawl(self, progress_callback: Optional[Callable[[str], None]] = None) -> List[CrawledPage]:
        """
        Executes breadth-first search crawl starting from root_url up to max_depth and max_pages.
        """
        root_normalized = self.config.normalize_url(self.config.root_url)
        if not root_normalized:
            raise ValueError("A valid root_url is required for crawling.")

        visited: Set[str] = set()
        queue = deque([(root_normalized, 0)])
        crawled_pages: List[CrawledPage] = []

        logger.info(f"Starting BFS crawl at root: {root_normalized} (max_depth={self.config.max_depth}, max_pages={self.config.max_pages})")

        with sync_playwright() as playwright_instance:
            browser = launch_browser(playwright_instance)
            context = browser.new_context(
                viewport={
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height,
                },
                user_agent=self.config.user_agent,
                ignore_https_errors=True,
            )
            page = context.new_page()
            page_analyzer = PageAnalyzer()

            while queue and len(crawled_pages) < self.config.max_pages:
                current_url, current_depth = queue.popleft()

                if current_url in visited:
                    continue
                visited.add(current_url)

                page_record = CrawledPage(url=current_url, depth=current_depth)
                msg = f"Crawling page {len(crawled_pages) + 1}/{self.config.max_pages} [Depth {current_depth}]: {current_url}"
                logger.info(msg)
                if progress_callback:
                    progress_callback(msg)

                # Attach runtime error and console listeners
                page_analyzer.attach_listeners(page)

                start_time = time.time()
                try:
                    response = None
                    # Attempt navigation with progressive timeout fallbacks
                    try:
                        response = page.goto(
                            current_url,
                            wait_until="networkidle",
                            timeout=self.config.timeout_ms,
                        )
                    except Exception:
                        try:
                            response = page.goto(
                                current_url,
                                wait_until="load",
                                timeout=int(self.config.timeout_ms * 0.75),
                            )
                        except Exception:
                            response = page.goto(
                                current_url,
                                wait_until="domcontentloaded",
                                timeout=int(self.config.timeout_ms * 0.5),
                            )

                    page_record.duration_ms = int((time.time() - start_time) * 1000)
                    page_record.final_url = page.url or current_url
                    page_record.status = response.status if response else 200

                    # Optional settling wait for client-side JS hydration / animations
                    if self.config.wait_seconds > 0:
                        page.wait_for_timeout(int(self.config.wait_seconds * 1000))

                    page_record.title = page.title() or ""

                    # Extract DOM elements
                    page_record.elements = ElementAnalyzer.extract_elements(page)

                    # Capture high-resolution viewport screenshot
                    page_record.screenshot_png = page.screenshot(
                        full_page=False,
                        type="png"
                    )

                    # Store JS & console runtime logs
                    page_record.js_errors = list(page_analyzer.js_errors)
                    page_record.console_errors = list(page_analyzer.console_errors)

                    # Enqueue internal child links if depth allows
                    if current_depth < self.config.max_depth:
                        child_links = extract_child_links(page, page.url or current_url, self.config)
                        for link in child_links:
                            if link not in visited:
                                queue.append((link, current_depth + 1))

                except Exception as exc:
                    page_record.navigation_error = str(exc)
                    page_record.duration_ms = int((time.time() - start_time) * 1000)
                    logger.error(f"Error while crawling {current_url}: {exc}")

                crawled_pages.append(page_record)

            context.close()
            browser.close()

        logger.info(f"Crawl completed. Total pages crawled: {len(crawled_pages)}")
        return crawled_pages
