# UI Validation Framework — Analysis, Gaps, and Design

This document is the pre-implementation analysis of **UI_Validator_POC**. Code changes listed at the end were applied on top of the existing screenshot/BMP comparison POC without replacing it.

---

## 1. Existing Architecture Analysis

### 1.1 What the POC is

A **two-image localization visual QA** tool: English baseline bitmap vs localized bitmap. Findings are mapped to Autodesk LQA 4-digit codes. Users can upload files or capture two URLs with Playwright.

There is **no Selenium** in this repository. Browser automation is **Playwright (sync API)** only, used for a **single pair of page screenshots**, not for crawling.

### 1.2 Process topology

```
React (Vite :3000)  --proxy /api-->  FastAPI (uvicorn :8000)
                                          |
                                          +-- cv_engine.analyze_localization_quality()
                                          +-- Playwright capture_url_screenshot()  [URL mode only]
```

Frontend never calls port 8000 directly. `frontend/vite.config.js` proxies `/api` to `127.0.0.1:8000`.

### 1.3 Backend surface (`backend/main.py`)

| Endpoint | Role |
|---|---|
| `GET /api/health` | Liveness |
| `GET /api/presets` | Demo preset metadata |
| `GET /api/preset-image/{filename}` | Serve `backend/sample_data/` PNGs |
| `POST /api/analyze-preset` | Pair `en_baseline.png` with a preset PNG |
| `POST /api/analyze` | Multipart upload of two images |
| `POST /api/capture-and-analyze-url` | Playwright two-URL capture then CV |

All analysis paths decode to OpenCV BGR arrays and call **`analyze_localization_quality(img_en, img_loc)`**.

### 1.4 Image / “BMP” comparison flow

“BMP” in this POC means **bitmap pixel comparison**, not a dedicated Windows `.bmp` pipeline. Uploads are decoded with `cv2.imdecode` (PNG/JPEG/WebP work; BMP would decode if sent). The engine:

1. Rejects empty images.
2. **Zero-noise shortcut**: if shapes match and mean `absdiff` &lt; 0.8 → score 100, no findings.
3. Resizes both images to a shared canvas.
4. Contour-based **container** and **text-line** detection.
5. Heuristic LQA checks (ellipsis truncation, button overflow, overlap, missing controls, header shift, combo height, corrupted glyphs, etc.).
6. Deduplicates overlapping boxes, draws annotated badges, builds a JET heatmap.
7. Score = `100 - (critical×25 + major×15 + minor×5)`.
8. Returns JSON: `score`, `summary`, `findings[]`, `images` (base64 PNG data URLs).

**Extension point:** `analyze_localization_quality` is the single CV entry. Helpers `detect_ellipsis_precise`, `detect_corrupted_glyph`, `detect_ui_containers`, `extract_text_lines`, `image_to_base64`, `crop_region_base64` are reusable without changing the pair-comparison contract.

### 1.5 Playwright integration (existing)

`capture_url_screenshot` in `main.py`:

- Headless Chromium, viewport 1280×800.
- `goto(..., wait_until="networkidle")` with `load` fallback.
- Viewport screenshot (`full_page=False`), bytes → `cv2.imdecode`.
- Auto `playwright install chromium` if the executable is missing.

`backend/test_playwright.py` is a smoke test only. **No link crawl, no DOM inventory.**

### 1.6 Frontend flow (`frontend/src/App.jsx`)

Two input modes in `ImageUploader.jsx`: **Upload Images** and **Auto-Capture URL**. Results render:

`Scorecard` → `DiffViewer` → `FindingsList` → `FindingModal` → `ReportExporter` (client-side **PDF only** via jsPDF).

`PresetSelector.jsx` exists but is **not mounted**.

### 1.7 Reporting (existing)

- **In-app JSON** from FastAPI (findings + base64 images).
- **PDF** generated in the browser (`ReportExporter.jsx`).
- **No JSON file download, CSV, or Excel.**
- No per-issue schema of `{Page, Element, Issue, Confidence, Status, Details, EvidenceImage}`.

### 1.8 Tests and fixtures

- `backend/test_engine.py` — score bands on `sample_data/` presets.
- `test_images/` + `TEST_GUIDE.md` — 22 synthetic Autodesk-style screenshots.
- Generator/calibration scripts are offline dataset tools, not runtime.

### 1.9 Important limitation

Several CV rules use **fixed pixel gutters** tuned to those synthetic screenshots (e.g. overlap strip around x≈936, button bar around y≈690). Pairwise CV remains valuable for similar layouts and for heatmap/annotation; **DOM geometry is more reliable** on arbitrary crawled sites.

