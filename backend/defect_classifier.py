"""
Defect Classifier module for UI Validation Engine.
Categorizes discovered element defects and runtime issues into standard categories,
mapping them to Autodesk LQA taxonomy codes where applicable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Standard Defect Categories
CATEGORY_BROKEN_LINK = "Broken Link"
CATEGORY_BROKEN_IMAGE = "Broken Image"
CATEGORY_MISSING_ELEMENT = "Missing Element"
CATEGORY_INVISIBLE_ELEMENT = "Invisible Element"
CATEGORY_DISABLED_ELEMENT = "Disabled Element"
CATEGORY_NAVIGATION_FAILURE = "Navigation Failure"
CATEGORY_HTTP_ERROR = "HTTP Error"
CATEGORY_INTERACTION_FAILURE = "Interaction Failure"
CATEGORY_JAVASCRIPT_ERROR = "JavaScript Error"
CATEGORY_LAYOUT_OVERLAP = "Layout Overlap"
CATEGORY_TEXT_TRUNCATION = "Text Truncation"
CATEGORY_MISALIGNMENT = "Misalignment"
CATEGORY_OTHER = "Other"

ALL_DEFECT_CATEGORIES = [
    CATEGORY_BROKEN_LINK,
    CATEGORY_BROKEN_IMAGE,
    CATEGORY_MISSING_ELEMENT,
    CATEGORY_INVISIBLE_ELEMENT,
    CATEGORY_DISABLED_ELEMENT,
    CATEGORY_NAVIGATION_FAILURE,
    CATEGORY_HTTP_ERROR,
    CATEGORY_INTERACTION_FAILURE,
    CATEGORY_JAVASCRIPT_ERROR,
    CATEGORY_LAYOUT_OVERLAP,
    CATEGORY_TEXT_TRUNCATION,
    CATEGORY_MISALIGNMENT,
    CATEGORY_OTHER,
]

# Autodesk LQA Defect Code Mappings
AUTODESK_CODE_MAP = {
    CATEGORY_LAYOUT_OVERLAP: "0001",       # OVERLAPPING
    CATEGORY_MISALIGNMENT: "0004",         # MISSALIGNMENT
    CATEGORY_MISSING_ELEMENT: "0006",      # MISC
    CATEGORY_TEXT_TRUNCATION: "0009",      # TRUNCATION
    CATEGORY_NAVIGATION_FAILURE: "0014",   # CAPTURE_BITMAP_FAILED
    CATEGORY_HTTP_ERROR: "0014",           # CAPTURE_BITMAP_FAILED
    CATEGORY_BROKEN_LINK: "0006",          # MISC
    CATEGORY_BROKEN_IMAGE: "0006",         # MISC
    CATEGORY_INVISIBLE_ELEMENT: "0006",    # MISC
    CATEGORY_DISABLED_ELEMENT: "0006",     # MISC
    CATEGORY_JAVASCRIPT_ERROR: "0020",     # UNKNOWN_ERROR
    CATEGORY_INTERACTION_FAILURE: "0020",  # UNKNOWN_ERROR
    CATEGORY_OTHER: "0020",                # UNKNOWN_ERROR
}


@dataclass
class DefectRecord:
    """
    Standardized defect/issue record across the crawling & validation engine.
    """
    root_url: str
    crawled_url: str
    page_title: str
    element_type: str
    element_identifier: str
    element_selector: str
    expected_behavior: str
    actual_behavior: str
    status: str  # "PASS" | "FAIL"
    defect_category: str
    http_status: Optional[int] = None
    error_message: str = ""
    screenshot_path: str = ""
    evidence_image_b64: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    confidence: float = 1.0
    severity: str = "Major"  # "Critical" | "Major" | "Minor" | "Info"
    bbox: Optional[Dict[str, int]] = None
    lqa_code: str = "0020"

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the record for API responses and JSON reports."""
        return {
            "root_url": self.root_url,
            "crawled_url": self.crawled_url,
            "page_title": self.page_title,
            "element_type": self.element_type,
            "element_identifier": self.element_identifier,
            "element_selector": self.element_selector,
            "expected_behavior": self.expected_behavior,
            "actual_behavior": self.actual_behavior,
            "status": self.status,
            "defect_category": self.defect_category,
            "http_status": self.http_status,
            "error_message": self.error_message,
            "screenshot_path": self.screenshot_path,
            "evidence_image": self.evidence_image_b64,
            "timestamp": self.timestamp,
            "confidence": round(self.confidence, 2),
            "severity": self.severity,
            "lqa_code": self.lqa_code,
            "_bbox": self.bbox,
        }

    def to_legacy_format(self) -> Dict[str, Any]:
        """Provides backwards compatibility with existing UI components expecting Page/Element/Issue keys."""
        return {
            "Page": self.crawled_url,
            "Element": f"{self.element_type}: {self.element_identifier}" if self.element_identifier else self.element_type,
            "Issue": self.defect_category,
            "Confidence": round(self.confidence, 2),
            "Status": self.status,
            "Details": self.actual_behavior or self.error_message,
            "EvidenceImage": self.screenshot_path or self.evidence_image_b64,
            "Selector": self.element_selector,
            "Expected": self.expected_behavior,
            "Actual": self.actual_behavior,
            "Category": self.defect_category,
            "Severity": self.severity,
            "HttpStatus": self.http_status,
            "Timestamp": self.timestamp,
            "_bbox": self.bbox,
        }


def create_defect(
    root_url: str,
    crawled_url: str,
    page_title: str,
    element_type: str,
    element_identifier: str,
    element_selector: str,
    expected_behavior: str,
    actual_behavior: str,
    defect_category: str,
    status: str = "FAIL",
    http_status: Optional[int] = None,
    error_message: str = "",
    screenshot_path: str = "",
    evidence_image_b64: str = "",
    confidence: float = 0.9,
    severity: str = "Major",
    bbox: Optional[Dict[str, int]] = None,
) -> DefectRecord:
    """Factory helper to instantiate a standardized DefectRecord."""
    lqa = AUTODESK_CODE_MAP.get(defect_category, "0020")
    return DefectRecord(
        root_url=root_url,
        crawled_url=crawled_url,
        page_title=page_title,
        element_type=element_type,
        element_identifier=element_identifier,
        element_selector=element_selector,
        expected_behavior=expected_behavior,
        actual_behavior=actual_behavior,
        status=status,
        defect_category=defect_category,
        http_status=http_status,
        error_message=error_message,
        screenshot_path=screenshot_path,
        evidence_image_b64=evidence_image_b64,
        confidence=confidence,
        severity=severity,
        bbox=bbox,
        lqa_code=lqa,
    )
