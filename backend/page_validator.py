"""DOM + visual validators that emit framework issue records."""

from __future__ import annotations

from typing import Dict, List, Optional

import cv2
import numpy as np

from cv_engine import (
    analyze_localization_quality,
    crop_region_base64,
    detect_corrupted_glyph,
    detect_ellipsis_precise,
    detect_ui_containers,
    extract_text_lines,
    image_to_base64,
)
from element_extractor import element_label
from ocr_utils import find_symbol_issues_in_text, ocr_text_from_bgr


ISSUE_KEYS = ("Page", "Element", "Issue", "Confidence", "Status", "Details", "EvidenceImage")


def make_issue(
    page: str,
    element: str,
    issue: str,
    confidence: float,
    status: str,
    details: str,
    evidence: str = "",
) -> dict:
    return {
        "Page": page,
        "Element": element,
        "Issue": issue,
        "Confidence": round(float(confidence), 2),
        "Status": status,
        "Details": details,
        "EvidenceImage": evidence or "",
    }


def _rects_overlap(a: dict, b: dict, min_area: int = 8) -> bool:
    ax2, ay2 = a["x"] + a["width"], a["y"] + a["height"]
    bx2, by2 = b["x"] + b["width"], b["y"] + b["height"]
    ix = max(0, min(ax2, bx2) - max(a["x"], b["x"]))
    iy = max(0, min(ay2, by2) - max(a["y"], b["y"]))
    return ix * iy >= min_area


def _crop_evidence(img_bgr, bbox: Optional[dict], pad: int = 8) -> str:
    if img_bgr is None or not bbox:
        return image_to_base64(img_bgr) if img_bgr is not None else ""
    box = (int(bbox["x"]), int(bbox["y"]), int(bbox["width"]), int(bbox["height"]))
    return crop_region_base64(img_bgr, box, padding=pad)


