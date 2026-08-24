"""
FastAPI Backend Application Entry Point.
Serves:
  1. Web Crawling & UI Element Validation Engine (/api/crawl-and-validate)
  2. Multi-Format Report & Evidence Downloads (/api/reports/...)
  3. Preserved Pairwise Image & URL Comparison (/api/analyze, /api/capture-and-analyze-url)
  4. Presets and System Health Check (/api/presets, /api/health)
"""

from __future__ import annotations

import io
import logging
import os
import sys
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image
from playwright.sync_api import sync_playwright
from pydantic import BaseModel, Field

from cv_engine import analyze_localization_quality, sanitize_for_json
from framework import run_framework
from report_generator import REPORTS_BASE_DIR

# Configure structured application logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("UI_Validator_API")

app = FastAPI(
    title="Web UI Quality & Localization Validation Engine",
    description="Automated Playwright Web Crawler, DOM Element Validator, and Computer Vision Quality Engine.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SAMPLE_DATA_DIR = os.path.join(os.path.dirname(__file__), "sample_data")

PRESETS = [
    {
        "id": "de_perfect",
        "title": "German (Clean Quality)",
        "language": "German",
        "expected_result": "Pass (100/100)",
        "description": "Standard translated support ticket form with properly expanded button widths and clean alignment.",
        "filename": "de_perfect.png",
    },
    {
        "id": "de_expansion_defect",
        "title": "German (Button Text Overflow)",
        "language": "German",
        "expected_result": "Critical Defect",
        "description": "Primary action button has fixed 145px width causing longer German label to burst past borders and collide with adjacent controls.",
        "filename": "de_expansion_defect.png",
    },
    {
        "id": "es_missing_misaligned",
        "title": "Spanish (Missing Component & Alignment)",
        "language": "Spanish",
        "expected_result": "Critical & Minor Defects",
        "description": "Secondary action button ('Attach Log File') is completely omitted, and the top product dropdown is misaligned by +30px.",
        "filename": "es_missing_misaligned.png",
    },
    {
        "id": "ja_shift_overlap",
        "title": "Japanese (Header Shift & Collision)",
        "language": "Japanese",
        "expected_result": "Major & Critical Defects",
        "description": "Global dark header is displaced vertically by 28px, and the central form card overlaps the right help widget.",
        "filename": "ja_shift_overlap.png",
    },
]


def capture_url_screenshot(url: str, width: int = 1280, height: int = 800, wait_seconds: float = 1.0) -> np.ndarray:
    """Captures a high-resolution screenshot of a web URL using headless Chromium."""
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as launch_err:
            if "Executable doesn't exist" in str(launch_err) or "playwright install" in str(launch_err):
                import subprocess
                try:
                    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
                    browser = p.chromium.launch(headless=True)
                except Exception:
                    raise RuntimeError("Playwright Chromium is not installed. Please run: 'playwright install chromium'.")
            else:
                raise launch_err

        context = browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=20000)
        except Exception:
            page.goto(url, wait_until="load", timeout=15000)

        if wait_seconds > 0:
            page.wait_for_timeout(int(wait_seconds * 1000))

        screenshot_bytes = page.screenshot(full_page=False)
        browser.close()

        nparr = np.frombuffer(screenshot_bytes, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img_bgr


@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "engine": "OpenCV / NumPy + Playwright Crawler & DOM Element Validator",
        "modes": ["site-crawl", "bitmap-compare", "url-pair"],
        "version": "2.0.0",
    }


@app.get("/api/presets")
def get_presets():
    return PRESETS


