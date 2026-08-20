from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Optional
import os
import cv2
import numpy as np
from PIL import Image
import io
from playwright.sync_api import sync_playwright

from cv_engine import analyze_localization_quality, sanitize_for_json

app = FastAPI(title="Localization UI Quality Checker API", version="1.0.0")

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
        "filename": "de_perfect.png"
    },
    {
        "id": "de_expansion_defect",
        "title": "German (Button Text Overflow)",
        "language": "German",
        "expected_result": "Critical Defect",
        "description": "Primary action button has fixed 145px width causing longer German label to burst past borders and collide with adjacent controls.",
        "filename": "de_expansion_defect.png"
    },
    {
        "id": "es_missing_misaligned",
        "title": "Spanish (Missing Component & Alignment)",
        "language": "Spanish",
        "expected_result": "Critical & Minor Defects",
        "description": "Secondary action button ('Attach Log File') is completely omitted, and the top product dropdown is misaligned by +30px.",
        "filename": "es_missing_misaligned.png"
    },
    {
        "id": "ja_shift_overlap",
        "title": "Japanese (Header Shift & Collision)",
        "language": "Japanese",
        "expected_result": "Major & Critical Defects",
        "description": "Global dark header is displaced vertically by 28px, and the central form card overlaps the right help widget.",
        "filename": "ja_shift_overlap.png"
    }
]

def capture_url_screenshot(url: str, width: int = 1280, height: int = 800, wait_seconds: float = 1.0) -> np.ndarray:
    """Captures a high-resolution screenshot of a web URL using headless Chromium."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=20000)
        except Exception:
            # Fallback to load state if networkidle times out
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
    return {"status": "healthy", "engine": "OpenCV / NumPy + Playwright Auto-Capture"}

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
            wait_seconds=req.wait_seconds or 1.0
        )
        img_loc = capture_url_screenshot(
            req.localized_url,
            width=req.viewport_width or 1280,
            height=req.viewport_height or 800,
            wait_seconds=req.wait_seconds or 1.0
        )

        if img_en is None or img_loc is None:
            raise HTTPException(status_code=400, detail="Failed to capture screenshot from one or both URLs.")

        result = analyze_localization_quality(img_en, img_loc)
        return JSONResponse(content=sanitize_for_json(result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Live URL Auto-Capture failed: {str(e)}")
