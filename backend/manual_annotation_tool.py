import os
import sys
import json
import base64
import pathlib
import io
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import pandas as pd
from PIL import Image

EXCEL_PATH = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize/Screenshot data list from Welocalize.xlsx')
BASE_DATA_ROOT = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize')
ANNOTATIONS_FILE = pathlib.Path(r'F:/POC__/backend/manual_defect_annotations.json')
PORT = 8050

def load_dataset():
    df = pd.read_excel(EXCEL_PATH, engine='openpyxl')
    cases = []
    case_idx = 0
    for _, row in df.iterrows():
        product = str(row['Product']).strip()
        folder = str(row['Screenshot Folder Name']).strip()
        lang = str(row['Language']).strip()
        gt_cat = str(row.get('Defect Catogery', row.get('Defect Category', 'Unknown'))).strip()
        
        target_dir = BASE_DATA_ROOT / product / folder
        en_files = list(target_dir.glob('(ENU)*.*'))
        loc_files = list(target_dir.glob(f'({lang})*.*'))
        
        if not en_files or not loc_files:
            continue
            
        case_idx += 1
        cases.append({
            "case_id": case_idx,
            "product": product,
            "folder": folder,
            "lang": lang,
            "gt_category": gt_cat,
            "en_path": str(en_files[0]),
            "loc_path": str(loc_files[0])
        })
    return cases

