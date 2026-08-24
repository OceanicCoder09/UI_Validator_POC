"""
Framework Orchestrator module for Web UI Quality Validation Engine.
Coordinates:
  1. PlaywrightCrawler (BFS page crawl & screenshot capture)
  2. PageAnalyzer (HTTP status & JS runtime exceptions)
  3. LinkValidator (Broken links & invalid href detection)
  4. ImageValidator (Broken images & load verification)
  5. InteractionValidator (Safety classification & layout collision/overflow checks)
  6. CV Engine (Optional baseline pairwise comparison)
  7. ScreenshotManager (Annotations, crops, and evidence saving)
  8. ReportGenerator (JSON, CSV, and formatted Excel audit reports)
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
import cv2

from config_manager import CrawlConfig
from crawler import CrawledPage, PlaywrightCrawler
from cv_engine import analyze_localization_quality, image_to_base64
from defect_classifier import (
    ALL_DEFECT_CATEGORIES,
    DefectRecord,
    create_defect,
)
from element_analyzer import ElementAnalyzer
from image_validator import ImageValidator
from interaction_validator import InteractionValidator
from link_validator import LinkValidator
from page_analyzer import PageAnalyzer
from report_generator import ReportGenerator
from screenshot_manager import ScreenshotManager

logger = logging.getLogger(__name__)


def run_framework(
    root_url: str,
    baseline_root_url: Optional[str] = None,
    max_depth: int = 2,
    max_pages: int = 10,
    same_origin_only: bool = True,
    viewport_width: int = 1280,
    viewport_height: int = 800,
    wait_seconds: float = 1.0,
    timeout_ms: int = 25000,
    check_links: bool = True,
    check_images: bool = True,
    check_interactions: bool = True,
    safe_interactions_only: bool = True,
) -> Dict[str, Any]:
    """
    Executes end-to-end web crawling, DOM validation, defect detection, and report generation.
    """
    config = CrawlConfig(
        root_url=root_url,
        baseline_root_url=baseline_root_url,
        max_depth=max_depth,
        max_pages=max_pages,
        same_origin_only=same_origin_only,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        wait_seconds=wait_seconds,
        timeout_ms=timeout_ms,
        check_links=check_links,
        check_images=check_images,
        check_interactions=check_interactions,
        safe_interactions_only=safe_interactions_only,
    )

    run_id = uuid.uuid4().hex[:12]
    run_dir = ReportGenerator.ensure_run_dir(run_id)

    # 1. Execute Web Crawl
    crawler = PlaywrightCrawler(config)
    target_pages = crawler.crawl()

    # Optional: Baseline crawl for pairwise localization comparison if requested
    baseline_pages: List[CrawledPage] = []
    if config.baseline_root_url:
        baseline_config = CrawlConfig(
            root_url=config.baseline_root_url,
            max_depth=config.max_depth,
            max_pages=config.max_pages,
            same_origin_only=config.same_origin_only,
            viewport_width=config.viewport_width,
            viewport_height=config.viewport_height,
            wait_seconds=config.wait_seconds,
        )
        baseline_crawler = PlaywrightCrawler(baseline_config)
        baseline_pages = baseline_crawler.crawl()

    # 2. Initialize Validators
    link_validator = LinkValidator(check_live_status=config.check_links)
    image_validator = ImageValidator(check_live_src=config.check_images)
    interaction_validator = InteractionValidator()
    page_analyzer = PageAnalyzer()

    all_defects: List[DefectRecord] = []
    page_summaries: List[Dict[str, Any]] = []

    total_elements_checked = 0
    total_links_checked = 0
    total_images_checked = 0
    total_interactions_checked = 0

    import re
    from urllib.parse import urlparse

    def find_matching_baseline_page(target_url: str, bp_list: List[CrawledPage], cur_idx: int) -> Optional[CrawledPage]:
        if not bp_list:
            return None
        target_path = urlparse(target_url).path.strip("/")
        target_slug = re.sub(r'^(en|enu|de|deu|es|esp|fr|fra|ja|jpn|zh|chs|it|ita|pt|ptb|ko|kor)/?', '', target_path, flags=re.IGNORECASE).strip("/")
        for bp in bp_list:
            bp_path = urlparse(bp.url).path.strip("/")
            bp_slug = re.sub(r'^(en|enu|de|deu|es|esp|fr|fra|ja|jpn|zh|chs|it|ita|pt|ptb|ko|kor)/?', '', bp_path, flags=re.IGNORECASE).strip("/")
            if target_slug and target_slug.lower() == bp_slug.lower():
                return bp
        if cur_idx < len(bp_list):
            return bp_list[cur_idx]
        return bp_list[0]

    # 3. Analyze each crawled page
    for idx, page in enumerate(target_pages):
        img_bgr = ScreenshotManager.bytes_to_bgr(page.screenshot_png)
        page_defects: List[DefectRecord] = []

        # Find matching baseline page if baseline crawl was requested
        matched_baseline = find_matching_baseline_page(page.url, baseline_pages, idx) if baseline_pages else None
        img_en_bgr = ScreenshotManager.bytes_to_bgr(matched_baseline.screenshot_png) if matched_baseline and matched_baseline.screenshot_png else None
        
        cv_result: Optional[Dict[str, Any]] = None
        if img_en_bgr is not None and img_bgr is not None:
            try:
                cv_result = analyze_localization_quality(img_en_bgr, img_bgr)
            except Exception as cv_err:
                logger.warning(f"Pairwise CV analysis failed for {page.url}: {cv_err}")

        # Count element stats
        elements = page.elements
        total_elements_checked += len(elements)
        links_on_page = [e for e in elements if e.get("kind") == "link" or e.get("tag") == "a"]
        images_on_page = [e for e in elements if e.get("kind") == "image" or e.get("tag") == "img"]
        interactive_on_page = [
            e for e in elements
            if e.get("kind") in ("button", "input", "dropdown", "textarea", "checkbox", "radio", "interactive")
        ]

        total_links_checked += len(links_on_page)
        total_images_checked += len(images_on_page)
        total_interactions_checked += len(interactive_on_page)

        # Evidence crop map for elements
        evidence_crops: Dict[str, str] = {}
        if img_bgr is not None:
            for el in elements:
                sel = el.get("selector")
                bbox = el.get("bbox")
                if sel and bbox and bbox.get("width", 0) > 0 and bbox.get("height", 0) > 0:
                    evidence_crops[sel] = ScreenshotManager.crop_element_b64(img_bgr, bbox)

        # 3.1 Pairwise Computer Vision Visual Localization Defects
        if cv_result and cv_result.get("findings"):
            for f in cv_result["findings"]:
                loc = f.get("location") or {}
                page_defects.append(create_defect(
                    root_url=config.root_url,
                    crawled_url=page.url,
                    page_title=page.title or "(Localized Target)",
                    element_type=f.get("category", "Visual Layout"),
                    element_identifier=f.get("title", f.get("id", "Visual Issue")),
                    element_selector=f.get("id", "layout-node"),
                    expected_behavior=f.get("expected", "Matches baseline English layout and typography."),
                    actual_behavior=f.get("actual", f.get("description", "Visual regression detected.")),
                    defect_category=f.get("category", "Other"),
                    status="FAIL",
                    http_status=page.status,
                    error_message=f.get("description", ""),
                    evidence_image_b64=f.get("crop_localized_b64") or f.get("crop_baseline_b64") or "",
                    confidence=0.95,
                    severity=f.get("severity", "Major"),
                    bbox=loc if loc.get("width", 0) > 0 else None,
                    crop_baseline_b64=f.get("crop_baseline_b64", ""),
                    crop_localized_b64=f.get("crop_localized_b64", ""),
                    remediation=f.get("remediation", ""),
                    lqa_code=f.get("code", "0020"),
                ))

        # 3.2 Page-Level Health Checks
        page_defects.extend(page_analyzer.evaluate_page_health(
            root_url=config.root_url,
            page_url=page.url,
            page_title=page.title,
            http_status=page.status,
            navigation_error=page.navigation_error,
            evidence_b64=ScreenshotManager.image_to_base64(img_bgr) if img_bgr is not None else "",
        ))

        # If page navigated successfully, run DOM & Element checks
        if not page.navigation_error:
            # 3.3 Link Validation
            if config.check_links:
                page_defects.extend(link_validator.validate_all_links(
                    root_url=config.root_url,
                    page_url=page.url,
                    page_title=page.title,
                    elements=elements,
                    evidence_b64_map=evidence_crops,
                ))

            # 3.4 Image Validation
            if config.check_images:
                page_defects.extend(image_validator.validate_all_images(
                    root_url=config.root_url,
                    page_url=page.url,
                    page_title=page.title,
                    elements=elements,
                    evidence_b64_map=evidence_crops,
                ))

            # 3.5 Interaction & Layout Validation
            if config.check_interactions:
                page_defects.extend(interaction_validator.validate_element_states(
                    root_url=config.root_url,
                    page_url=page.url,
                    page_title=page.title,
                    elements=elements,
                    evidence_b64_map=evidence_crops,
                ))

        # If no FAIL issues occurred on this page, emit a PASS record
        page_fails = [d for d in page_defects if d.status == "FAIL"]
        if not page_fails:
            pass_defect = create_defect(
                root_url=config.root_url,
                crawled_url=page.url,
                page_title=page.title or "(Untitled Page)",
                element_type="Page",
                element_identifier=page.url,
                element_selector="html",
                expected_behavior="All discovered links, images, inputs, and components meet quality checks.",
                actual_behavior=f"Verified {len(elements)} DOM elements and visual layout against baseline. No defects discovered.",
                defect_category="Other",
                status="PASS",
                http_status=page.status,
                error_message="",
                evidence_image_b64=ScreenshotManager.image_to_base64(img_bgr) if img_bgr is not None else "",
                confidence=1.0,
                severity="Info",
            )
            page_defects.append(pass_defect)

        # 3.6 Persist Screenshots & Annotations
        screenshot_filename = f"page_{idx:02d}_screenshot.png"
        annotated_filename = f"page_{idx:02d}_annotated.png"

        screenshot_rel = ""
        annotated_rel = ""

        if page.screenshot_png:
            screenshot_rel = ScreenshotManager.save_evidence_file(
                run_dir, screenshot_filename, page.screenshot_png
            )

        annotated_bgr = None
        if img_bgr is not None:
            raw_defects_dict = [d.to_dict() for d in page_defects]
            annotated_bgr = ScreenshotManager.annotate_defects(img_bgr, raw_defects_dict)
            annotated_bytes = ScreenshotManager.bgr_to_bytes(annotated_bgr)
            if annotated_bytes:
                annotated_rel = ScreenshotManager.save_evidence_file(
                    run_dir, annotated_filename, annotated_bytes
                )

        # Assign screenshot paths and crops to defects
        for d in page_defects:
            if d.status == "FAIL":
                d.screenshot_path = annotated_rel or screenshot_rel
                if not d.crop_localized_b64 and d.bbox and img_bgr is not None:
                    d.crop_localized_b64 = ScreenshotManager.crop_element_b64(img_bgr, d.bbox)
                if not d.crop_baseline_b64 and d.bbox and img_en_bgr is not None:
                    d.crop_baseline_b64 = ScreenshotManager.crop_element_b64(img_en_bgr, d.bbox)
        # Filter out truncation, invisible element, and raw DOM layout collisions per user requirement
        page_defects = [
            d for d in page_defects
            if "truncat" not in (d.defect_category or "").lower()
            and "truncat" not in (d.error_message or "").lower()
            and "truncat" not in (d.actual_behavior or "").lower()
            and "invisible" not in (d.defect_category or "").lower()
            and "hidden" not in (d.defect_category or "").lower()
            and d.element_type != "Layout Collision"
        ]

        all_defects.extend(page_defects)

        # Pairwise visual images from CV engine if available
        cv_images = (cv_result.get("images") or {}) if cv_result else {}

        # Page summary for UI rendering
        page_summaries.append({
            "url": page.url,
            "baseline_url": matched_baseline.url if matched_baseline else "",
            "title": page.title,
            "baseline_title": matched_baseline.title if matched_baseline else "",
            "depth": page.depth,
            "http_status": page.status,
            "duration_ms": page.duration_ms,
            "error": page.navigation_error,
            "element_counts": ElementAnalyzer.get_element_counts(elements),
            "screenshot": screenshot_rel,
            "annotated": annotated_rel,
            "screenshot_b64": cv_images.get("localized_image") or (ScreenshotManager.image_to_base64(img_bgr) if img_bgr is not None else ""),
            "baseline_b64": cv_images.get("baseline_image") or (ScreenshotManager.image_to_base64(img_en_bgr) if img_en_bgr is not None else ""),
            "annotated_b64": cv_images.get("annotated_diff_image") or (ScreenshotManager.image_to_base64(annotated_bgr) if annotated_bgr is not None else ""),
            "heatmap_b64": cv_images.get("heatmap_image") or "",
            "defects_count": len([d for d in page_defects if d.status == "FAIL"]),
            "score": cv_result.get("score") if cv_result else None,
        })


    # 4. Aggregate Summary Metrics
    defects_dict_list = [d.to_dict() for d in all_defects]
    legacy_issues_list = [d.to_legacy_format() for d in all_defects]

    fail_count = sum(1 for d in all_defects if d.status == "FAIL")
    pass_count = max(0, total_elements_checked - fail_count)

    category_breakdown: Dict[str, int] = {cat: 0 for cat in ALL_DEFECT_CATEGORIES}
    for d in all_defects:
        if d.status == "FAIL" and d.defect_category in category_breakdown:
            category_breakdown[d.defect_category] += 1

    summary_stats = {
        "pages_crawled": len(target_pages),
        "total_elements_checked": total_elements_checked,
        "total_links_checked": total_links_checked,
        "total_images_checked": total_images_checked,
        "total_interactions_checked": total_interactions_checked,
        "fail_count": fail_count,
        "pass_count": pass_count,
        "total_defects": fail_count,
        "status": "FAIL" if fail_count > 0 else "PASS",
        "category_breakdown": category_breakdown,
    }

    report_payload = {
        "run_id": run_id,
        "mode": "site-crawl",
        "root_url": config.root_url,
        "baseline_root_url": config.baseline_root_url or "",
        "config": {
            "max_depth": config.max_depth,
            "max_pages": config.max_pages,
            "same_origin_only": config.same_origin_only,
            "viewport": {"width": config.viewport_width, "height": config.viewport_height},
            "check_links": config.check_links,
            "check_images": config.check_images,
            "check_interactions": config.check_interactions,
        },
        "summary": summary_stats,
        "pages": page_summaries,
        "defects": defects_dict_list,
        "issues": legacy_issues_list,  # For seamless backward compatibility with existing UI
        "reports": {
            "json": f"/api/reports/{run_id}/report.json",
            "csv": f"/api/reports/{run_id}/report.csv",
            "xlsx": f"/api/reports/{run_id}/report.xlsx",
        },
    }

    # 5. Generate Multi-Format Report Files
    ReportGenerator.generate_json_report(run_dir, report_payload)
    ReportGenerator.generate_csv_report(run_dir, defects_dict_list)
    ReportGenerator.generate_excel_report(run_dir, report_payload, defects_dict_list, page_summaries)

    return report_payload
