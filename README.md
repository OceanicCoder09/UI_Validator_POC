# Autodesk Localization UI Quality Validator (LQA Engine)

An automated Computer Vision visual quality validation platform that compares an **English baseline screenshot** against **localized screenshots** (German, Spanish, French, Japanese, Chinese, Italian, Portuguese, Korean, etc.) to automatically detect layout regressions, text truncations, and translation expansion defects.

Built on the official **Autodesk Enterprise Localization QA (LQA) Defect Taxonomy Standard**.

> **⚡ Zero AI / Cloud Costs**: Powered purely by deterministic **OpenCV (`cv2`)** and **NumPy** on Python FastAPI with a React frontend and Playwright headless URL capture.

---

## 🎯 Autodesk LQA Defect Taxonomy (12 Categories)

Every detected finding is automatically mapped to its official 4-digit Autodesk error classification code:

| Defect Code | Category | Description & Detection Logic |
|:---:|---|---|
| **`0001`** | **`OVERLAPPING`** | Component collisions, expanding cards colliding with sidebars / sibling widgets ($A \cap B > 0$). |
| **`0004`** | **`MISSALIGNMENT`** | Grid alignment shifts, vertical header displacement ($\ge 20\text{px}$), form field indents, and sibling card width discrepancies. |
| **`0005`** | **`LEAD_TRAIL`** | Leading / trailing whitespace anomalies and missing mandatory field punctuation (`*` / `:`). |
| **`0006`** | **`MISC`** | Missing action buttons in button bars and omitted navigation header utility icons. |
| **`0008`** | **`SPEC_CHARACTERS`** | Unescaped HTML entities (`&amp;`, `&quot;`) or raw template tags in rendered text lines. |
| **`0009`** | **`TRUNCATION`** | Shift-compensated text truncation with ellipsis (`...` / `…`) and button text spilling past fixed boundaries. |
| **`0011`** | **`FONT_CONSISTENCY`** | Font typography, scale, and stroke thickness variance relative to baseline. |
| **`0012`** | **`COMBO_BOX_HEIGHT`** | Dropdown / select box container height too small ($< 30\text{px}$) causing text padding clipping. |
| **`0014`** | **`CAPTURE_BITMAP_FAILED`** | Playwright network timeout / headless browser page render failure handler. |
| **`0015`** | **`BITMAP_DIFFERENCE`** | Normalized structural pixel regression delta & JET colormap difference heatmap. |
| **`0016`** | **`EXTENDED_CHAR_ISSUE`** | Corrupted character glyphs (Unicode black replacement diamond ``, broken tofu boxes `□`). |
| **`0020`** | **`UNKNOWN_ERROR`** | Fallback exception handler for uncategorized layout anomalies. |

---

## 📖 How to Use

Once the application is running at **`http://localhost:3000`**:

### Method 1: Upload Screenshots
1. Stay on the **"Upload Images"** tab.
2. Drag and drop (or click to browse) your **English Reference Screenshot** into the left box (e.g. from `test_images/01_Baseline_English_Reference.png`).
3. Drag and drop your **Localized Target Screenshot** into the right box (e.g. from `test_images/`).
4. Click **"Analyze Screenshots"**.

---

### Method 2: Auto-Capture from Live Web URLs
1. Switch to the **"Auto-Capture URL"** tab on the main card.
2. Enter your **English Baseline URL** (e.g. `https://help.autodesk.com/view/ACD/2026/ENU/`).
3. Enter your **Localized Target URL** (e.g. `https://help.autodesk.com/view/ACD/2026/DEU/` or `CHS/`).
4. Click **"Auto-Capture & Analyze"**.
5. Headless Chromium automatically opens both links, captures full $1280\times800\text{px}$ snapshots, and runs visual quality analysis.

---

### Understanding the Results

1. **Quality Score & Summary**:
   - **Numerical Quality Score (0–100)**: Calculated based on defect severity penalties.
   - **Severity Breakdown**: Counts of Critical, Major, and Minor defects.
   - **Layout Integrity Percentage**: Overall structural layout health.

2. **Visual Diff Viewer**:
   - **Side-by-Side Comparison**: Synchronized view of baseline and localized screenshots.
   - **Annotated Localized View**: Color-coded bounding boxes with Autodesk LQA error badges (e.g. `[ERR-0009] TRUNCATION`).
   - **Structural Heatmap**: Thermal colormap showing exact pixel variance.

3. **Findings & Remediation Snippets**:
   - Lists each issue with exact pixel coordinates $(x, y, w, h)$.
   - Shows before / after visual crop snippets.
   - Provides ready-to-use CSS / HTML remediation code to fix each defect.

4. **Consolidated PDF Audit Report**:
   - Click **"Download Audit Report (PDF)"** to export an official audit document with executive summary, both embedded screenshots, and full issue listings.

---

## 🧪 Standardized 22-Image Test Suite

The `test_images/` directory contains a standardized 22-screenshot test library across **7 languages** (English, German, Spanish, French, Japanese, Italian, Portuguese, Korean, Chinese):

