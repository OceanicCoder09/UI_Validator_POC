"""
Page Analyzer module for UI Validation Engine.
Tracks runtime page health, captures uncaught JavaScript exceptions,
monitors browser console errors, and evaluates HTTP response codes and navigation status.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from defect_classifier import (
    CATEGORY_HTTP_ERROR,
    CATEGORY_JAVASCRIPT_ERROR,
    CATEGORY_NAVIGATION_FAILURE,
    DefectRecord,
    create_defect,
)

logger = logging.getLogger(__name__)


class PageAnalyzer:
    """
    Analyzes page-level runtime conditions, console errors, and HTTP status codes.
    """

    def __init__(self):
        self.js_errors: List[str] = []
        self.console_errors: List[str] = []

    def attach_listeners(self, page) -> None:
        """
        Attaches event listeners to the Playwright page to capture runtime exceptions and console logs.
        """
        self.js_errors.clear()
        self.console_errors.clear()

        def handle_page_error(exc):
            msg = str(exc)
            logger.warning(f"Uncaught Page JavaScript Error: {msg}")
            self.js_errors.append(msg)

        def handle_console(msg):
            if msg.type == "error":
                text = msg.text
                # Filter out standard non-critical font/favicon 404 noise if desired
                if not any(ign in text for ign in ("favicon.ico", "DevTools failed")):
                    self.console_errors.append(text)

        page.on("pageerror", handle_page_error)
        page.on("console", handle_console)

    def evaluate_page_health(
        self,
        root_url: str,
        page_url: str,
        page_title: str,
        http_status: int,
        navigation_error: Optional[str] = None,
        evidence_b64: str = "",
    ) -> List[DefectRecord]:
        """
        Evaluates page-level HTTP responses, navigation failures, and JavaScript errors.
        Returns a list of DefectRecord objects.
        """
        defects: List[DefectRecord] = []

        # 1. Navigation / Load Failure
        if navigation_error:
            defects.append(create_defect(
                root_url=root_url,
                crawled_url=page_url,
                page_title=page_title or "(Navigation Error)",
                element_type="Page",
                element_identifier=page_url,
                element_selector="html",
                expected_behavior="Browser should successfully navigate and render the page.",
                actual_behavior=f"Navigation failed with error: {navigation_error}",
                defect_category=CATEGORY_NAVIGATION_FAILURE,
                status="FAIL",
                http_status=http_status or 0,
                error_message=navigation_error,
                evidence_image_b64=evidence_b64,
                confidence=1.0,
                severity="Critical",
            ))
            return defects

        # 2. HTTP Status Code Errors (4xx Client Error, 5xx Server Error)
        if http_status >= 400:
            defects.append(create_defect(
                root_url=root_url,
                crawled_url=page_url,
                page_title=page_title,
                element_type="Page",
                element_identifier=page_url,
                element_selector="html",
                expected_behavior="Page URL should return HTTP 200 OK.",
                actual_behavior=f"Server returned HTTP status {http_status}.",
                defect_category=CATEGORY_HTTP_ERROR,
                status="FAIL",
                http_status=http_status,
                error_message=f"HTTP {http_status} returned for page {page_url}",
                evidence_image_b64=evidence_b64,
                confidence=1.0,
                severity="Critical" if http_status in (404, 500, 502, 503) else "Major",
            ))

        # 3. Uncaught JavaScript Runtime Errors
        for js_err in self.js_errors:
            defects.append(create_defect(
                root_url=root_url,
                crawled_url=page_url,
                page_title=page_title,
                element_type="JavaScript Runtime",
                element_identifier="window.onerror",
                element_selector="window",
                expected_behavior="Page JavaScript execution should complete without uncaught exceptions.",
                actual_behavior=f"Uncaught JavaScript exception thrown: {js_err[:300]}",
                defect_category=CATEGORY_JAVASCRIPT_ERROR,
                status="FAIL",
                http_status=http_status,
                error_message=f"JS Exception: {js_err[:200]}",
                evidence_image_b64=evidence_b64,
                confidence=0.95,
                severity="Critical",
            ))

        # 4. Critical Console Error Logs
        for con_err in self.console_errors[:5]:  # Cap at top 5 console errors to avoid flooding
            defects.append(create_defect(
                root_url=root_url,
                crawled_url=page_url,
                page_title=page_title,
                element_type="Console",
                element_identifier="console.error",
                element_selector="console",
                expected_behavior="Browser console should not log fatal application runtime errors.",
                actual_behavior=f"Console error logged: {con_err[:300]}",
                defect_category=CATEGORY_JAVASCRIPT_ERROR,
                status="FAIL",
                http_status=http_status,
                error_message=f"Console Error: {con_err[:200]}",
                evidence_image_b64=evidence_b64,
                confidence=0.85,
                severity="Major",
            ))

        return defects
