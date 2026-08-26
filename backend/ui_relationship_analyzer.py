import os
import sys
import json
import time
import pathlib
import io
import base64
import numpy as np
import pandas as pd
import cv2
from PIL import Image

EXCEL_PATH = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize/Screenshot data list from Welocalize.xlsx')
BASE_DATA_ROOT = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize')
OUTPUT_JSON = pathlib.Path('backend/ui_relationship_poc.json')
OUTPUT_HTML = pathlib.Path('backend/ui_relationship_poc.html')

# Exactly 10 representative benchmark cases: 5 Misalignment + 5 Overlapping
SELECTED_CASE_IDS = [
    # 5 Misalignment cases across Civil3d, Inventor, Vault (RUS, FRA, ESP, JPN, HUN)
    9,   # Civil3d / Civil3d-01 (RUS) - Misalignment
    10,  # Civil3d / Civil3d-12 (FRA) - Misalignment
    11,  # Civil3d / Civil3d-13 (ESP) - Misalignment
    15,  # Inventor / Inventor-01 (JPN) - Misalignment
    22,  # Vault / Vault-28 (HUN) - Misalignment

    # 5 Overlapping cases across Civil3d, Inventor, Vault (RUS, CSY, PTB, ITA, FRA)
    30,  # Civil3d / Civil3d-06 (RUS) - Overlapping
    31,  # Civil3d / Civil3d-18 (CSY) - Overlapping
    32,  # Civil3d / Civil3d-28 (PTB) - Overlapping
    37,  # Inventor / Inventor-33 (ITA) - Overlapping
    44   # Vault / Vault-14 (FRA) - Overlapping
]

_ocr_reader = None
def get_ocr():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    return _ocr_reader