| # | Test File | Language | Scenario / Defect | Expected Score | Expected LQA Code |
|:---:|---|:---:|---|:---:|:---:|
| **01** | `01_Baseline_English_Reference.png` | **English** | **Baseline Reference Standard** | — | *Reference* |
| **02** | `02_German_Clean_Perfect_100.png` | German | Clean Translation | **100 / 100** | **Pass (0 Defects)** |
| **03** | `03_Spanish_Clean_Perfect_100.png` | Spanish | Clean Translation | **100 / 100** | **Pass (0 Defects)** |
| **04** | `04_French_Clean_Perfect_100.png` | French | Clean Translation | **100 / 100** | **Pass (0 Defects)** |
| **05** | `05_Japanese_Clean_Perfect_100.png` | Japanese | Clean Translation | **100 / 100** | **Pass (0 Defects)** |
| **06** | `06_Italian_Clean_Perfect_100.png` | Italian | Clean Translation | **100 / 100** | **Pass (0 Defects)** |
| **07** | `07_Portuguese_Clean_Perfect_100.png` | Portuguese | Clean Translation | **100 / 100** | **Pass (0 Defects)** |
| **08** | `08_Korean_Clean_Perfect_100.png` | Korean | Clean Translation | **100 / 100** | **Pass (0 Defects)** |
| **09** | `09_German_Button_Overflow_ERR0009.png` | German | Primary button label spills past border | **75 / 100** | **`[ERR-0009] TRUNCATION`** |
| **10** | `10_French_Button_Overflow_ERR0009.png` | French | Primary button label spills past border | **75 / 100** | **`[ERR-0009] TRUNCATION`** |
| **11** | `11_Spanish_Missing_Button_ERR0006.png` | Spanish | Secondary action button omitted | **75 / 100** | **`[ERR-0006] MISC`** |
| **12** | `12_French_Missing_Help_Icon_ERR0006.png` | French | Header Help (?) icon omitted | **75 / 100** | **`[ERR-0006] MISC`** |
| **13** | `13_Spanish_Form_Dropdown_Misaligned_ERR0004.png` | Spanish | Form select input indented +30px off-grid | **95 / 100** | **`[ERR-0004] MISSALIGNMENT`** |
| **14** | `14_German_Form_Dropdown_Misaligned_ERR0004.png` | German | Form select input indented +30px off-grid | **95 / 100** | **`[ERR-0004] MISSALIGNMENT`** |
| **15** | `15_Japanese_Header_Bar_Shift_ERR0004.png` | Japanese | Navigation header shifted down 28px | **85 / 100** | **`[ERR-0004] MISSALIGNMENT`** |
| **16** | `16_Japanese_Card_Widget_Collision_ERR0001.png` | Japanese | Form card expanded into right widget | **75 / 100** | **`[ERR-0001] OVERLAPPING`** |
| **17** | `17_Spanish_Missing_And_Misaligned_Combo.png` | Spanish | Missing button + Form dropdown offset | **70 / 100** | **`[ERR-0006]` & `[ERR-0004]`** |
| **18** | `18_German_Overflow_And_Misaligned_Combo.png` | German | Button overflow + Form dropdown offset | **70 / 100** | **`[ERR-0009]` & `[ERR-0004]`** |
| **19** | `19_Italian_Overflow_And_Missing_Combo.png` | Italian | Button overflow + Missing button | **50 / 100** | **`[ERR-0009]` & `[ERR-0006]`** |
| **20** | `20_Japanese_Full_Cascade_Overlap_Shift_Combo.png` | Japanese | Card collision + Header shift + Missing icon | **35 / 100** | **`[ERR-0001]`, `[0004]`, `[0006]`** |
| **21** | `21_French_ComboBox_Height_Defect_ERR0012.png` | French | Dropdown container height restricted | **85 / 100** | **`[ERR-0012] COMBO_BOX_HEIGHT`** |
| **22** | `22_German_Corrupted_Glyph_Defect_ERR0016.png` | German | Corrupted Unicode replacement diamond () | **75 / 100** | **`[ERR-0016] EXTENDED_CHAR_ISSUE`** |

---

## 🚀 Installation & Setup

### Prerequisites
- **Python 3.10+**
- **Node.js 18+**

### Step 1: Clone the Repository
```bash
git clone https://github.com/OceanicCoder09/UI_Validator_POC.git
cd UI_Validator_POC
```

### Step 2: Start the Python Backend

**On Windows (PowerShell):**
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
python -m uvicorn main:app --reload --port 8000
```

**On macOS / Linux:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload --port 8000
```

### Step 3: Start the React Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend dashboard will be available at **`http://localhost:3000`**.

---

## 📂 Project Structure

```
UI_Validator_POC/
├── backend/
│   ├── cv_engine.py                # Full 12-rule Autodesk LQA Computer Vision Engine
│   ├── generate_20_test_images.py  # Standardized 22-screenshot test generator
│   ├── main.py                     # FastAPI REST API + Playwright URL capture
│   └── requirements.txt            # Python dependencies (fastapi, opencv, pillow, playwright)
├── frontend/
│   ├── src/
│   │   ├── components/             # React UI components (Scorecard, DiffViewer, Exporter, etc.)
│   │   ├── App.jsx                 # Main application dashboard
│   │   └── index.css               # Clean modern CSS styling
│   ├── package.json                # Frontend dependencies (React, Vite, jsPDF, html2canvas)
│   └── vite.config.js              # Vite bundler configuration
├── test_images/                    # 22 Standardized test screenshots (01 to 22)
│   └── TEST_GUIDE.md               # Complete test scenario matrix guide
├── .gitignore
└── README.md
```

---

## 🛡️ License

Internal Proof of Concept — Built for Autodesk Localization Quality Assurance (LQA) Automation.
