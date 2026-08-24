"""
Screenshot Manager module for UI Validation Engine.
Handles image encoding/decoding, bounding box annotations with defect badges,
element visual crops, and persistence of evidence screenshots to disk.
"""

from __future__ import annotations

import base64
import io
import logging
import os
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Distinct color palette for defect categories (BGR format for OpenCV)
CATEGORY_COLOR_PALETTE: Dict[str, Tuple[int, int, int]] = {
    "Broken Link": (45, 38, 220),         # Vibrant Red
    "Broken Image": (30, 100, 230),       # Orange-Red
    "Missing Element": (180, 40, 200),    # Magenta
    "Invisible Element": (130, 60, 200),  # Purple
    "Disabled Element": (160, 160, 160),  # Gray
    "Navigation Failure": (20, 20, 210),  # Dark Red
    "HTTP Error": (0, 0, 220),            # Pure Red
    "Interaction Failure": (30, 150, 230),# Amber
    "JavaScript Error": (0, 70, 220),     # Crimson
    "Layout Overlap": (210, 80, 30),      # Blue-Cyan
    "Text Truncation": (40, 170, 220),    # Orange
    "Misalignment": (180, 130, 20),       # Cyan-Teal
    "Other": (100, 100, 100),             # Slate
}


class ScreenshotManager:
    """
    Manages capturing, annotating, cropping, and persisting evidence images.
    """

    @staticmethod
    def bytes_to_bgr(png_bytes: bytes) -> Optional[np.ndarray]:
        """Converts raw PNG/JPEG bytes into an OpenCV BGR numpy array."""
        if not png_bytes:
            return None
        arr = np.frombuffer(png_bytes, np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    @staticmethod
    def bgr_to_bytes(img_bgr: np.ndarray, ext: str = ".png") -> bytes:
        """Encodes an OpenCV BGR numpy array to image bytes."""
        if img_bgr is None or img_bgr.size == 0:
            return b""
        ok, buf = cv2.imencode(ext, img_bgr)
        return buf.tobytes() if ok else b""

    @staticmethod
    def image_to_base64(img: np.ndarray) -> str:
        """Converts an OpenCV BGR image to a data:image/png;base64 string."""
        if img is None or img.size == 0:
            return ""
        ok, buf = cv2.imencode(".png", img)
        if not ok:
            return ""
        b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
        return f"data:image/png;base64,{b64}"

    @staticmethod
    def crop_element_b64(img_bgr: np.ndarray, bbox: Optional[dict], padding: int = 12) -> str:
        """Crops a region from the image with padding and returns a base64 string."""
        if img_bgr is None or not bbox:
            return ""
        bx = int(bbox.get("x", 0))
        by = int(bbox.get("y", 0))
        bw = int(bbox.get("width", 0))
        bh = int(bbox.get("height", 0))

        if bw <= 0 or bh <= 0:
            return ""

        h, w = img_bgr.shape[:2]
        x1 = max(0, bx - padding)
        y1 = max(0, by - padding)
        x2 = min(w, bx + bw + padding)
        y2 = min(h, by + bh + padding)

        if x2 <= x1 or y2 <= y1:
            return ""

        crop = img_bgr[y1:y2, x1:x2]
        return ScreenshotManager.image_to_base64(crop)

    @staticmethod
    def annotate_defects(img_bgr: np.ndarray, defects: List[dict]) -> np.ndarray:
        """
        Draws colored bounding boxes and informative defect badges onto a copy of the image.
        """
        if img_bgr is None or img_bgr.size == 0:
            return img_bgr

        annotated = img_bgr.copy()
        h, w = annotated.shape[:2]

        for defect in defects:
            if defect.get("status") != "FAIL" and defect.get("Status") != "FAIL":
                continue

            loc = defect.get("_bbox") or defect.get("bbox")
            if not loc:
                continue

            bx = int(loc.get("x", 0))
            by = int(loc.get("y", 0))
            bw = int(loc.get("width", 0))
            bh = int(loc.get("height", 0))

            if bw <= 0 or bh <= 0:
                continue

            category = defect.get("defect_category") or defect.get("Issue") or "Defect"
            color = CATEGORY_COLOR_PALETTE.get(category, (45, 38, 220))

            # Draw soft highlighted rectangle overlay
            overlay = annotated.copy()
            cv2.rectangle(overlay, (bx, by), (bx + bw, by + bh), color, -1)
            cv2.addWeighted(overlay, 0.18, annotated, 0.82, 0, annotated)

            # Draw outer border line
            cv2.rectangle(annotated, (bx, by), (bx + bw, by + bh), color, 2)

            # Draw defect badge header
            badge_text = f" {category[:35]} "
            (tw, th), _ = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
            y_badge = max(0, by - 20)
            cv2.rectangle(annotated, (bx, y_badge), (bx + tw + 6, y_badge + 18), color, -1)
            cv2.putText(
                annotated,
                badge_text,
                (bx + 3, y_badge + 13),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        return annotated

    @staticmethod
    def save_evidence_file(run_dir: str, filename: str, img_bytes: bytes) -> str:
        """
        Saves image bytes into run_dir/evidence/filename and returns relative path.
        """
        evidence_dir = os.path.join(run_dir, "evidence")
        os.makedirs(evidence_dir, exist_ok=True)
        file_path = os.path.join(evidence_dir, filename)
        with open(file_path, "wb") as f:
            f.write(img_bytes)
        return os.path.join("evidence", filename).replace("\\", "/")
