# Localization UI Quality Checker (POC)

A visual UI quality validation tool that compares an **English baseline screenshot** against a **Localized screenshot** (German, Spanish, Japanese, etc.) to automatically detect layout breakages and translation expansion defects.

> **Zero AI / Cloud Costs**: Built purely with **OpenCV (`cv2`)** and **NumPy** on Python FastAPI with a React frontend.

---

## 📖 How to Use

Once the application is running at **`http://localhost:3000`**, you can test it using any of the 3 methods below:

### Method 1: 1-Click Sample Demos (Fastest)
1. At the top of the page, click on any of the 4 preloaded test scenarios:
   - **German (Clean Quality)**: Normal text expansion (+25% length) $\rightarrow$ *Scores 100/100 (Pass)*.
   - **German (Button Text Overflow)**: Fixed button width causes text to spill past borders $\rightarrow$ *Scores 75/100*.
   - **Spanish (Missing Component)**: Secondary button omitted $\rightarrow$ *Scores 50/100*.
   - **Japanese (Header Shift)**: Top header displaced downwards by 28px $\rightarrow$ *Scores 60/100*.
2. The score, diff views, and findings list will update immediately.

---

### Method 2: Upload Your Own Screenshots
1. Stay on the **"Upload Images"** tab.
2. Drag and drop (or click to browse) your **English Reference Screenshot** into the left box.
3. Drag and drop your **Localized Screenshot** into the right box.
4. Click **"Compare & Check UI Quality"**.

---

### Method 3: Auto-Capture from Live Web URLs
1. Switch to the **"Auto-Capture URL"** tab on the main card.
2. Enter your **English Baseline URL** (e.g. `https://example.com/en/support`).
3. Enter your **Localized Target URL** (e.g. `https://example.com/de/support`).
4. Click **"Auto-Capture & Analyze"**.
5. Headless Chromium will automatically open both links, take $1280\times800\text{px}$ screenshots, and run the quality comparison.

---

### Understanding the Results

1. **Quality Scorecard**:
   - **Score (0–100) & Grade (A+ to F)**: Overall layout integrity.
   - **Defect Breakdown**: Counts of Critical, Major, and Minor defects.
   - **Checklist**: Status of each individual quality factor check.

2. **Visual Diff Viewer**:
   - **Side-by-Side Comparison**: Side-by-side view of baseline and localized images.
   - **Defects Highlighted**: Shows color-coded bounding boxes around every detected flaw.
   - **Difference Heatmap**: Highlights modified and shifted pixels in color.

3. **Findings & Code Fixes**:
   - Lists each issue with exact pixel coordinates $(x, y, w, h)$.
   - Shows before/after visual crop snippets.
   - Provides copyable CSS/HTML remediation code to fix the issue.

4. **Export Audit Report**:
   - Click **"Download PDF Report"** to export a clean, shareable audit report.

---

## 🛠️ What the Engine Checks

| Category | Allowed (Normal) | Flagged (Defect) |
|---|---|---|
| **Text Length Expansion** | +10% to +40% longer words that fit inside containers cleanly. | Text spilling outside button or input borders. |
| **Text Truncation** | Full translated strings rendered without cutoffs. | Text cut off with trailing ellipsis (`...` or `…`). |
| **Component Presence** | All interactive controls preserved. | Buttons, icons, or badges missing from localized UI. |
| **Component Spacing** | Elements separated with clean margins. | Sibling buttons or widgets overlapping / colliding. |
| **Layout Stability** | Elements anchored to grid. | Headers or sections shifted by $\ge 20\text{px}$. |
| **Identical Images** | Same screenshot uploaded twice $\rightarrow$ **100/100 (0 errors)**. | Zero pixel-noise false alarms. |

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

**On macOS / Linux:**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload --port 8000
```

**On Windows (PowerShell):**
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
python -m uvicorn main:app --reload --port 8000
```

### Step 3: Start the React Frontend

**On macOS / Linux / Windows:**
```bash
cd frontend
npm install
npm run dev
```
---

## 📂 Project Structure

```
UI_Validator_POC/
├── backend/
│   ├── cv_engine.py           # OpenCV & NumPy detection pipeline (11 UI factors)
│   ├── dataset_generator.py   # Test scenario screenshot generator
│   ├── main.py                # FastAPI REST API + Playwright URL capture
│   ├── requirements.txt       # Python dependencies
│   └── sample_data/           # Sample test screenshots
├── frontend/
│   ├── src/
│   │   ├── components/        # UI components (Scorecard, DiffViewer, Exporter, etc.)
│   │   ├── App.jsx            # Main app orchestrator
│   │   └── index.css          # Tailwind CSS styles
│   ├── package.json           # Frontend dependencies
│   └── vite.config.js         # Vite configuration
├── .gitignore
└── README.md
```

---
