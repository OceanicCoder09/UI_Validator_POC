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

            # 1. Invisible element defect (Check for active elements unexpectedly hidden via opacity 0 or clipping)
            if kind in interactive_kinds:
                is_named = bool(el.get("id") or el.get("name") or el.get("ariaLabel") or el.get("text"))
                is_hidden_input = (el.get("type") or "").lower() == "hidden"
                # Exclude standard collapsible/accordion/dropdown containers and non-named/hidden controls
                is_collapsible = any(k in selector.lower() for k in ("collapse", "dropdown", "modal", "drawer", "menu", "tree", "accordion"))
                if not is_hidden_input and is_named and not is_collapsible:
                    is_invisible = vis.get("display") == "none" or vis.get("visibility") in ("hidden", "collapse") or (vis.get("opacity") == "0" and bbox.get("width", 0) > 20)
                    if is_invisible:
                        defects.append(create_defect(
                            root_url=root_url,
                            crawled_url=page_url,
                            page_title=page_title,
                            element_type=kind.capitalize(),
                            element_identifier=label,
                            element_selector=selector,
                            expected_behavior=f"Interactive {kind} should be rendered and visible to the user.",
                            actual_behavior=f"Element is hidden in DOM (display={vis.get('display')}, visibility={vis.get('visibility')}, opacity={vis.get('opacity')}).",
                            defect_category=CATEGORY_INVISIBLE_ELEMENT,
                            status="FAIL",
                            error_message=f"Interactive {kind} is hidden from user view.",
                            evidence_image_b64=ev,
                            confidence=0.90,
                            severity="Major",
                            bbox=bbox if bbox.get("width", 0) > 0 else None,
                        ))

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

            # 3. Text truncation / scroll overflow (Exclude standard scrollbars or subpixel variations)
            overflow = el.get("overflow") or {}
            if kind in ("button", "label", "link", "dropdown"):
                is_ellipsis = overflow.get("textOverflow") == "ellipsis"
                x_overflow = overflow.get("x", 0)
                if is_ellipsis or x_overflow > 12:
                    defects.append(create_defect(
                        root_url=root_url,
                        crawled_url=page_url,
                        page_title=page_title,
                        element_type=kind.capitalize(),
                        element_identifier=label,
                        element_selector=selector,
                        expected_behavior=f"Element text content should fit comfortably inside container boundaries without truncation.",
                        actual_behavior=f"Content overflow / text truncation detected (overflowX={x_overflow}px, textOverflow={overflow.get('textOverflow')}).",
                        defect_category=CATEGORY_TEXT_TRUNCATION,
                        status="FAIL",
                        error_message=f"Text container overflow: {x_overflow}px horizontal overflow.",
                        evidence_image_b64=ev,
                        confidence=0.92,
                        severity="Major" if x_overflow > 25 else "Minor",
                        bbox=bbox,
                    ))

        # 4. Layout Collision / Overlap among distinct, non-nested visible interactive controls
        visible_interactive = [
            e for e in elements
            if e.get("kind") in interactive_kinds
            and (e.get("bbox") or {}).get("width", 0) > 15
            and (e.get("bbox") or {}).get("height", 0) > 15
            and (e.get("visibility") or {}).get("isVisible")
        ]

        for i, a in enumerate(visible_interactive):
            box_a = a["bbox"]
            sel_a = a.get("selector") or ""
            ax2, ay2 = box_a["x"] + box_a["width"], box_a["y"] + box_a["height"]
            for b in visible_interactive[i + 1:]:
                box_b = b["bbox"]
                sel_b = b.get("selector") or ""
                
                # Skip if one element is nested inside or shares root ancestor with the other
                if sel_a in sel_b or sel_b in sel_a:
                    continue

                bx2, by2 = box_b["x"] + box_b["width"], box_b["y"] + box_b["height"]
                
                # Check bounding box rectangle intersection
                ix = max(0, min(ax2, bx2) - max(box_a["x"], box_b["x"]))
                iy = max(0, min(ay2, by2) - max(box_a["y"], box_b["y"]))
                intersect_area = ix * iy
                
                # Only flag significant intersection between disjoint elements
                if intersect_area > 120:
                    label_a = ElementAnalyzer.get_element_label(a)
                    label_b = ElementAnalyzer.get_element_label(b)
                    defects.append(create_defect(
                        root_url=root_url,
                        crawled_url=page_url,
                        page_title=page_title,
                        element_type="Layout Collision",
                        element_identifier=f"{label_a} ∩ {label_b}",
                        element_selector=sel_a,
                        expected_behavior="Adjacent interactive UI components should not overlap each other.",
                        actual_behavior=f"Bounding box collision detected between '{label_a}' and '{label_b}' (intersection area={intersect_area}px²).",
                        defect_category=CATEGORY_LAYOUT_OVERLAP,
                        status="FAIL",
                        error_message=f"Interactive component collision: {label_a} overlaps {label_b}",
                        evidence_image_b64=evidence_b64_map.get(sel_a, ""),
                        confidence=0.88,
                        severity="Critical",
                        bbox=box_a,
                    ))
                    break

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