---

## 2. Gap Analysis

| Required capability | Existing | Gap |
|---|---|---|
| Root URL in | Two explicit URLs, no crawl | No site graph |
| Recursive crawl + depth | None | Need BFS, max depth/pages, same-origin filter |
| Element inventory (button, textbox, dropdown, label, checkbox, radio, link, icon, image, table) | Contour guesses only | Need Playwright DOM extraction |
| Per-page screenshots | One pair of viewports | Need one (or pair) per crawled page |
| Missing / hidden / extra controls | Pixel heuristics vs English bitmap | Need DOM visibility + optional baseline inventory diff |
| Broken images | None | `img` complete / naturalWidth |
| Layout / overlap / misalignment | CV heuristics (often layout-specific) | DOM bounding boxes + reuse CV when a baseline pair exists |
| Truncation / overflow | Ellipsis contours + button HSV | DOM `scrollWidth`/`clientWidth` + existing ellipsis detector |
| Hotkeys | None | `accessKey`, duplicate accelerators, `&` mnemonics |
| Symbol / punctuation | Glyph diamond + HTML-entity-ish CV | DOM text entities + optional OCR |
| OCR | None | Optional Tesseract; fallback to existing glyph detector |
| JSON / CSV / Excel reports | PDF only | Server-side report builder |
| Framework issue schema | LQA finding objects | Adapter to `{Page, Element, Issue, ...}` |
| Backward compatible BMP compare | Working | **Must keep** `/api/analyze`, URL pair, presets, UI tabs |

---

## 3. Proposed Design

Keep the existing app as **Mode A: Bitmap compare**. Add **Mode B: Site crawl framework**.

```
Root URL (+ optional Baseline Root URL)
        │
        ▼
Playwright BFS crawl (depth, max pages, same origin)
        │
        ▼
Per page: DOM extract + viewport screenshot
        │
        ├─ DOM validators (overflow, hidden, broken img, overlap,
        │   alignment, hotkeys, punctuation, missing/extra vs baseline)
        ├─ OpenCV on screenshot (ellipsis, glyphs, containers)
        └─ If baseline page paired: analyze_localization_quality()
        │
        ▼
Annotate evidence PNGs
        │
        ▼
PASS/FAIL issue list + JSON / CSV / XLSX
```

**Optional baseline root URL:** crawl both sites, pair by URL path, then run the **existing CV engine** plus inventory diff (missing/extra controls). If omitted, Mode B still validates a single site via DOM + single-image CV.

**Issue record** (exactly the requested fields):

```json
{
  "Page": "https://...",
  "Element": "BUTTON: Submit",
  "Issue": "Text overflow",
  "Confidence": 0.95,
  "Status": "FAIL",
  "Details": "...",
  "EvidenceImage": "data:image/png;base64,..."
}
```

Pages with no FAILs emit one page-level **PASS** row.

---

## 4. Files To Modify

| File | Change |
|---|---|
| `backend/main.py` | Add crawl/validate + report download routes; leave existing routes unchanged |
| `backend/requirements.txt` / `requirements.txt` | `openpyxl`; optional `pytesseract` |
| `frontend/src/App.jsx` | Crawl state + handler; do not remove upload/URL analyze |
| `frontend/src/components/ImageUploader.jsx` | Third tab: Site Crawl |
| `README.md` | Document Mode B |
| `.gitignore` | Ignore `backend/reports/` |
| `frontend` accept types | Include `.bmp` on upload inputs |

`cv_engine.py` is **not rewritten**. Call it from the framework; do not change scoring/finding JSON for Mode A.

---

## 5. New Files To Create

| File | Role |
|---|---|
| `backend/crawler.py` | Playwright BFS crawl + screenshot |
| `backend/element_extractor.py` | DOM UI-element inventory |
| `backend/page_validator.py` | DOM + visual checks → framework issues |
| `backend/ocr_utils.py` | Optional Tesseract; safe fallback |
| `backend/report_builder.py` | JSON / CSV / Excel + evidence files |
| `backend/framework.py` | Orchestrator |
| `frontend/src/components/CrawlResults.jsx` | Pages, issues table, report downloads |

---

## 6. Implementation notes (applied)

- Existing `/api/analyze`, `/api/capture-and-analyze-url`, presets, Scorecard, DiffViewer, PDF exporter remain.
- New `POST /api/crawl-and-validate` and `GET /api/reports/{run_id}/{filename}`.
- Playwright is reused; Selenium is still not introduced.