def extract_ocr_blocks(img_bgr):
    reader = get_ocr()
    h, w = img_bgr.shape[:2]
    scale = 1.0
    if max(h, w) > 1000:
        scale = 1000.0 / max(h, w)
        proc = cv2.resize(img_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        proc = img_bgr

    try:
        results = reader.readtext(proc, paragraph=False, batch_size=4)
    except Exception:
        return []

    inv = 1.0 / scale
    blocks = []
    for bbox, text, conf in results:
        if conf < 0.20 or not text.strip():
            continue
        xs = [p[0] * inv for p in bbox]
        ys = [p[1] * inv for p in bbox]
        x, y = int(min(xs)), int(min(ys))
        bw, bh = int(max(xs) - x), int(max(ys) - y)
        blocks.append({
            "box": (x, y, bw, bh),
            "text": text.strip(),
            "conf": float(conf)
        })
    return blocks

def detect_containers(img_bgr):
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 30, 100)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    cnts, _ = cv2.findContours(closed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    containers = []
    for c in cnts:
        x, y, bw, bh = cv2.boundingRect(c)
        if bw < 20 or bh < 18 or (bw >= w - 10 and bh >= h - 10):
            continue
        aspect = bw / float(bh)
        ctype = "container"
        if 22 <= bh <= 65 and 40 <= bw <= 350 and 1.1 <= aspect <= 9.0:
            ctype = "button"
        elif 20 <= bh <= 65 and 100 <= bw <= 450:
            ctype = "dropdown"
        elif 28 <= bh <= 85 and 120 <= bw <= w * 0.95 and aspect > 2.0:
            ctype = "input"
        elif bh > 80 and bw > 150 and bw * bh > 12000:
            ctype = "card"
        containers.append({"box": (x, y, bw, bh), "type": ctype})
        
    # Deduplicate
    unique = []
    for b in sorted(containers, key=lambda c: (c["box"][1], c["box"][0])):
        bx = b["box"]
        if not any(abs(u["box"][0] - bx[0]) < 10 and abs(u["box"][1] - bx[1]) < 10 and abs(u["box"][2] - bx[2]) < 10 for u in unique):
            unique.append(b)
    return unique

def extract_all_elements(img_bgr, prefix="E"):
    """Extracts all UI and text elements with spatial geometry and container hierarchy."""
    ocr_blocks = extract_ocr_blocks(img_bgr)
    containers = detect_containers(img_bgr)
    
    elements = []
    elem_id = 1
    
    # 1. Add OCR text elements
    for ob in ocr_blocks:
        x, y, w, h = ob["box"]
        cx, cy = x + w / 2.0, y + h / 2.0
        
        # Check parent container
        parent_id = None
        for c in containers:
            cx_c, cy_c, cw_c, ch_c = c["box"]
            if cx_c - 4 <= x and (x + w) <= cx_c + cw_c + 4 and cy_c - 4 <= y and (y + h) <= cy_c + ch_c + 4:
                parent_id = f"{prefix}_C{containers.index(c)+1}"
                break
                
        elements.append({
            "id": f"{prefix}{elem_id}",
            "type": "text",
            "text": ob["text"],
            "ocr_conf": round(ob["conf"], 3),
            "x": int(x),
            "y": int(y),
            "width": int(w),
            "height": int(h),
            "center": [round(cx, 1), round(cy, 1)],
            "parent": parent_id
        })
        elem_id += 1
        
    # 2. Add containers that do not perfectly overlap text
    for i, c in enumerate(containers):
        x, y, w, h = c["box"]
        cx, cy = x + w / 2.0, y + h / 2.0
        # Check if container is just a duplicate of an existing text element
        is_dup = any(abs(e["x"] - x) < 8 and abs(e["y"] - y) < 8 and abs(e["width"] - w) < 15 for e in elements)
        if not is_dup:
            elements.append({
                "id": f"{prefix}_C{i+1}",
                "type": c["type"],
                "text": "",
                "ocr_conf": None,
                "x": int(x),
                "y": int(y),
                "width": int(w),
                "height": int(h),
                "center": [round(cx, 1), round(cy, 1)],
                "parent": None
            })
            
    return elements

def calc_iou(box1, box2):
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    xi1, yi1 = max(x1, x2), max(y1, y2)
    xi2, yi2 = min(x1 + w1, x2 + w2), min(y1 + h1, y2 + h2)
    inter_w, inter_h = max(0, xi2 - xi1), max(0, yi2 - yi1)
    inter_area = inter_w * inter_h
    union_area = (w1 * h1) + (w2 * h2) - inter_area
    return (inter_area / union_area) if union_area > 0 else 0.0

def match_elements(enu_elements, loc_elements, img_w, img_h):
    """
    Matches ENU elements -> Localized elements using multi-signal evidence:
    - Relative spatial distance (normalized by screen width/height)
    - Vertical alignment consistency (same row/column)
    - Bounding-box aspect ratio and size similarity
    - Element type matching
    - Neighboring context similarity
    """
    matches = []
    unmatched_enu = set(e["id"] for e in enu_elements)
    unmatched_loc = set(e["id"] for e in loc_elements)
    
    # Pre-calculate candidate similarity scores
    pairs = []
    for e in enu_elements:
        for l in loc_elements:
            # 1. Type compatibility
            type_score = 1.0 if e["type"] == l["type"] else 0.4
            
            # 2. Normalized spatial distance
            dist_x = abs(e["center"][0] - l["center"][0]) / float(img_w)
            dist_y = abs(e["center"][1] - l["center"][1]) / float(img_h)
            pos_score = max(0.0, 1.0 - (dist_x * 1.5 + dist_y * 3.0)) # Vertical distance matters more for rows
            
            # 3. Size similarity
            w_ratio = min(e["width"], l["width"]) / max(1.0, max(e["width"], l["width"]))
            h_ratio = min(e["height"], l["height"]) / max(1.0, max(e["height"], l["height"]))
            size_score = (w_ratio * 0.4 + h_ratio * 0.6)
            
            # 4. Same row bonus
            row_bonus = 0.15 if abs(e["y"] - l["y"]) < 18 else 0.0
            
            # Composite match confidence
            match_score = (pos_score * 0.55 + size_score * 0.30 + type_score * 0.15) + row_bonus
            match_score = min(1.0, match_score)
            
            # Evidence explanation
            evidence = {
                "distance_px": round(np.hypot(e["center"][0] - l["center"][0], e["center"][1] - l["center"][1]), 1),
                "vertical_offset_px": int(l["y"] - e["y"]),
                "horizontal_offset_px": int(l["x"] - e["x"]),
                "width_ratio": round(w_ratio, 2),
                "height_ratio": round(h_ratio, 2),
                "same_element_type": bool(e["type"] == l["type"])
            }
            
            if match_score >= 0.45:
                pairs.append((match_score, e, l, evidence))
                
    # Greedy bipartite assignment
    pairs.sort(key=lambda p: p[0], reverse=True)
    
    assigned_enu = set()
    assigned_loc = set()
    
    for score, e, l, evidence in pairs:
        if e["id"] in assigned_enu or l["id"] in assigned_loc:
            continue
        assigned_enu.add(e["id"])
        assigned_loc.add(l["id"])
        
        matches.append({
            "enu_id": e["id"],
            "loc_id": l["id"],
            "match_confidence": round(score, 3),
            "evidence": evidence,
            "enu_element": e,
            "loc_element": l
        })
        
    unmatched_enu = [e for e in enu_elements if e["id"] not in assigned_enu]
    unmatched_loc = [l for l in loc_elements if l["id"] not in assigned_loc]
    return matches, unmatched_enu, unmatched_loc

def compute_spatial_relationship_changes(matches, enu_elements, loc_elements):
    """
    Computes exact physical relationship deltas for each matched element:
    - dx, dy
    - width delta, height delta
    - nearest neighbor distance change before and after
    - sibling overlap/collision deltas
    """
    enu_by_id = {e["id"]: e for e in enu_elements}
    loc_by_id = {l["id"]: l for l in loc_elements}
    
    results = []
    for m in matches:
        e = m["enu_element"]
        l = m["loc_element"]
        
        dx = l["x"] - e["x"]
        dy = l["y"] - e["y"]
        dw = l["width"] - e["width"]
        dh = l["height"] - e["height"]
        
        # 1. Nearest neighbor in ENU vs Localized
        def get_nearest(elem, pool):
            others = [o for o in pool if o["id"] != elem["id"]]
            if not others: return None, 0.0
            dists = [np.hypot(elem["center"][0] - o["center"][0], elem["center"][1] - o["center"][1]) for o in others]
            min_idx = int(np.argmin(dists))
            return others[min_idx]["id"], round(dists[min_idx], 1)
            
        enu_nn_id, enu_nn_dist = get_nearest(e, enu_elements)
        loc_nn_id, loc_nn_dist = get_nearest(l, loc_elements)
        nn_dist_delta = round(loc_nn_dist - enu_nn_dist, 1)
        
        # 2. Overlap / Collisions before vs after
        def count_overlaps(elem, pool):
            box1 = (elem["x"], elem["y"], elem["width"], elem["height"])
            overlaps = []
            for o in pool:
                if o["id"] == elem["id"]: continue
                box2 = (o["x"], o["y"], o["width"], o["height"])
                iou = calc_iou(box1, box2)
                # Check bounding box collision
                xi1, yi1 = max(box1[0], box2[0]), max(box1[1], box2[1])
                xi2, yi2 = min(box1[0] + box1[2], box2[0] + box2[2]), min(box1[1] + box1[3], box2[1] + box2[3])
                if xi1 < xi2 and yi1 < yi2:
                    overlaps.append({"target_id": o["id"], "overlap_px_w": xi2 - xi1, "overlap_px_h": yi2 - yi1})
            return overlaps
            
        enu_overlaps = count_overlaps(e, enu_elements)
        loc_overlaps = count_overlaps(l, loc_elements)
        
        results.append({
            "enu_id": e["id"],
            "loc_id": l["id"],
            "enu_text": e["text"],
            "loc_text": l["text"],
            "match_confidence": m["match_confidence"],
            "match_evidence": m["evidence"],
            "spatial_changes": {
                "dx": dx,
                "dy": dy,
                "dw": dw,
                "dh": dh,
                "relative_movement_magnitude": round(float(np.hypot(dx, dy)), 1),
                "nearest_neighbor_enu": {"id": enu_nn_id, "dist_px": enu_nn_dist},
                "nearest_neighbor_loc": {"id": loc_nn_id, "dist_px": loc_nn_dist},
                "nearest_neighbor_dist_delta": nn_dist_delta,
                "enu_overlaps": enu_overlaps,
                "loc_overlaps": loc_overlaps,
                "newly_created_overlap": bool(len(loc_overlaps) > len(enu_overlaps))
            }
        })
        
    # Sort by largest spatial relationship change
    results.sort(key=lambda r: (r["spatial_changes"]["relative_movement_magnitude"] + abs(r["spatial_changes"]["dw"])), reverse=True)
    return results

def draw_element_overlays(img_bgr, elements, matches, is_localized=False):
    """Draws element bounding boxes and ID badges on the screenshot."""
    canvas = img_bgr.copy()
    matched_ids = {m["loc_id"] if is_localized else m["enu_id"]: m for m in matches}
    
    for el in elements:
        x, y, w, h = el["x"], el["y"], el["width"], el["height"]
        eid = el["id"]
        is_matched = eid in matched_ids
        
        color = (0, 200, 80) if is_matched else (0, 80, 220) # Green for matched, Orange/Red for unmatched
        cv2.rectangle(canvas, (x, y), (x + w, y + h), color, 2)
        
        # Tag ID
        tag = eid
        if is_matched:
            m = matched_ids[eid]
            other_id = m["enu_id"] if is_localized else m["loc_id"]
            tag = f"{eid} <-> {other_id}"
            
        (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        tag_y = max(16, y)
        cv2.rectangle(canvas, (x, tag_y - th - 4), (x + tw + 4, tag_y), color, -1)
        cv2.putText(canvas, tag, (x + 2, tag_y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        
    return canvas

def img_to_b64(img_bgr):
    _, buf = cv2.imencode('.png', img_bgr)
    return f"data:image/png;base64,{base64.b64encode(buf).decode('utf-8')}"

def generate_poc_html_report(all_cases_data, output_path):
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>UI Relationship Analyzer — 10 Case Proof-of-Concept</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }
  h1 { color: #38bdf8; font-size: 24px; margin-bottom: 6px; }
  .summary-bar { background: #1e293b; padding: 16px 20px; border-radius: 8px; margin-bottom: 24px; border: 1px solid #334155; display: flex; gap: 32px; font-size: 15px; }
  .case-card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; margin-bottom: 32px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); }
  .case-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 12px; margin-bottom: 16px; }
  .case-title { font-size: 18px; font-weight: 600; color: #f1f5f9; }
  .badge { background: #0f172a; border: 1px solid #475569; padding: 4px 10px; border-radius: 6px; font-size: 13px; }
  .gt-badge { background: #831843; border: 1px solid #f43f5e; color: #ffe4e6; font-weight: 600; padding: 4px 12px; border-radius: 6px; }
  .image-comparison { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
  .img-col { text-align: center; }
  .img-col span { display: block; font-size: 12px; color: #94a3b8; margin-bottom: 6px; font-weight: 600; }
  .img-col img { max-width: 100%; border: 1px solid #475569; border-radius: 6px; background: #020617; }
  table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
  th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid #334155; }
  th { background: #0f172a; color: #38bdf8; font-weight: 600; }
  tr:hover { background: #243247; }
  .tag-match { color: #4ade80; font-family: monospace; font-weight: bold; }
  .tag-shift { color: #facc15; font-family: monospace; }
  .tag-overlap { color: #f43f5e; font-weight: bold; }
</style>
</head>
<body>
<h1>UI Relationship Analyzer — 10 Case Proof-of-Concept Report</h1>
<div style="font-size:14px; color:#94a3b8; margin-bottom:16px;">
  Demonstration of UI element correspondence matching and spatial relationship delta calculation across 5 Misalignment and 5 Overlapping benchmark pairs.
</div>
"""
    for c in all_cases_data:
        stats = c["stats"]
        html += f"""
<div class="case-card">
  <div class="case-header">
    <div>
      <span class="case-title">Case #{c['case_id']}: {c['product']} / {c['folder']} ({c['lang']})</span>
      <span class="gt-badge" style="margin-left: 12px;">GT Category: {c['gt_category']}</span>
    </div>
    <div style="display: flex; gap: 16px; font-size: 13px;">
      <span class="badge">ENU Elements: <strong>{stats['total_enu']}</strong></span>
      <span class="badge">Localized Elements: <strong>{stats['total_loc']}</strong></span>
      <span class="badge" style="border-color: #10b981; color: #4ade80;">Matched: <strong>{stats['matched_count']} ({stats['match_rate_pct']}%)</strong></span>
      <span class="badge">Avg Conf: <strong>{stats['avg_match_confidence']}</strong></span>
    </div>
  </div>

  <div class="image-comparison">
    <div class="img-col">
      <span>Baseline (ENU) with Overlaid Element IDs</span>
      <img src="{c['enu_overlay_b64']}" alt="ENU" />
    </div>
    <div class="img-col">
      <span>Localized with Matched Corresponding IDs</span>
      <img src="{c['loc_overlay_b64']}" alt="Localized" />
    </div>
  </div>

  <h3 style="font-size: 14px; color: #38bdf8; margin: 12px 0 6px 0;">Top Spatial Relationship Changes (Sorted by Movement & Dimension Deltas):</h3>
  <table>
    <thead>
      <tr>
        <th>ENU ID &harr; Loc ID</th>
        <th>ENU Text</th>
        <th>Localized Text</th>
        <th>Match Conf</th>
        <th>Movement (&Delta;X, &Delta;Y)</th>
        <th>Size Delta (&Delta;W, &Delta;H)</th>
        <th>NN Distance Delta</th>
        <th>Overlap / Collision Status</th>
      </tr>
    </thead>
    <tbody>
"""
        for r in c["relationships"][:8]: # Show top 8 largest changes
            sc = r["spatial_changes"]
            overlap_str = "<span class='tag-overlap'>New Overlap Collision!</span>" if sc["newly_created_overlap"] else "<span style='color:#94a3b8;'>Clean</span>"
            html += f"""
      <tr>
        <td class="tag-match">{r['enu_id']} &harr; {r['loc_id']}</td>
        <td>{r['enu_text'] if r['enu_text'] else '<em>(container)</em>'}</td>
        <td>{r['loc_text'] if r['loc_text'] else '<em>(container)</em>'}</td>
        <td>{r['match_confidence']}</td>
        <td class="tag-shift">&Delta;X: {sc['dx']:+d}px, &Delta;Y: {sc['dy']:+d}px (&Delta;mag={sc['relative_movement_magnitude']}px)</td>
        <td>&Delta;W: {sc['dw']:+d}px, &Delta;H: {sc['dh']:+d}px</td>
        <td>{sc['nearest_neighbor_dist_delta']:+0.1f}px</td>
        <td>{overlap_str}</td>
      </tr>
"""
        html += """
    </tbody>
  </table>
</div>
"""

    html += """
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

def main():
    df = pd.read_excel(EXCEL_PATH, engine='openpyxl')
    print(f"Loaded Excel dataset. Filtering for the 10 selected proof-of-concept cases...", flush=True)
    
    all_cases = []
    case_idx = 0
    for idx, row in df.iterrows():
        product = str(row['Product']).strip()
        folder = str(row['Screenshot Folder Name']).strip()
        lang = str(row['Language']).strip()
        gt_cat = str(row.get('Defect Catogery', row.get('Defect Category', 'Unknown'))).strip()
        
        target_dir = BASE_DATA_ROOT / product / folder
        en_files = list(target_dir.glob('(ENU)*.*'))
        loc_files = list(target_dir.glob(f'({lang})*.*'))
        if not en_files or not loc_files: continue
        
        case_idx += 1
        if case_idx in SELECTED_CASE_IDS:
            all_cases.append({
                "case_id": case_idx,
                "product": product,
                "folder": folder,
                "lang": lang,
                "gt_category": gt_cat,
                "en_path": str(en_files[0]),
                "loc_path": str(loc_files[0])
            })
            
    print(f"Selected {len(all_cases)} cases (5 Misalignment + 5 Overlapping). Running relationship analyzer...", flush=True)
    
    results = []
    total_enu_all = 0
    total_loc_all = 0
    total_matched_all = 0
    
    for i, c in enumerate(all_cases):
        t0 = time.time()
        img_en = cv2.imread(c["en_path"])
        img_loc = cv2.imread(c["loc_path"])
        
        # Standardize size for matching
        h_en, w_en = img_en.shape[:2]
        h_loc, w_loc = img_loc.shape[:2]
        target_w, target_h = max(w_en, w_loc), max(h_en, h_loc)
        if (w_en, h_en) != (target_w, target_h):
            img_en = cv2.resize(img_en, (target_w, target_h), interpolation=cv2.INTER_AREA)
        if (w_loc, h_loc) != (target_w, target_h):
            img_loc = cv2.resize(img_loc, (target_w, target_h), interpolation=cv2.INTER_AREA)
            
        # 1. Extract elements
        enu_elements = extract_all_elements(img_en, prefix="E")
        loc_elements = extract_all_elements(img_loc, prefix="L")
        
        # 2. Match elements
        matches, unmatched_enu, unmatched_loc = match_elements(enu_elements, loc_elements, target_w, target_h)
        
        # 3. Compute spatial relationship deltas
        relationships = compute_spatial_relationship_changes(matches, enu_elements, loc_elements)
        
        # 4. Generate overlays
        enu_overlay = draw_element_overlays(img_en, enu_elements, matches, is_localized=False)
        loc_overlay = draw_element_overlays(img_loc, loc_elements, matches, is_localized=True)
        
        avg_conf = round(float(np.mean([m["match_confidence"] for m in matches])) if matches else 0.0, 3)
        match_rate = round(len(matches) / max(1, min(len(enu_elements), len(loc_elements))) * 100, 1)
        
        stats = {
            "total_enu": len(enu_elements),
            "total_loc": len(loc_elements),
            "matched_count": len(matches),
            "unmatched_enu_count": len(unmatched_enu),
            "unmatched_loc_count": len(unmatched_loc),
            "match_rate_pct": match_rate,
            "avg_match_confidence": avg_conf
        }
        
        total_enu_all += len(enu_elements)
        total_loc_all += len(loc_elements)
        total_matched_all += len(matches)
        
        print(f"[{i+1}/10] Case #{c['case_id']}: {c['product']}/{c['folder']} ({c['lang']} - {c['gt_category']}) in {time.time()-t0:.1f}s | ENU: {len(enu_elements)}, Loc: {len(loc_elements)} -> Matched: {len(matches)} (Avg Conf: {avg_conf})", flush=True)
        
        results.append({
            "case_id": c["case_id"],
            "product": c["product"],
            "folder": c["folder"],
            "lang": c["lang"],
            "gt_category": c["gt_category"],
            "stats": stats,
            "enu_elements": enu_elements,
            "loc_elements": loc_elements,
            "relationships": relationships,
            "unmatched_enu_ids": [e["id"] for e in unmatched_enu],
            "unmatched_loc_ids": [l["id"] for l in unmatched_loc],
            "enu_overlay_b64": img_to_b64(enu_overlay),
            "loc_overlay_b64": img_to_b64(loc_overlay)
        })
        
    # Save JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        # Strip heavy base64 strings from JSON for compact persistence
        json_clean = []
        for r in results:
            copy_r = dict(r)
            del copy_r["enu_overlay_b64"]
            del copy_r["loc_overlay_b64"]
            json_clean.append(copy_r)
        json.dump(json_clean, f, indent=2)
    print(f"\nSaved relationship data to {OUTPUT_JSON.resolve()}", flush=True)
    
    # Save HTML report
    generate_poc_html_report(results, OUTPUT_HTML)
    print(f"Saved visual HTML report to {OUTPUT_HTML.resolve()}", flush=True)

if __name__ == '__main__':
    main()