def load_annotations():
    if ANNOTATIONS_FILE.exists():
        try:
            with open(ANNOTATIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_annotations(data):
    with open(ANNOTATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def image_to_base64_url(img_path):
    try:
        with Image.open(img_path) as img:
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            b64_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
            w, h = img.size
            return f"data:image/png;base64,{b64_str}", w, h
    except Exception as e:
        return "", 0, 0

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Welocalize Manual Defect Annotator</title>
<style>
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    background: #0f172a;
    color: #f8fafc;
    margin: 0;
    padding: 16px 24px;
    height: 100vh;
    display: flex;
    flex-direction: column;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 12px;
    border-bottom: 1px solid #334155;
    flex-shrink: 0;
  }
  h1 { font-size: 18px; color: #38bdf8; margin: 0; }
  .badge {
    background: #1e293b;
    border: 1px solid #475569;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
  }
  .gt-badge {
    background: #831843;
    border-color: #f43f5e;
    color: #ffe4e6;
    font-weight: 600;
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 14px;
  }
  .progress-bar-container {
    width: 220px;
    background: #1e293b;
    height: 10px;
    border-radius: 5px;
    overflow: hidden;
    border: 1px solid #475569;
  }
  .progress-bar {
    background: #10b981;
    height: 100%;
    width: 0%;
    transition: width 0.2s;
  }
  .nav-controls {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  button {
    background: #2563eb;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 600;
    font-size: 13px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: background 0.15s;
  }
  button:hover { background: #1d4ed8; }
  button.secondary { background: #334155; }
  button.secondary:hover { background: #475569; }
  button.save-btn { background: #059669; }
  button.save-btn:hover { background: #047857; }
  button.clear-btn { background: #dc2626; }
  button.clear-btn:hover { background: #b91c1c; }
  button:disabled { opacity: 0.4; cursor: not-allowed; }

  main {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-top: 12px;
    min-height: 0;
  }
  .panel {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .panel-header {
    background: #0f172a;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: 600;
    color: #94a3b8;
    border-bottom: 1px solid #334155;
    display: flex;
    justify-content: space-between;
  }
  .viewport-container {
    flex: 1;
    overflow: auto;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding: 12px;
    background: #020617;
    position: relative;
    user-select: none;
  }
  .canvas-wrapper {
    position: relative;
    display: inline-block;
  }
  .canvas-wrapper img {
    display: block;
    max-width: none;
    pointer-events: none;
  }
  #annotationOverlay {
    position: absolute;
    top: 0;
    left: 0;
    cursor: crosshair;
  }
  .footer-status {
    margin-top: 10px;
    font-size: 12px;
    color: #94a3b8;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-shrink: 0;
  }
  .coords-info {
    color: #38bdf8;
    font-family: monospace;
    font-size: 13px;
  }
</style>
</head>
<body>

<header>
  <div>
    <h1>Welocalize Dataset Annotator — <span id="caseTitle" style="color:white;">Loading...</span></h1>
    <div style="display:flex; gap:10px; align-items:center; margin-top:4px;">
      <span class="badge" id="productLangBadge">-</span>
      <span>Ground Truth:</span>
      <span class="gt-badge" id="gtCategoryBadge">-</span>
    </div>
  </div>

  <div class="nav-controls">
    <div style="text-align:right;">
      <div style="font-size:12px; color:#94a3b8; margin-bottom:3px;">
        Annotated: <strong id="progressText" style="color:#10b981;">0</strong> / <span id="totalCasesText">114</span>
      </div>
      <div class="progress-bar-container">
        <div class="progress-bar" id="progressBar"></div>
      </div>
    </div>

    <button class="secondary" id="prevBtn" onclick="navigate(-1)">&larr; Prev</button>
    <select id="caseSelect" onchange="jumpToCase(this.value)" style="background:#1e293b; color:white; border:1px solid #475569; padding:8px 10px; border-radius:6px; font-size:13px;"></select>
    <button class="secondary" id="nextBtn" onclick="navigate(1)">Next &rarr;</button>
    <button class="clear-btn" onclick="clearBox()">Clear Box</button>
    <button class="save-btn" id="saveBtn" onclick="saveCurrentAnnotation()">&#10003; Save & Next</button>
  </div>
</header>

<main>
  <div class="panel">
    <div class="panel-header">
      <span>Baseline Screenshot (English ENU)</span>
      <span id="enuDims">-</span>
    </div>
    <div class="viewport-container" id="enuContainer">
      <div class="canvas-wrapper">
        <img id="enuImg" src="" alt="ENU Baseline" />
      </div>
    </div>
  </div>

  <div class="panel">
    <div class="panel-header">
      <span>Localized Screenshot (Draw defect bounding box here)</span>
      <span id="locDims">-</span>
    </div>
    <div class="viewport-container" id="locContainer">
      <div class="canvas-wrapper">
        <img id="locImg" src="" alt="Localized Image" onload="initOverlay()" />
        <canvas id="annotationOverlay"></canvas>
      </div>
    </div>
  </div>
</main>

<div class="footer-status">
  <div>
    Instructions: Click and drag on the <strong>Localized Screenshot</strong> to draw the defect box. Drag again to adjust. Click <strong>Save & Next</strong> or press <kbd>Enter</kbd>.
  </div>
  <div class="coords-info" id="coordsDisplay">Box: (none)</div>
</div>

<script>
let cases = [];
let annotations = {};
let currentIndex = 0;
let currentCase = null;

let isDrawing = false;
let startX = 0, startY = 0;
let currentBox = null; // { x, y, width, height }

async function init() {
  const res = await fetch('/api/init');
  const data = await res.json();
  cases = data.cases;
  annotations = data.annotations;

  const select = document.getElementById('caseSelect');
  select.innerHTML = '';
  cases.forEach((c, idx) => {
    const isDone = Boolean(annotations[c.case_id]);
    const opt = document.createElement('option');
    opt.value = idx;
    opt.textContent = `${isDone ? '✓ ' : ''}#${c.case_id}: ${c.product}/${c.folder} (${c.lang}) - ${c.gt_category}`;
    select.appendChild(opt);
  });

  document.getElementById('totalCasesText').textContent = cases.length;
  updateProgress();

  // Load first unannotated case if available
  const firstUnannotated = cases.findIndex(c => !annotations[c.case_id]);
  currentIndex = firstUnannotated !== -1 ? firstUnannotated : 0;
  loadCase(currentIndex);
}

function updateProgress() {
  const count = Object.keys(annotations).length;
  document.getElementById('progressText').textContent = count;
  const pct = (count / cases.length) * 100;
  document.getElementById('progressBar').style.width = pct + '%';

  // Update dropdown checkmarks
  const select = document.getElementById('caseSelect');
  Array.from(select.options).forEach((opt, idx) => {
    const c = cases[idx];
    const isDone = Boolean(annotations[c.case_id]);
    opt.textContent = `${isDone ? '✓ ' : ''}#${c.case_id}: ${c.product}/${c.folder} (${c.lang}) - ${c.gt_category}`;
  });
}

async function loadCase(index) {
  if (index < 0 || index >= cases.length) return;
  currentIndex = index;
  currentCase = cases[currentIndex];
  document.getElementById('caseSelect').value = currentIndex;

  document.getElementById('caseTitle').textContent = `#${currentCase.case_id}: ${currentCase.product} / ${currentCase.folder}`;
  document.getElementById('productLangBadge').textContent = `${currentCase.product} | ${currentCase.folder} | ${currentCase.lang}`;
  document.getElementById('gtCategoryBadge').textContent = currentCase.gt_category;

  document.getElementById('prevBtn').disabled = currentIndex === 0;
  document.getElementById('nextBtn').disabled = currentIndex === cases.length - 1;

  // Fetch images
  const res = await fetch(`/api/case?id=${currentCase.case_id}`);
  const data = await res.json();

  document.getElementById('enuImg').src = data.en_url;
  document.getElementById('locImg').src = data.loc_url;
  document.getElementById('enuDims').textContent = `${data.en_w} x ${data.en_h} px`;
  document.getElementById('locDims').textContent = `${data.loc_w} x ${data.loc_h} px`;

  // Existing annotation if present
  if (annotations[currentCase.case_id]) {
    const a = annotations[currentCase.case_id];
    currentBox = { x: a.x, y: a.y, width: a.width, height: a.height };
  } else {
    currentBox = null;
  }
  updateCoordsDisplay();
}

function initOverlay() {
  const locImg = document.getElementById('locImg');
  const canvas = document.getElementById('annotationOverlay');
  canvas.width = locImg.naturalWidth;
  canvas.height = locImg.naturalHeight;
  canvas.style.width = locImg.naturalWidth + 'px';
  canvas.style.height = locImg.naturalHeight + 'px';

  canvas.onmousedown = onMouseDown;
  canvas.onmousemove = onMouseMove;
  canvas.onmouseup = onMouseUp;
  redraw();
}

function onMouseDown(e) {
  const rect = e.target.getBoundingClientRect();
  startX = e.clientX - rect.left;
  startY = e.clientY - rect.top;
  isDrawing = true;
  currentBox = { x: Math.round(startX), y: Math.round(startY), width: 0, height: 0 };
  redraw();
}

function onMouseMove(e) {
  if (!isDrawing) return;
  const rect = e.target.getBoundingClientRect();
  const currentX = e.clientX - rect.left;
  const currentY = e.clientY - rect.top;

  const x = Math.min(startX, currentX);
  const y = Math.min(startY, currentY);
  const width = Math.abs(currentX - startX);
  const height = Math.abs(currentY - startY);

  currentBox = {
    x: Math.round(Math.max(0, x)),
    y: Math.round(Math.max(0, y)),
    width: Math.round(width),
    height: Math.round(height)
  };
  redraw();
  updateCoordsDisplay();
}

function onMouseUp(e) {
  if (!isDrawing) return;
  isDrawing = false;
  if (currentBox && (currentBox.width < 4 || currentBox.height < 4)) {
    currentBox = null;
  }
  redraw();
  updateCoordsDisplay();
}

function redraw() {
  const canvas = document.getElementById('annotationOverlay');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (currentBox) {
    // Fill mask
    ctx.fillStyle = 'rgba(244, 63, 94, 0.22)';
    ctx.fillRect(currentBox.x, currentBox.y, currentBox.width, currentBox.height);

    // Border
    ctx.strokeStyle = '#f43f5e';
    ctx.lineWidth = 2;
    ctx.setLineDash([4, 2]);
    ctx.strokeRect(currentBox.x, currentBox.y, currentBox.width, currentBox.height);
    ctx.setLineDash([]);

    // Header label
    ctx.fillStyle = '#f43f5e';
    const tag = ` [GT: ${currentCase ? currentCase.gt_category : ''}] ${currentBox.width}x${currentBox.height}px `;
    ctx.font = 'bold 12px sans-serif';
    const textW = ctx.measureText(tag).width;
    const tagY = Math.max(16, currentBox.y - 4);
    ctx.fillRect(currentBox.x, tagY - 14, textW + 6, 16);
    ctx.fillStyle = '#ffffff';
    ctx.fillText(tag, currentBox.x + 3, tagY - 2);
  }
}

function updateCoordsDisplay() {
  const el = document.getElementById('coordsDisplay');
  if (currentBox) {
    el.textContent = `Selected Defect Box: x=${currentBox.x}, y=${currentBox.y}, w=${currentBox.width}, h=${currentBox.height} (Area: ${currentBox.width*currentBox.height}px)`;
  } else {
    el.textContent = 'Selected Defect Box: (none)';
  }
}

function clearBox() {
  currentBox = null;
  redraw();
  updateCoordsDisplay();
}

async function saveCurrentAnnotation() {
  if (!currentBox) {
    alert('Please draw a bounding box around the defect region before saving.');
    return;
  }

  const payload = {
    case_id: currentCase.case_id,
    product: currentCase.product,
    folder: currentCase.folder,
    lang: currentCase.lang,
    gt_category: currentCase.gt_category,
    x: currentBox.x,
    y: currentBox.y,
    width: currentBox.width,
    height: currentBox.height
  };

  const res = await fetch('/api/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  const data = await res.json();
  if (data.status === 'ok') {
    annotations[currentCase.case_id] = payload;
    updateProgress();
    if (currentIndex < cases.length - 1) {
      loadCase(currentIndex + 1);
    } else {
      alert('You have reached the final case in the dataset!');
    }
  }
}

function navigate(delta) {
  const nextIdx = currentIndex + delta;
  if (nextIdx >= 0 && nextIdx < cases.length) {
    loadCase(nextIdx);
  }
}

function jumpToCase(idx) {
  loadCase(parseInt(idx));
}

window.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    saveCurrentAnnotation();
  } else if (e.key === 'ArrowRight' && e.altKey) {
    navigate(1);
  } else if (e.key === 'ArrowLeft' && e.altKey) {
    navigate(-1);
  } else if (e.key === 'Escape') {
    clearBox();
  }
});

window.onload = init;
</script>

</body>
</html>
"""

class AnnotationHandler(BaseHTTPRequestHandler):
    cases = []

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in ['/', '/index.html']:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
            return

        elif path == '/api/init':
            annos = load_annotations()
            case_summaries = [{
                "case_id": c["case_id"],
                "product": c["product"],
                "folder": c["folder"],
                "lang": c["lang"],
                "gt_category": c["gt_category"]
            } for c in AnnotationHandler.cases]
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"cases": case_summaries, "annotations": annos}).encode('utf-8'))
            return

        elif path == '/api/case':
            case_id = int(query.get('id', [1])[0])
            c = next((item for item in AnnotationHandler.cases if item["case_id"] == case_id), None)
            if not c:
                self.send_response(404)
                self.end_headers()
                return

            en_url, en_w, en_h = image_to_base64_url(c["en_path"])
            loc_url, loc_w, loc_h = image_to_base64_url(c["loc_path"])

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "case_id": c["case_id"],
                "product": c["product"],
                "folder": c["folder"],
                "lang": c["lang"],
                "gt_category": c["gt_category"],
                "en_url": en_url,
                "loc_url": loc_url,
                "en_w": en_w,
                "en_h": en_h,
                "loc_w": loc_w,
                "loc_h": loc_h
            }).encode('utf-8'))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path == '/api/save':
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            payload = json.loads(body.decode('utf-8'))

            case_id = str(payload['case_id'])
            annos = load_annotations()
            annos[case_id] = payload
            save_annotations(annos)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "total_saved": len(annos)}).encode('utf-8'))
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        # Silence routine request logging in terminal
        pass

def main():
    print(f"Loading Welocalize benchmark dataset...", flush=True)
    cases = load_dataset()
    AnnotationHandler.cases = cases
    annos = load_annotations()
    
    print(f"Loaded {len(cases)} test cases. Current saved annotations: {len(annos)}/{len(cases)}", flush=True)
    print(f"\n=======================================================", flush=True)
    print(f" MANUAL DEFECT ANNOTATION TOOL READY", flush=True)
    print(f" URL: http://localhost:{PORT}", flush=True)
    print(f" File: {ANNOTATIONS_FILE.resolve()}", flush=True)
    print(f"=======================================================\n", flush=True)
    print(f"Open http://localhost:{PORT} in your web browser to start annotating.", flush=True)
    
    server = HTTPServer(('0.0.0.0', PORT), AnnotationHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAnnotation server stopped.")

if __name__ == '__main__':
    main()
