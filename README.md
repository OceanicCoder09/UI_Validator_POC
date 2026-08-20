# Localization UI Quality Checker (POC)

An autonomous, production-ready Computer Vision tool designed to validate localization UI quality between an **English reference screenshot** and a **Localized screenshot** (Spanish, German, Japanese, French, etc.).

> **Engine Architecture**: Built purely with **OpenCV (`cv2`)** and **NumPy** — Zero external AI APIs, zero OpenAI/Azure dependencies, zero cloud services, and zero databases.

---

## 🌟 Key Features

1. **Intelligent Localization Quality Rules**:
   - **Tolerates Normal Localization Growth**: Accepts natural text length expansion (+10% to +40% longer words) and responsive container sizing.
   - **Zero False Positives on Clean UI**: Identical or properly expanded localized interfaces receive a 100/100 Quality Score.
2. **Precision Defect Detection**:
   - **Text Truncation & Ellipsis (`...` / `…`)**: Detects clipped labels cut short by rigid containers.
   - **Button & Container Text Overflow**: Detects text spilling outside button and input borders.
   - **Missing UI Components**: Detects omitted buttons, icons, or controls present in the baseline.
   - **Structural Layout Shifts**: Detects vertical/horizontal header and content dislocations ($\ge 20\text{px}$).
   - **Component Collisions & Sibling Overlaps**: Detects intersecting containers and buttons.
   - **Paragraph / Card Bleed**: Detects description text overflowing parent card containers.
3. **Interactive Visual Diff & Reporting**:
   - **Side-by-Side Comparison**: Synchronized visual inspection.
   - **Defects Highlighted**: Bounding box overlays with severity color codes (Critical, Major, Minor).
   - **Difference Heatmap**: Structural intensity difference overlay.
   - **1-Click PDF Report Export**: Clean downloadable audit report.

---

## 🛠️ Technology Stack

- **Frontend**: React 18, Tailwind CSS, Vite, Lucide Icons, jsPDF.
- **Backend**: Python 3.11+, FastAPI, Uvicorn, Pillow.
- **Image Processing**: Pure OpenCV (`cv2`), NumPy.

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.10+
- Node.js 18+

### 1. Start Backend
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

### 2. Start Frontend
```powershell
cd frontend
npm install
npm run dev
```

### 3. Open Application
- **Web App**: [http://localhost:3000](http://localhost:3000)
- **API Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📂 Project Structure

```
UI_Validator_POC/
├── backend/
│   ├── cv_engine.py           # Core OpenCV / NumPy detection pipeline
│   ├── dataset_generator.py   # Test scenario dataset generator
│   ├── main.py                # FastAPI REST API endpoints
│   ├── requirements.txt       # Python dependencies
│   └── sample_data/           # Sample baseline & localized screenshots
├── frontend/
│   ├── src/
│   │   ├── components/        # React components (Scorecard, DiffViewer, etc.)
│   │   ├── App.jsx            # Main application layout
│   │   └── index.css          # Tailwind CSS styles
│   ├── package.json           # Frontend dependencies
│   └── vite.config.js         # Vite configuration & API proxy
├── .gitignore
└── README.md
```

---

## 📄 License
MIT License.
