"""
Image Validator module for UI Validation Engine.
Inspects <img>, SVG, and graphical elements, validates source URLs,
and detects broken images, zero natural dimensions, load errors, and missing src attributes.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional
from urllib.parse import urljoin

from defect_classifier import (
    CATEGORY_BROKEN_IMAGE,
    CATEGORY_HTTP_ERROR,
    DefectRecord,
    create_defect,
)
from link_validator import check_url_status

logger = logging.getLogger(__name__)


class ImageValidator:
    """
    Validates image elements extracted from a webpage DOM.
    """

    def __init__(self, check_live_src: bool = True):
        self.check_live_src = check_live_src

    def validate_image(
        self,
        root_url: str,
        page_url: str,
        page_title: str,
        img_element: dict,
        evidence_b64: str = "",
    ) -> Optional[DefectRecord]:
        """
        Validates a single image element.
        Returns a DefectRecord if broken or invalid, otherwise None.
        """
        src = (img_element.get("src") or img_element.get("currentSrc") or "").strip()
        alt = (img_element.get("alt") or img_element.get("ariaLabel") or "").strip()
        selector = img_element.get("selector") or "img"
        bbox = img_element.get("bbox")
        natural_w = img_element.get("naturalWidth", 0)
        natural_h = img_element.get("naturalHeight", 0)
        is_broken = img_element.get("imageBroken", False)

        # 1. Check for missing or empty src
        if not src and img_element.get("tag") == "img":
            return create_defect(
                root_url=root_url,
                crawled_url=page_url,
                page_title=page_title,
                element_type="Image",
                element_identifier=alt or selector,
                element_selector=selector,
                expected_behavior="Image tag (<img>) must have a valid 'src' attribute.",
                actual_behavior="Image tag has an empty or missing 'src' attribute.",
                defect_category=CATEGORY_BROKEN_IMAGE,
                status="FAIL",
                error_message="Image missing 'src' attribute.",
                evidence_image_b64=evidence_b64,
                confidence=0.99,
                severity="Critical",
                bbox=bbox,
            )

        # 2. Check for browser rendering failure (complete with 0 naturalWidth/Height)
        if is_broken or (src and natural_w == 0 and natural_h == 0 and img_element.get("tag") == "img"):
            return create_defect(
                root_url=root_url,
                crawled_url=page_url,
                page_title=page_title,
                element_type="Image",
                element_identifier=alt or src,
                element_selector=selector,
                expected_behavior="Image asset should load and decode successfully with natural dimensions > 0.",
                actual_behavior=f"Image failed to decode (naturalWidth={natural_w}, naturalHeight={natural_h}). src={src}",
                defect_category=CATEGORY_BROKEN_IMAGE,
                status="FAIL",
                error_message=f"Broken image asset failed to render: {src}",
                evidence_image_b64=evidence_b64,
                confidence=0.98,
                severity="Critical",
                bbox=bbox,
            )

        # 3. If source is an external HTTP URL and image failed to render, verify responsiveness
        if self.check_live_src and src.startswith(("http://", "https://")) and (natural_w == 0 or natural_h == 0):
            status_code, err_msg = check_url_status(src, timeout_sec=4.0)
            if status_code in (404, 410):
                return create_defect(
                    root_url=root_url,
                    crawled_url=page_url,
                    page_title=page_title,
                    element_type="Image",
                    element_identifier=alt or src,
                    element_selector=selector,
                    expected_behavior=f"Image asset source '{src}' should return HTTP 200 OK.",
                    actual_behavior=f"Image asset source returned HTTP {status_code} ({err_msg}).",
                    defect_category=CATEGORY_BROKEN_IMAGE,
                    status="FAIL",
                    http_status=status_code,
                    error_message=f"Image 404 Not Found: {src}",
                    evidence_image_b64=evidence_b64,
                    crop_localized_b64=evidence_b64,
                    confidence=0.96,
                    severity="Critical",
                    bbox=bbox,
                )

        return None

    def validate_all_images(
        self,
        root_url: str,
        page_url: str,
        page_title: str,
        elements: List[dict],
        evidence_b64_map: Optional[Dict[str, str]] = None,
    ) -> List[DefectRecord]:
        """
        Filters and validates all <img> and image-role elements from the page inventory.
        """
        defects: List[DefectRecord] = []
        evidence_b64_map = evidence_b64_map or {}

        for el in elements:
            if el.get("kind") == "image" or el.get("tag") == "img":
                selector = el.get("selector") or ""
                ev = evidence_b64_map.get(selector, "")
                defect = self.validate_image(
                    root_url=root_url,
                    page_url=page_url,
                    page_title=page_title,
                    img_element=el,
                    evidence_b64=ev,
                )
                if defect:
                    defects.append(defect)

        return defects
