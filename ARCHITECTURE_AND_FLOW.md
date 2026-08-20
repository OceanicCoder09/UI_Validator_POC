# Localization UI Quality Checker — Architecture, Technology & Workflow Guide

A complete, easy-to-understand explanation of how the system works, what technologies are used, and the step-by-step data flow.

---

## 1. High-Level Summary (What is this and why was it made?)

When software or websites are translated from **English** to other languages like **German**, **Spanish**, or **Japanese**:
- German words are often **20% to 40% longer**.
- If a button or card has a fixed width in code, the longer translated text can **burst outside the button**, get **cut off with `...`**, or **push other elements out of place**.

**This tool automates UI visual testing**:
It takes the **English original screenshot** and the **Translated screenshot**, compares their layout, and reports any visual defects while allowing normal translation text growth.

---

## 2. Technologies Used & Why

| Technology | What it is | What it does in this project | How it works |
|---|---|---|---|
| **Python 3** | Backend Programming Language | Runs the core logic, image analysis, and API server. | Executes fast numerical operations and image algorithms. |
| **OpenCV (`cv2`)** | Computer Vision Library | Analyzes images, detects UI buttons, text boxes, and checks boundaries. | Converts images into pixel arrays, finds shapes (contours), detects text ellipses (`...`), and calculates pixel differences. |
| **NumPy** | Numerical Matrix Library | Fast image math and array calculations. | Computes difference masks, average pixel shifts, and component coordinate overlaps. |
| **FastAPI** | Python Web Framework | Provides REST API endpoints between frontend and backend. | Accepts image uploads or URLs via HTTP POST, runs the OpenCV analysis, and returns clean JSON results. |
| **Playwright** | Browser Automation Tool | Takes automated screenshots of live websites. | Launches a background (headless) Chromium browser, opens the two URLs, waits for them to load, and captures pixel-perfect screenshots. |
| **React (Vite)** | Frontend Web UI Framework | Builds the interactive dashboard for the user. | Renders the preset buttons, uploader tabs, scorecard, visual diff viewer, and findings list. |
| **Tailwind CSS** | Styling Framework | Modern visual design and layout. | Provides clean cards, badges, colors, and responsive grid layouts. |
| **jsPDF & html2canvas** | PDF Generation Libraries | Generates downloadable audit reports. | Captures the results on screen and converts them into a clean 1-click downloadable PDF. |

---

## 3. Complete Step-by-Step Flow

```
[ USER INPUT ]
   │
   ├── Option A: 1-Click Demo Preset
   ├── Option B: Upload 2 Screenshots (English + Localized)
   └── Option C: Enter 2 Live Web URLs (Auto-Capture)
   │
   ▼
[ 1. CAPTURE & PREPARE ]
   - If URLs: Playwright opens headless Chromium & captures screenshots.
   - Images are decoded into OpenCV format (Height x Width x Color).
   │
   ▼
[ 2. ZERO-NOISE CHECK ]
   - If identical images are uploaded, immediately return Score: 100/100 (0 errors).
   │
   ▼
[ 3. FIVE CORE QUALITY CHECKS ]
   1. Button Text Overflow (checks if text spilled past button borders).
   2. Text Truncation (detects trailing '...' ellipsis dots).
   3. Missing Components (detects buttons/icons present in English but missing in Localized).
   4. Overlap & Collision (detects sibling elements crashing into each other).
   5. Layout Shift (detects if headers or containers moved by >= 20px).
   │
   ▼
[ 4. SCORING & VISUAL RENDERING ]
   - Calculates Score (0 to 100) and Grade (A+ to F).
   - Generates 3 visual images: Baseline, Localized with Red Highlight Boxes, and Jet Heatmap.
   │
   ▼
[ 5. DISPLAY TO USER ]
   - React Dashboard displays Scorecard, Visual Diff Viewer, Findings list, and PDF Export button.
```

---

## 4. How Each Quality Check Works (in Plain English)

### 1. Button Text Overflow Check
- **The Problem**: A button designed for the English word *"Submit"* is too small for the German translation *"Fall übermitteln"*. The text spills outside the button background.
- **How OpenCV Detects It**: The engine detects the rectangular container border of the button. Then it inspects the region just outside the right border ($+3\text{px}$ to $+30\text{px}$). If text pixels are found outside the button edge, it flags an **Overflow Defect**.

---

### 2. Text Truncation & Ellipsis (`...`) Check
- **The Problem**: When text is too long, the software cuts off the sentence and adds three dots (`...`).
- **How OpenCV Detects It**: The engine scans text line baselines for 3 consecutive small, evenly spaced circular dot contours with matching horizontal alignments. If found, it flags a **Truncation Defect**.

---

### 3. Missing Component Check
- **The Problem**: A translator or template bug accidentally dropped a button (e.g. *"Attach File"* is completely missing in Spanish).
- **How OpenCV Detects It**: The engine finds all interactive action buttons in the English image. It then checks if a corresponding button exists in the same relative area of the localized image. If missing, it flags a **Missing Component Defect**.

---

### 4. Layout Shift Check
- **The Problem**: The top header bar or a form section is pushed down or displaced.
- **How OpenCV Detects It**: The engine compares the vertical starting coordinate ($y$) of primary structural containers. If an element shifted by $\ge 20\text{px}$, it flags a **Layout Shift Defect**.

---

### 5. Smart Tolerance (Accepting Normal Translations)
- **Why this is important**: A normal translation will always change text pixels (e.g. *"Help"* $\rightarrow$ *"Hilfe"*).
- **How OpenCV Handles It**: The engine does **not** complain about pixel text changes if the container grew cleanly and no borders were broken. It only complains when layout rules are violated.

---

## 5. Scoring Formula

$$\text{Final Score} = 100 - (\text{Critical Defects} \times 25) - (\text{Major Defects} \times 15) - (\text{Minor Defects} \times 5)$$

- **Grade A+ / A** ($88 - 100$): Clean UI / Exceptional Quality.
- **Grade B** ($70 - 87$): Acceptable with minor observations.
- **Grade C** ($55 - 69$): Warning — Noticeable layout shift or text truncation.
- **Grade D / F** ($< 55$): Severe failure — Missing buttons or broken UI.
