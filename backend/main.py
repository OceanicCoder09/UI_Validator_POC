"""
Localization UI Quality Checker - FastAPI Backend Server
Provides REST endpoints for comparing English reference screenshots against localized screenshots.
"""

import os
import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from typing import Optional

from cv_engine import analyze_localization_quality, sanitize_for_json, ensure_bgr3
from dataset_generator import generate_all_presets

app = FastAPI(
    title="Localization UI Quality Checker API",
    description="Backend service for Autodesk Helpdesk localization UI quality validation",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_data")
os.makedirs(SAMPLE_DIR, exist_ok=True)

if not os.path.exists(os.path.join(SAMPLE_DIR, "en_baseline.png")):
    generate_all_presets(SAMPLE_DIR)

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Localization UI Quality Checker",
        "engine": "OpenCV / NumPy Pure CV Engine",
        "version": "1.0.0",
        "cloud_free": True,
        "ai_free": True
    }

@app.get("/api/presets")
async def list_presets():
    """Returns available Autodesk Helpdesk UI test presets."""
    presets = [
        {
            "id": "de_perfect",
            "title": "German - Clean Quality",
            "subtitle": "Properly Sized & Translated",
            "description": "Clean German localization with translated strings ('Fall übermitteln', 'Protokolldatei anhängen'), correctly expanded containers, zero UI layout defects.",
            "expected_score": 100,
            "expected_defects": 0,
            "filename": "de_perfect.png",
            "baseline_filename": "en_baseline.png",
            "tags": ["German", "High Quality", "Pass"]
        },
        {
            "id": "de_expansion_defect",
            "title": "German - Button Text Overflow",
            "subtitle": "Container Overflow & Collision",
            "description": "German translation text length ('Technischen Support-Fall jetzt sofort absenden') bursts out of primary button container, truncates, and collides with adjacent 'Attach' button.",
            "expected_score": 75,
            "expected_defects": 1,
            "filename": "de_expansion_defect.png",
            "baseline_filename": "en_baseline.png",
            "tags": ["German", "Text Overflow", "Overlap Defect"]
        },
        {
            "id": "es_missing_misaligned",
            "title": "Spanish - Missing Action Button",
            "subtitle": "Omitted Button & Input Misalignment",
            "description": "Spanish localization where 'Attach Log File' button is completely missing from DOM, and 'Affected Product' input dropdown is indented by +30px causing ragged alignment.",
            "expected_score": 70,
            "expected_defects": 2,
            "filename": "es_missing_misaligned.png",
            "baseline_filename": "en_baseline.png",
            "tags": ["Spanish", "Missing Component", "Alignment Defect"]
        },
        {
            "id": "ja_shift_overlap",
            "title": "Japanese - Layout Shift & Overlap",
            "subtitle": "28px Header Shift & Component Overlap",
            "description": "Japanese localization where header is displaced 28px downward, Help icon is missing, and main support card expands colliding with right-hand urgent assistance panel.",
            "expected_score": 35,
            "expected_defects": 3,
            "filename": "ja_shift_overlap.png",
            "baseline_filename": "en_baseline.png",
            "tags": ["Japanese", "Layout Shift", "Severe Overlap"]
        }
    ]
    return JSONResponse(content=sanitize_for_json(presets))

@app.get("/api/preset-image/{filename}")
async def get_preset_image(filename: str):
    """Serves preset screenshot files."""
    file_path = os.path.join(SAMPLE_DIR, filename)
    if not os.path.exists(file_path):
        generate_all_presets(SAMPLE_DIR)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Preset image {filename} not found")
    return FileResponse(file_path, media_type="image/png")

@app.post("/api/analyze-preset")
async def analyze_preset(preset_id: str = Form(...)):
    """Runs analysis on a pre-loaded Autodesk test preset."""
    en_path = os.path.join(SAMPLE_DIR, "en_baseline.png")
    loc_path = os.path.join(SAMPLE_DIR, f"{preset_id}.png")
    
    if not os.path.exists(en_path) or not os.path.exists(loc_path):
        generate_all_presets(SAMPLE_DIR)
        
    img_en = cv2.imread(en_path, cv2.IMREAD_UNCHANGED)
    img_loc = cv2.imread(loc_path, cv2.IMREAD_UNCHANGED)
    
    if img_en is None or img_loc is None:
        raise HTTPException(status_code=400, detail="Failed to load preset images")
        
    result = analyze_localization_quality(img_en, img_loc)
    result["preset_id"] = str(preset_id)
    return JSONResponse(content=sanitize_for_json(result))

@app.post("/api/analyze")
async def analyze_custom_images(
    english_image: UploadFile = File(...),
    localized_image: UploadFile = File(...)
):
    """
    Analyzes uploaded English Baseline and Localized screenshots.
    Returns comprehensive defect findings, quality score, difference composite, and crops.
    """
    try:
        en_bytes = await english_image.read()
        loc_bytes = await localized_image.read()
        
        nparr_en = np.frombuffer(en_bytes, np.uint8)
        img_en = cv2.imdecode(nparr_en, cv2.IMREAD_UNCHANGED)
        
        nparr_loc = np.frombuffer(loc_bytes, np.uint8)
        img_loc = cv2.imdecode(nparr_loc, cv2.IMREAD_UNCHANGED)
        
        if img_en is None:
            raise HTTPException(status_code=400, detail="Invalid English reference image file")
        if img_loc is None:
            raise HTTPException(status_code=400, detail="Invalid Localized image file")
            
        result = analyze_localization_quality(img_en, img_loc)
        return JSONResponse(content=sanitize_for_json(result))
    except HTTPException as he:
        raise he
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Image processing failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
