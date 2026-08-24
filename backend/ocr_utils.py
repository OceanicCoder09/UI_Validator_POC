"""Optional OCR helpers. Tesseract is used when installed; otherwise visual/DOM fallbacks apply."""

from __future__ import annotations

import re
from typing import Optional

HTML_ENTITY_RE = re.compile(r"&(?:amp|lt|gt|quot|nbsp|apos|#\d+|#x[0-9a-fA-F]+);")
REPLACEMENT_CHARS = ("\ufffd", "\u25a1", "\u25a2")


def ocr_available() -> bool:
    try:
        import pytesseract  # noqa: F401
        return True
    except Exception:
        return False


def ocr_text_from_bgr(img_bgr) -> Optional[str]:
    if img_bgr is None:
        return None
    try:
        import pytesseract
        import cv2
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        return pytesseract.image_to_string(rgb) or ""
    except Exception:
        return None


def find_symbol_issues_in_text(text: str) -> list:
    issues = []
    if not text:
        return issues
    if any(ch in text for ch in REPLACEMENT_CHARS):
        issues.append("Replacement / tofu glyph in rendered text")
    if HTML_ENTITY_RE.search(text):
        issues.append("Unescaped HTML entity visible in UI text")
    if "{{" in text or "{%" in text or "${" in text:
        issues.append("Unresolved template token in rendered text")
    return issues
