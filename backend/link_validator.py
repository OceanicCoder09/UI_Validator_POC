"""
Link Validator module for UI Validation Engine.
Inspects anchor links, evaluates URL syntax, resolves relative links,
and detects 4xx/5xx HTTP errors, broken targets, and missing/invalid href attributes.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse
import requests

from defect_classifier import (
    CATEGORY_BROKEN_LINK,
    CATEGORY_HTTP_ERROR,
    DefectRecord,
    create_defect,
)

logger = logging.getLogger(__name__)

# In-memory cache for checked URLs during a run to prevent redundant HTTP requests
_URL_STATUS_CACHE: Dict[str, Tuple[int, str]] = {}


def check_url_status(url: str, timeout_sec: float = 6.0) -> Tuple[int, str]:
    """
    Performs a lightweight HTTP HEAD (or fallback GET) request to check URL responsiveness.
    Returns (status_code, error_message).
    """
    if not url or not url.startswith(("http://", "https://")):
        return 0, "Invalid or non-HTTP URL"

    if url in _URL_STATUS_CACHE:
        return _URL_STATUS_CACHE[url]

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36 LinkValidator/2.0"
        )
    }

    try:
        # Try HEAD request first for efficiency
        resp = requests.head(url, headers=headers, timeout=timeout_sec, allow_redirects=True)
        # If HEAD returns 405 Method Not Allowed or 403, fallback to GET
        if resp.status_code in (403, 405, 501):
            resp = requests.get(url, headers=headers, timeout=timeout_sec, stream=True, allow_redirects=True)
        
        status = resp.status_code
        err = ""
        if status >= 400:
            err = f"HTTP {status} - {resp.reason}"
        _URL_STATUS_CACHE[url] = (status, err)
        return status, err
    except requests.exceptions.Timeout:
        _URL_STATUS_CACHE[url] = (408, "Request Timeout")
        return 408, "Request Timeout"
    except requests.exceptions.SSLError as ssl_err:
        _URL_STATUS_CACHE[url] = (525, f"SSL Handshake Error: {ssl_err}")
        return 525, f"SSL Handshake Error: {ssl_err}"
    except requests.exceptions.ConnectionError:
        _URL_STATUS_CACHE[url] = (503, "Connection Refused / Domain Not Found")
        return 503, "Connection Refused / Domain Not Found"
    except Exception as exc:
        _URL_STATUS_CACHE[url] = (500, f"Network Exception: {str(exc)}")
        return 500, f"Network Exception: {str(exc)}"


class LinkValidator:
    """
    Validates link elements extracted from a webpage DOM.
    """

    def __init__(self, check_live_status: bool = True, timeout_sec: float = 5.0):
        self.check_live_status = check_live_status
        self.timeout_sec = timeout_sec

    def validate_link(
        self,
        root_url: str,
        page_url: str,
        page_title: str,
        link_element: dict,
        evidence_b64: str = "",
    ) -> Optional[DefectRecord]:
        """
        Validates a single link element.
        Returns a DefectRecord if an issue is discovered, otherwise None.
        """
        href = (link_element.get("href") or "").strip()
        text = (link_element.get("text") or link_element.get("ariaLabel") or "").strip()
        selector = link_element.get("selector") or "a"
        bbox = link_element.get("bbox")
        role = (link_element.get("role") or "").lower()
        has_click = link_element.get("hasOnClick", False)

        # 1. Check for completely missing or empty href
        if not href:
            # Anchors used as expandable accordion toggles, tabs, or buttons are valid ARIA controls
            if role in ("button", "tab", "treeitem", "menuitem") or has_click:
                return None

            return create_defect(
                root_url=root_url,
                crawled_url=page_url,
                page_title=page_title,
                element_type="Link",
                element_identifier=text or selector,
                element_selector=selector,
                expected_behavior="Anchor tag must contain a valid, non-empty 'href' attribute pointing to a destination.",
                actual_behavior="Anchor tag is missing an 'href' attribute or href is empty.",
                defect_category=CATEGORY_BROKEN_LINK,
                status="FAIL",
                error_message="Missing or empty 'href' attribute on <a> element.",
                evidence_image_b64=evidence_b64,
                crop_localized_b64=evidence_b64,
                confidence=0.98,
                severity="Major",
                bbox=bbox,
            )

        # 2. Check for dummy javascript:void(0) or naked '#' without button semantics or aria role
        if href in ("#", "javascript:void(0)", "javascript:;", "javascript:void(0);"):
            if role not in ("button", "tab", "treeitem", "menuitem") and not has_click:
                return create_defect(
                    root_url=root_url,
                    crawled_url=page_url,
                    page_title=page_title,
                    element_type="Link",
                    element_identifier=text or selector,
                    element_selector=selector,
                    expected_behavior="Interactive placeholder links should use <button> or provide appropriate ARIA roles and handlers.",
                    actual_behavior=f"Anchor element uses unhandled dummy href='{href}' without button role or action handler.",
                    defect_category=CATEGORY_BROKEN_LINK,
                    status="FAIL",
                    error_message=f"Placeholder link '{href}' without role or click handler.",
                    evidence_image_b64=evidence_b64,
                    crop_localized_b64=evidence_b64,
                    confidence=0.85,
                    severity="Minor",
                    bbox=bbox,
                )
            return None

        # Skip non-HTTP schemes like mailto:, tel:
        parsed = urlparse(href)
        if parsed.scheme in ("mailto", "tel", "sms", "data", "blob", "javascript"):
            return None

        # 3. Resolve absolute URL and test HTTP responsiveness if enabled
        target_absolute_url = urljoin(page_url, href)
        if self.check_live_status and target_absolute_url.startswith(("http://", "https://")):
            status_code, err_msg = check_url_status(target_absolute_url, timeout_sec=self.timeout_sec)
            # Only flag actual dead links: 404 (Not Found), 410 (Gone), or connection errors.
            # HTTP 401, 403, 405, 429, etc. occur due to CDN/WAF anti-bot protections on valid live links.
            if status_code in (404, 410) or (status_code >= 500 and "Refused" in err_msg):
                category = CATEGORY_BROKEN_LINK
                return create_defect(
                    root_url=root_url,
                    crawled_url=page_url,
                    page_title=page_title,
                    element_type="Link",
                    element_identifier=text or href,
                    element_selector=selector,
                    expected_behavior=f"Link target URL '{target_absolute_url}' should be reachable and return HTTP 200.",
                    actual_behavior=f"Link target URL returned HTTP {status_code} ({err_msg}). Target destination does not exist.",
                    defect_category=category,
                    status="FAIL",
                    http_status=status_code,
                    error_message=f"Broken link (HTTP {status_code}) for target {target_absolute_url}",
                    evidence_image_b64=evidence_b64,
                    crop_localized_b64=evidence_b64,
                    confidence=0.95,
                    severity="Critical",
                    bbox=bbox,
                    target_url=target_absolute_url,
                )

        return None

    def validate_all_links(
        self,
        root_url: str,
        page_url: str,
        page_title: str,
        elements: List[dict],
        evidence_b64_map: Optional[Dict[str, str]] = None,
    ) -> List[DefectRecord]:
        """
        Filters and validates all <a> link elements from the page inventory.
        """
        defects: List[DefectRecord] = []
        evidence_b64_map = evidence_b64_map or {}

        for el in elements:
            if el.get("kind") == "link" or el.get("tag") == "a":
                selector = el.get("selector") or ""
                ev = evidence_b64_map.get(selector, "")
                defect = self.validate_link(
                    root_url=root_url,
                    page_url=page_url,
                    page_title=page_title,
                    link_element=el,
                    evidence_b64=ev,
                )
                if defect:
                    defects.append(defect)

        return defects