@app.get("/api/preset-image/{filename}")
def get_preset_image(filename: str):
    file_path = os.path.join(SAMPLE_DATA_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Preset image not found")
    return FileResponse(file_path, media_type="image/png")


@app.post("/api/analyze-preset")
def analyze_preset(preset_id: str = Form(...)):
    preset = next((p for p in PRESETS if p["id"] == preset_id), None)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    baseline_path = os.path.join(SAMPLE_DATA_DIR, "en_baseline.png")
    localized_path = os.path.join(SAMPLE_DATA_DIR, preset["filename"])

    if not os.path.exists(baseline_path) or not os.path.exists(localized_path):
        raise HTTPException(status_code=500, detail="Preset sample images missing on server")

    img_en = cv2.imread(baseline_path)
    img_loc = cv2.imread(localized_path)

    result = analyze_localization_quality(img_en, img_loc)
    return JSONResponse(content=sanitize_for_json(result))


@app.post("/api/analyze")
async def analyze_custom_images(
    english_image: UploadFile = File(...),
    localized_image: UploadFile = File(...)
):
    """Pairwise uploaded bitmap comparison (Preserves existing POC functionality)."""
    try:
        en_bytes = await english_image.read()
        loc_bytes = await localized_image.read()

        nparr_en = np.frombuffer(en_bytes, np.uint8)
        img_en = cv2.imdecode(nparr_en, cv2.IMREAD_COLOR)

        nparr_loc = np.frombuffer(loc_bytes, np.uint8)
        img_loc = cv2.imdecode(nparr_loc, cv2.IMREAD_COLOR)

        if img_en is None or img_loc is None:
            raise HTTPException(status_code=400, detail="Invalid image format. Could not decode images.")

        result = analyze_localization_quality(img_en, img_loc)
        return JSONResponse(content=sanitize_for_json(result))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image analysis exception: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


class UrlCaptureRequest(BaseModel):
    english_url: str
    localized_url: str
    viewport_width: Optional[int] = 1280
    viewport_height: Optional[int] = 800
    wait_seconds: Optional[float] = 1.0


@app.post("/api/capture-and-analyze-url")
def capture_and_analyze_url(req: UrlCaptureRequest):
    """Automatically captures screenshots of two live web URLs and compares UI localization quality."""
    try:
        img_en = capture_url_screenshot(
            req.english_url,
            width=req.viewport_width or 1280,
            height=req.viewport_height or 800,
            wait_seconds=req.wait_seconds or 1.0,
        )
        img_loc = capture_url_screenshot(
            req.localized_url,
            width=req.viewport_width or 1280,
            height=req.viewport_height or 800,
            wait_seconds=req.wait_seconds or 1.0,
        )

        if img_en is None or img_loc is None:
            raise HTTPException(status_code=400, detail="Failed to capture screenshot from one or both URLs.")

        result = analyze_localization_quality(img_en, img_loc)
        return JSONResponse(content=sanitize_for_json(result))
    except Exception as e:
        logger.error(f"URL Auto-capture exception: {e}")
        raise HTTPException(status_code=500, detail=f"Live URL Auto-Capture failed: {str(e)}")


class CrawlValidateRequest(BaseModel):
    root_url: str
    baseline_root_url: Optional[str] = None
    max_depth: Optional[int] = Field(default=2, ge=0, le=5)
    max_pages: Optional[int] = Field(default=10, ge=1, le=50)
    same_origin_only: Optional[bool] = True
    viewport_width: Optional[int] = 1280
    viewport_height: Optional[int] = 800
    wait_seconds: Optional[float] = 1.0
    timeout_ms: Optional[int] = 25000
    check_links: Optional[bool] = True
    check_images: Optional[bool] = True
    check_interactions: Optional[bool] = True
    safe_interactions_only: Optional[bool] = True


@app.post("/api/crawl-and-validate")
def crawl_and_validate(req: CrawlValidateRequest):
    """
    Crawls from a Root URL, discovers web elements, validates broken links/images/interactions/JS errors,
    recursively traverses internal pages, collects defects, and generates final JSON/CSV/Excel reports.
    """
    try:
        logger.info(f"Received Crawl & Validate request for root_url: {req.root_url}")
        result = run_framework(
            root_url=req.root_url,
            baseline_root_url=(req.baseline_root_url or None),
            max_depth=req.max_depth if req.max_depth is not None else 2,
            max_pages=req.max_pages if req.max_pages is not None else 10,
            same_origin_only=True if req.same_origin_only is None else req.same_origin_only,
            viewport_width=req.viewport_width or 1280,
            viewport_height=req.viewport_height or 800,
            wait_seconds=req.wait_seconds if req.wait_seconds is not None else 1.0,
            timeout_ms=req.timeout_ms or 25000,
            check_links=True if req.check_links is None else req.check_links,
            check_images=True if req.check_images is None else req.check_images,
            check_interactions=True if req.check_interactions is None else req.check_interactions,
            safe_interactions_only=True if req.safe_interactions_only is None else req.safe_interactions_only,
        )
        return JSONResponse(content=result)
    except Exception as e:
        logger.exception("Site crawl validation failed")
        raise HTTPException(status_code=500, detail=f"Site crawl validation failed: {str(e)}")


@app.get("/api/reports/{run_id}/{filename}")
def download_report(run_id: str, filename: str):
    """Serves generated JSON, CSV, and Excel reports."""
    safe_run = "".join(ch for ch in run_id if ch.isalnum() or ch in "-_")
    allowed = {"report.json", "report.csv", "report.xlsx"}
    if filename not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported report file")
    path = os.path.join(REPORTS_BASE_DIR, safe_run, filename)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Report file not found")
    media = {
        "report.json": "application/json",
        "report.csv": "text/csv",
        "report.xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }[filename]
    return FileResponse(path, media_type=media, filename=filename)


@app.get("/api/reports/{run_id}/evidence/{filename}")
def download_evidence(run_id: str, filename: str):
    """Serves captured screenshot evidence PNG files."""
    safe_run = "".join(ch for ch in run_id if ch.isalnum() or ch in "-_")
    safe_file = os.path.basename(filename)
    if not safe_file.endswith(".png"):
        raise HTTPException(status_code=400, detail="Only PNG evidence is available")
    path = os.path.join(REPORTS_BASE_DIR, safe_run, "evidence", safe_file)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Evidence image not found")
    return FileResponse(path, media_type="image/png", filename=safe_file)