def decode_png(png_bytes: bytes):
    if not png_bytes:
        return None
    arr = np.frombuffer(png_bytes, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def annotate_issues(img_bgr, issues: List[dict]) -> np.ndarray:
    if img_bgr is None:
        return img_bgr
    out = img_bgr.copy()
    fail = [i for i in issues if i.get("Status") == "FAIL"]
    for item in fail:
        loc = item.get("_bbox") or {}
        if not loc or loc.get("width", 0) <= 0:
            continue
        x, y, w, h = int(loc["x"]), int(loc["y"]), int(loc["width"]), int(loc["height"])
        color = (45, 38, 220)
        overlay = out.copy()
        cv2.rectangle(overlay, (x, y), (x + w, y + h), color, -1)
        cv2.addWeighted(overlay, 0.18, out, 0.82, 0, out)
        cv2.rectangle(out, (x, y), (x + w, y + h), color, 2)
        label = f" {item.get('Issue', 'ISSUE')[:40]} "
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        y1 = max(0, y - 18)
        cv2.rectangle(out, (x, y1), (x + tw + 4, y1 + 16), color, -1)
        cv2.putText(out, label, (x + 2, y1 + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def _attach_bbox(issue: dict, bbox: Optional[dict]) -> dict:
    if bbox:
        issue["_bbox"] = bbox
    return issue


def validate_dom(page_url: str, elements: list, img_bgr) -> List[dict]:
    issues: List[dict] = []
    interactive = {"button", "textbox", "dropdown", "checkbox", "radio", "link"}

    for el in elements:
        kind = el.get("kind")
        vis = el.get("visibility") or {}
        bbox = el.get("bbox") or {}
        label = element_label(el)

        if kind == "image" and el.get("imageBroken"):
            issues.append(_attach_bbox(make_issue(
                page_url, label, "Broken image", 0.99, "FAIL",
                f"Image failed to load (naturalWidth={el.get('naturalWidth', 0)}). src={el.get('src') or '(empty)'}",
                _crop_evidence(img_bgr, bbox),
            ), bbox))

        if kind in interactive:
            input_type = (el.get("type") or "").lower()
            if input_type == "hidden":
                continue
            hidden = (
                vis.get("display") == "none"
                or vis.get("visibility") == "hidden"
                or vis.get("hiddenAttr")
            )
            # Skip collapsed chrome (menus, unused nav copies) unless the control is named.
            named = bool(el.get("id") or el.get("name") or el.get("ariaLabel"))
            if hidden and named and kind in {"button", "textbox", "dropdown", "checkbox", "radio"}:
                issues.append(_attach_bbox(make_issue(
                    page_url, label, "Hidden element", 0.86, "FAIL",
                    f"Named interactive {kind} is hidden (display={vis.get('display')}, visibility={vis.get('visibility')}).",
                    _crop_evidence(img_bgr, bbox) if bbox.get("width", 0) > 0 else (image_to_base64(img_bgr) if img_bgr is not None else ""),
                ), bbox if bbox.get("width", 0) > 0 else None))

        overflow = el.get("overflow") or {}
        if kind in {"button", "textbox", "label", "link", "dropdown"}:
            if overflow.get("x", 0) > 2 or overflow.get("y", 0) > 2:
                ellipsis = overflow.get("textOverflow") == "ellipsis"
                issue_name = "Text truncation" if ellipsis else "Text overflow"
                issues.append(_attach_bbox(make_issue(
                    page_url, label, issue_name, 0.95, "FAIL",
                    f"scroll overflow dx={overflow.get('x')} dy={overflow.get('y')} textOverflow={overflow.get('textOverflow')}.",
                    _crop_evidence(img_bgr, bbox),
                ), bbox))

        for msg in find_symbol_issues_in_text(el.get("text") or ""):
            issues.append(_attach_bbox(make_issue(
                page_url, label, "Symbol/punctuation issue", 0.88, "FAIL",
                msg + f" Text snippet: {(el.get('text') or '')[:120]}",
                _crop_evidence(img_bgr, bbox),
            ), bbox))

        if kind == "label" and el.get("required"):
            text = el.get("text") or ""
            if "*" not in text and "required" not in text.lower():
                issues.append(_attach_bbox(make_issue(
                    page_url, label, "Symbol/punctuation issue", 0.7, "FAIL",
                    "Required field label is missing a mandatory marker (*).",
                    _crop_evidence(img_bgr, bbox),
                ), bbox))

    # Overlap among visible interactive controls
    visible_ix = [
        el for el in elements
        if el.get("kind") in interactive
        and (el.get("bbox") or {}).get("width", 0) > 4
        and (el.get("bbox") or {}).get("height", 0) > 4
        and (el.get("visibility") or {}).get("display") != "none"
    ]
    for i, a in enumerate(visible_ix):
        for b in visible_ix[i + 1:]:
            if _rects_overlap(a["bbox"], b["bbox"], min_area=24):
                issues.append(_attach_bbox(make_issue(
                    page_url, f"{element_label(a)} ∩ {element_label(b)}", "Overlap", 0.86, "FAIL",
                    f"Bounding boxes intersect: {a['bbox']} vs {b['bbox']}.",
                    _crop_evidence(img_bgr, a["bbox"]),
                ), a["bbox"]))
                break

    # Misalignment: same-row interactive elements with large y delta
    rows: Dict[int, list] = {}
    for el in visible_ix:
        row = int(round(el["bbox"]["y"] / 12) * 12)
        rows.setdefault(row, []).append(el)
    for group in rows.values():
        if len(group) < 2:
            continue
        ys = [g["bbox"]["y"] for g in group]
        if max(ys) - min(ys) >= 12:
            first = group[0]
            issues.append(_attach_bbox(make_issue(
                page_url, ", ".join(element_label(g) for g in group[:4]), "Misalignment", 0.78, "FAIL",
                f"Controls on the same row differ by {max(ys) - min(ys)}px vertically.",
                _crop_evidence(img_bgr, first["bbox"]),
            ), first["bbox"]))

    # Incorrect / duplicate hotkeys
    keys: Dict[str, list] = {}
    for el in elements:
        key = (el.get("accessKey") or "").strip().lower()
        if key:
            keys.setdefault(key, []).append(el)
        text = el.get("text") or ""
        if "&" in text and len(text) < 80 and not key and el.get("kind") in interactive:
            issues.append(_attach_bbox(make_issue(
                page_url, element_label(el), "Incorrect hotkey", 0.72, "FAIL",
                f"Mnemonic '&' present in label '{text}' but no accesskey is bound.",
                _crop_evidence(img_bgr, el.get("bbox")),
            ), el.get("bbox")))
    for key, group in keys.items():
        if len(group) > 1:
            issues.append(make_issue(
                page_url,
                ", ".join(element_label(g) for g in group),
                "Incorrect hotkey",
                0.9,
                "FAIL",
                f"Duplicate accesskey '{key}' bound to {len(group)} controls.",
                _crop_evidence(img_bgr, group[0].get("bbox")),
            ))

    return issues


def validate_visual_single(page_url: str, img_bgr) -> List[dict]:
    if img_bgr is None:
        return []
    issues: List[dict] = []
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    for bx, by, bw, bh in extract_text_lines(gray):
        crop = gray[max(0, by - 2): min(h, by + bh + 2), max(0, bx - 2): min(w, bx + bw + 2)]
        bbox = {"x": int(bx), "y": int(by), "width": int(bw), "height": int(bh)}
        if detect_ellipsis_precise(crop):
            issues.append(_attach_bbox(make_issue(
                page_url, f"TEXT @ ({bx},{by})", "Text truncation", 0.8, "FAIL",
                "OpenCV detected trailing ellipsis ('...') on a text line.",
                crop_region_base64(img_bgr, (bx, by, bw, bh)),
            ), bbox))
        if detect_corrupted_glyph(crop):
            issues.append(_attach_bbox(make_issue(
                page_url, f"TEXT @ ({bx},{by})", "Symbol/punctuation issue", 0.82, "FAIL",
                "OpenCV detected a replacement/corrupted glyph contour.",
                crop_region_base64(img_bgr, (bx, by, bw, bh)),
            ), bbox))

    ocr = ocr_text_from_bgr(img_bgr)
    if ocr:
        for msg in find_symbol_issues_in_text(ocr):
            issues.append(make_issue(
                page_url, "OCR:page", "Symbol/punctuation issue", 0.65, "FAIL",
                f"OCR: {msg}",
                image_to_base64(img_bgr),
            ))

    containers = detect_ui_containers(img_bgr)
    boxes = containers.get("all_containers") or []
    for i, a in enumerate(boxes):
        ax, ay, aw, ah = a
        for b in boxes[i + 1:]:
            bx, by, bw, bh = b
            if _rects_overlap(
                {"x": ax, "y": ay, "width": aw, "height": ah},
                {"x": bx, "y": by, "width": bw, "height": bh},
                min_area=80,
            ):
                # Ignore near-identical duplicate contours
                if abs(ax - bx) < 8 and abs(ay - by) < 8:
                    continue
                bbox = {"x": ax, "y": ay, "width": aw, "height": ah}
                issues.append(_attach_bbox(make_issue(
                    page_url, f"CONTAINER @ ({ax},{ay})", "Layout issue", 0.7, "FAIL",
                    "OpenCV container boxes overlap.",
                    crop_region_base64(img_bgr, a),
                ), bbox))
                break
    return issues


def cv_findings_to_issues(page_url: str, cv_result: dict) -> List[dict]:
    issues = []
    conf_map = {"Critical": 0.92, "Major": 0.8, "Minor": 0.65}
    for f in cv_result.get("findings") or []:
        loc = f.get("location") or {}
        bbox = {"x": loc.get("x", 0), "y": loc.get("y", 0), "width": loc.get("width", 0), "height": loc.get("height", 0)}
        evidence = f.get("crop_localized_b64") or (cv_result.get("images") or {}).get("annotated_diff_image") or ""
        issue = _attach_bbox(make_issue(
            page_url,
            f.get("category") or "UI",
            f.get("title") or f.get("category") or "Visual defect",
            conf_map.get(f.get("severity"), 0.75),
            "FAIL",
            f.get("description") or f.get("actual") or "",
            evidence,
        ), bbox)
        issues.append(issue)
    return issues


def inventory_diff(page_url: str, baseline_els: list, target_els: list, img_bgr) -> List[dict]:
    base_kinds = {}
    tgt_kinds = {}
    for el in baseline_els:
        base_kinds[el.get("kind")] = base_kinds.get(el.get("kind"), 0) + 1
    for el in target_els:
        tgt_kinds[el.get("kind")] = tgt_kinds.get(el.get("kind"), 0) + 1

    issues = []
    kinds = set(list(base_kinds) + list(tgt_kinds))
    for kind in kinds:
        b, t = base_kinds.get(kind, 0), tgt_kinds.get(kind, 0)
        if t < b:
            issues.append(make_issue(
                page_url, kind.upper() if kind else "CONTROL", "Missing element", 0.84, "FAIL",
                f"Baseline has {b} {kind}(s); crawled page has {t}.",
                image_to_base64(img_bgr) if img_bgr is not None else "",
            ))
        elif t > b + 2:
            issues.append(make_issue(
                page_url, kind.upper() if kind else "CONTROL", "Missing/extra controls", 0.7, "FAIL",
                f"Crawled page has extra {kind}s ({t} vs baseline {b}).",
                image_to_base64(img_bgr) if img_bgr is not None else "",
            ))

    base_ids = {(el.get("id") or "").strip() for el in baseline_els if el.get("id")}
    tgt_ids = {(el.get("id") or "").strip() for el in target_els if el.get("id")}
    for missing in sorted(base_ids - tgt_ids):
        issues.append(make_issue(
            page_url, f"#{missing}", "Missing element", 0.9, "FAIL",
            f"Element id '{missing}' present in baseline DOM is absent on this page.",
            image_to_base64(img_bgr) if img_bgr is not None else "",
        ))
    return issues


def counts_by_kind(elements: list) -> dict:
    out = {
        "button": 0, "textbox": 0, "dropdown": 0, "label": 0, "checkbox": 0,
        "radio": 0, "link": 0, "icon": 0, "image": 0, "table": 0,
    }
    for el in elements:
        k = el.get("kind")
        if k in out:
            out[k] += 1
    out["total"] = len(elements)
    return out
