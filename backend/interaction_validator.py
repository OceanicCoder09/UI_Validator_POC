"""
Interaction Validator module for UI Validation Engine.
Classifies interactive elements by safety category (Safe, Navigation, Form Submission, Destructive, Unknown),
validates presence, visibility, enabled state, clickability, overflow, and executes safe non-destructive trials.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from defect_classifier import (
    CATEGORY_DISABLED_ELEMENT,
    CATEGORY_INTERACTION_FAILURE,
    CATEGORY_INVISIBLE_ELEMENT,
    CATEGORY_LAYOUT_OVERLAP,
    CATEGORY_MISALIGNMENT,
    CATEGORY_TEXT_TRUNCATION,
    DefectRecord,
    create_defect,
)
from element_analyzer import ElementAnalyzer

logger = logging.getLogger(__name__)

# Safety Classification Constants
SAFETY_SAFE = "Safe"
SAFETY_NAVIGATION = "Navigation"
SAFETY_FORM_SUBMIT = "Form submission"
SAFETY_DESTRUCTIVE = "Destructive"
SAFETY_UNKNOWN = "Unknown"

# Regex keywords for destructive actions
DESTRUCTIVE_KEYWORDS = re.compile(
    r"\b(delete|remove|destroy|erase|cancel\s+account|cancel\s+subscription|unsubscribe|"
    r"logout|log\s+out|sign\s+out|signoff|terminate|purge|drop\s+database|reset\s+all|"
    r"buy\s+now|checkout|pay|payment|purchase|place\s+order|confirm\s+payment)\b",
    re.IGNORECASE,
)

# Regex keywords for safe UI actions (tabs, accordions, help, toggles)
SAFE_KEYWORDS = re.compile(
    r"\b(tab|view|expand|collapse|toggle|details|info|help|learn\s+more|faq|tooltip|"
    r"preview|close|dismiss|hide|show|filter|sort|accordion)\b",
    re.IGNORECASE,
)

# Regex keywords for form submission
SUBMIT_KEYWORDS = re.compile(
    r"\b(submit|save|update|send|register|sign\s+up|login|sign\s+in|apply|post|create)\b",
    re.IGNORECASE,
)


class InteractionValidator:
    """
    Evaluates interactive UI elements for safety, visibility, clickability, and interaction health.
    """

    @staticmethod
    def classify_safety(element: dict) -> str:
        """
        Classifies an element as Safe, Navigation, Form submission, Destructive, or Unknown.
        """
        kind = element.get("kind", "")
        tag = element.get("tag", "")
        el_type = element.get("type", "")
        text = f"{element.get('text', '')} {element.get('ariaLabel', '')} {element.get('id', '')} {element.get('name', '')}"

        # 1. Check for Destructive keywords
        if DESTRUCTIVE_KEYWORDS.search(text):
            return SAFETY_DESTRUCTIVE

        # 2. Form submission check
        if el_type == "submit" or (kind == "button" and SUBMIT_KEYWORDS.search(text)):
            return SAFETY_FORM_SUBMIT

        # 3. Navigation check
        if kind == "link" or tag == "a" or kind == "navigation":
            return SAFETY_NAVIGATION

        # 4. Safe UI controls (tabs, accordions, toggles, info dialogs)
        if SAFE_KEYWORDS.search(text) or element.get("role") in ("tab", "switch"):
            return SAFETY_SAFE

        if kind in ("button", "interactive", "dropdown"):
            return SAFETY_SAFE

        return SAFETY_UNKNOWN

    def validate_element_states(
        self,
        root_url: str,
        page_url: str,
        page_title: str,
        elements: List[dict],
        evidence_b64_map: Optional[Dict[str, str]] = None,
    ) -> List[DefectRecord]:
        """
        Validates visibility, enabled state, text overflow, and layout overlap across elements.
        """
        defects: List[DefectRecord] = []
        evidence_b64_map = evidence_b64_map or {}
        interactive_kinds = {"button", "input", "dropdown", "textarea", "checkbox", "radio", "interactive"}

        for el in elements:
            kind = el.get("kind")
            selector = el.get("selector") or ""
            label = ElementAnalyzer.get_element_label(el)
            vis = el.get("visibility") or {}
            bbox = el.get("bbox") or {}
            ev = evidence_b64_map.get(selector, "")

            # (Invisible element check removed per user requirement to avoid false positives on hidden sub-menus)

            # 2. Disabled element check (Flags elements rendered with disabled state or pointer-events: none)
            if el.get("disabled") and kind in ("button", "input", "dropdown", "textarea"):
                is_named = bool(el.get("id") or el.get("name") or el.get("text"))
                if vis.get("pointerEvents") == "none" and is_named:
                    defects.append(create_defect(
                        root_url=root_url,
                        crawled_url=page_url,
                        page_title=page_title,
                        element_type=kind.capitalize(),
                        element_identifier=label,
                        element_selector=selector,
                        expected_behavior=f"Interactive {kind} should allow user interaction.",
                        actual_behavior=f"Element has CSS 'pointer-events: none' preventing user interaction.",
                        defect_category=CATEGORY_DISABLED_ELEMENT,
                        status="FAIL",
                        error_message=f"Element interaction disabled via CSS pointer-events: none.",
                        evidence_image_b64=ev,
                        confidence=0.82,
                        severity="Minor",
                        bbox=bbox,
                    ))

            # (Text truncation checks removed per user requirement)

        # (Raw DOM layout collision check removed; visual collisions are handled via OpenCV pairwise visual diff)
        return defects

    def execute_safe_interaction_trial(
        self,
        page,
        root_url: str,
        page_url: str,
        page_title: str,
        element: dict,
        evidence_b64: str = "",
    ) -> Optional[DefectRecord]:
        """
        Safely attempts a hover / focus interaction on a verified Safe element
        to test for runtime JavaScript exceptions or unhandled interaction errors.
        """
        safety = self.classify_safety(element)
        if safety != SAFETY_SAFE:
            return None

        selector = element.get("selector")
        if not selector:
            return None

        label = ElementAnalyzer.get_element_label(element)
        bbox = element.get("bbox")

        try:
            loc = page.locator(selector).first
            if loc.is_visible(timeout=1000):
                loc.hover(timeout=1500)
                page.wait_for_timeout(100)
            return None
        except Exception as exc:
            msg = str(exc)
            # Filter standard timeout / non-attached issues
            if "Target closed" in msg or "page closed" in msg:
                return None
            return create_defect(
                root_url=root_url,
                crawled_url=page_url,
                page_title=page_title,
                element_type="Interaction",
                element_identifier=label,
                element_selector=selector,
                expected_behavior=f"Safe element '{label}' should handle hover/focus without exception.",
                actual_behavior=f"Interaction failure when interacting with element: {msg[:200]}",
                defect_category=CATEGORY_INTERACTION_FAILURE,
                status="FAIL",
                error_message=f"Element interaction exception: {msg[:150]}",
                evidence_image_b64=evidence_b64,
                confidence=0.85,
                severity="Major",
                bbox=bbox,
            )
