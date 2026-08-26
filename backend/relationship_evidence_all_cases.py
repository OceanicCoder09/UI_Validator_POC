import os
import sys
import json
import time
import pathlib
import re
import collections
import numpy as np
import pandas as pd
import cv2
from PIL import Image

EXCEL_PATH = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize/Screenshot data list from Welocalize.xlsx')
BASE_DATA_ROOT = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize')
OUTPUT_JSON = pathlib.Path('backend/relationship_evidence_all_cases.json')
OUTPUT_HTML = pathlib.Path('backend/relationship_evidence_analysis.html')

TARGET_CLASSES = [
    "Misalignment",
    "Overlapping",
    "Truncation",
    "Untranslation",
    "Repeated hotkey"
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
        
    unique = []
    for b in sorted(containers, key=lambda c: (c["box"][1], c["box"][0])):
        bx = b["box"]
        if not any(abs(u["box"][0] - bx[0]) < 10 and abs(u["box"][1] - bx[1]) < 10 and abs(u["box"][2] - bx[2]) < 10 for u in unique):
            unique.append(b)
    return unique

def extract_all_elements(img_bgr, prefix="E"):
    ocr_blocks = extract_ocr_blocks(img_bgr)
    containers = detect_containers(img_bgr)
    elements = []
    elem_id = 1
    
    for ob in ocr_blocks:
        x, y, w, h = ob["box"]
        cx, cy = x + w / 2.0, y + h / 2.0
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
        
    for i, c in enumerate(containers):
        x, y, w, h = c["box"]
        cx, cy = x + w / 2.0, y + h / 2.0
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
    pairs = []
    for e in enu_elements:
        for l in loc_elements:
            type_score = 1.0 if e["type"] == l["type"] else 0.4
            dist_x = abs(e["center"][0] - l["center"][0]) / float(img_w)
            dist_y = abs(e["center"][1] - l["center"][1]) / float(img_h)
            pos_score = max(0.0, 1.0 - (dist_x * 1.5 + dist_y * 3.0))
            w_ratio = min(e["width"], l["width"]) / max(1.0, max(e["width"], l["width"]))
            h_ratio = min(e["height"], l["height"]) / max(1.0, max(e["height"], l["height"]))
            size_score = (w_ratio * 0.4 + h_ratio * 0.6)
            row_bonus = 0.15 if abs(e["y"] - l["y"]) < 18 else 0.0
            match_score = min(1.0, (pos_score * 0.55 + size_score * 0.30 + type_score * 0.15) + row_bonus)
            if match_score >= 0.45:
                pairs.append((match_score, e, l))
                
    pairs.sort(key=lambda p: p[0], reverse=True)
    assigned_enu, assigned_loc, matches = set(), set(), []
    for score, e, l in pairs:
        if e["id"] in assigned_enu or l["id"] in assigned_loc:
            continue
        assigned_enu.add(e["id"])
        assigned_loc.add(l["id"])
        matches.append({
            "enu_id": e["id"],
            "loc_id": l["id"],
            "match_confidence": round(score, 3),
            "enu_element": e,
            "loc_element": l
        })
    unmatched_enu = [e for e in enu_elements if e["id"] not in assigned_enu]
    unmatched_loc = [l for l in loc_elements if l["id"] not in assigned_loc]
    return matches, unmatched_enu, unmatched_loc

def calc_box_gap_and_alignment(box1, box2):
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    if x1 + w1 <= x2: h_gap = x2 - (x1 + w1)
    elif x2 + w2 <= x1: h_gap = x1 - (x2 + w2)
    else: h_gap = -(min(x1 + w1, x2 + w2) - max(x1, x2))
    
    if y1 + h1 <= y2: v_gap = y2 - (y1 + h1)
    elif y2 + h2 <= y1: v_gap = y1 - (y2 + h2)
    else: v_gap = -(min(y1 + h1, y2 + h2) - max(y1, y2))
    
    inter_w = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
    inter_h = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
    return {
        "h_gap": int(h_gap),
        "v_gap": int(v_gap),
        "left_align_delta": int(abs(x1 - x2)),
        "intersection_area": int(inter_w * inter_h)
    }

def analyze_case_evidence(c, img_en, img_loc):
    h_en, w_en = img_en.shape[:2]
    h_loc, w_loc = img_loc.shape[:2]
    target_w, target_h = max(w_en, w_loc), max(h_en, h_loc)
    if (w_en, h_en) != (target_w, target_h): img_en = cv2.resize(img_en, (target_w, target_h), interpolation=cv2.INTER_AREA)
    if (w_loc, h_loc) != (target_w, target_h): img_loc = cv2.resize(img_loc, (target_w, target_h), interpolation=cv2.INTER_AREA)
    
    enu_elements = extract_all_elements(img_en, prefix="E")
    loc_elements = extract_all_elements(img_loc, prefix="L")
    matches, unmatched_enu, unmatched_loc = match_elements(enu_elements, loc_elements, target_w, target_h)
    
    all_dx = [m["loc_element"]["x"] - m["enu_element"]["x"] for m in matches]
    all_dy = [m["loc_element"]["y"] - m["enu_element"]["y"] for m in matches]
    median_dx = float(np.median(all_dx)) if all_dx else 0.0
    median_dy = float(np.median(all_dy)) if all_dy else 0.0
    
    # Text expansions & Ellipsis
    text_expansions = []
    has_ellipsis_count = 0
    untrans_word_count = 0
    hotkey_matches = []
    
    for m in matches:
        e = m["enu_element"]
        l = m["loc_element"]
        if e["type"] == "text" and l["type"] == "text":
            w_exp = l["width"] - e["width"]
            text_expansions.append(w_exp)
            if bool(re.search(r'(\.{2,4}|…|\.\s\.\s\.)$', l["text"].strip())):
                has_ellipsis_count += 1
            # Check untranslation: pure latin text matching ENU
            if l["text"].strip().lower() == e["text"].strip().lower() and len(e["text"].strip()) >= 4 and not e["text"].strip().isdigit():
                untrans_word_count += 1
            # Hotkey accelerator
            hk_m = re.findall(r'[\(\[\{（]\s*(?:&|_)?([A-Za-z0-9])\s*[\)\]\}）]|(?:&([A-Za-z0-9]))', l["text"])
            for h in hk_m:
                hotkey_matches.append(next(x for x in h if x).upper())

    # Check duplicate hotkey mnemonics
    hotkey_counts = collections.Counter(hotkey_matches)
    hotkey_conflicts = sum(cnt - 1 for k, cnt in hotkey_counts.items() if cnt > 1)

    # Relationship analysis across matched pairs
    displacements = []
    gap_collapses = []
    new_intersections = []
    align_divergences = []
    
    for i in range(len(matches)):
        m1 = matches[i]
        e1, l1 = m1["enu_element"], m1["loc_element"]
        dx1, dy1 = l1["x"] - e1["x"], l1["y"] - e1["y"]
        indep_disp = np.hypot(dx1 - median_dx, dy1 - median_dy)
        displacements.append(float(indep_disp))
        
        for j in range(i + 1, len(matches)):
            m2 = matches[j]
            e2, l2 = m2["enu_element"], m2["loc_element"]
            dist_e = np.hypot(e1["center"][0] - e2["center"][0], e1["center"][1] - e2["center"][1])
            if dist_e > 180: continue
            
            box_e1 = (e1["x"], e1["y"], e1["width"], e1["height"])
            box_e2 = (e2["x"], e2["y"], e2["width"], e2["height"])
            box_l1 = (l1["x"], l1["y"], l1["width"], l1["height"])
            box_l2 = (l2["x"], l2["y"], l2["width"], l2["height"])
            
            rel_before = calc_box_gap_and_alignment(box_e1, box_e2)
            rel_after = calc_box_gap_and_alignment(box_l1, box_l2)
            
            # Gap collapse
            if rel_before["h_gap"] > 0:
                collapse = rel_before["h_gap"] - rel_after["h_gap"]
                if collapse > 0: gap_collapses.append(collapse)
                
            # Newly created intersection area
            if rel_before["intersection_area"] == 0 and rel_after["intersection_area"] > 0:
                new_intersections.append(rel_after["intersection_area"])
                
            # Alignment divergence
            if rel_before["left_align_delta"] <= 4:
                align_div = rel_after["left_align_delta"] - rel_before["left_align_delta"]
                if align_div > 0: align_divergences.append(align_div)

    num_indep_displaced = sum(1 for d in displacements if d >= 12.0)
    max_disp = float(max(displacements, default=0.0))
    median_disp = float(np.median(displacements)) if displacements else 0.0
    max_gap_collapse = int(max(gap_collapses, default=0))
    num_new_intersections = len(new_intersections)
    total_intersection_area = int(sum(new_intersections))
    max_text_expansion = int(max(text_expansions, default=0))
    max_align_divergence = int(max(align_divergences, default=0))
    
    avg_conf = float(np.mean([m["match_confidence"] for m in matches])) if matches else 0.0
    match_rate = float(len(matches) / max(1, min(len(enu_elements), len(loc_elements))) * 100)
    
    return {
        "case_id": c["case_id"],
        "product": c["product"],
        "folder": c["folder"],
        "lang": c["lang"],
        "gt_category": c["gt_category"],
        "matching_stats": {
            "total_enu": len(enu_elements),
            "total_loc": len(loc_elements),
            "matched_count": len(matches),
            "unmatched_enu": len(unmatched_enu),
            "unmatched_loc": len(unmatched_loc),
            "match_rate_pct": round(match_rate, 1),
            "avg_confidence": round(avg_conf, 3)
        },
        "evidence_features": {
            "max_displacement_px": round(max_disp, 1),
            "median_displacement_px": round(median_disp, 1),
            "num_independently_displaced": num_indep_displaced,
            "max_alignment_divergence_px": max_align_divergence,
            "max_gap_collapse_px": max_gap_collapse,
            "num_newly_created_intersections": num_new_intersections,
            "total_intersection_area_px2": total_intersection_area,
            "max_text_expansion_px": max_text_expansion,
            "has_ellipsis_count": has_ellipsis_count,
            "untranslated_words_count": untrans_word_count,
            "hotkey_conflict_count": hotkey_conflicts
        }
    }

def compute_distribution(vals):
    if not vals:
        return {"min": 0, "p25": 0, "median": 0, "mean": 0, "p75": 0, "p90": 0, "max": 0}
    arr = np.array(vals, dtype=float)
    return {
        "min": round(float(np.min(arr)), 1),
        "median": round(float(np.median(arr)), 1),
        "mean": round(float(np.mean(arr)), 1),
        "p75": round(float(np.percentile(arr, 75)), 1),
        "p90": round(float(np.percentile(arr, 90)), 1),
        "max": round(float(np.max(arr)), 1)
    }

def generate_html_report(category_stats, all_cases, output_path):
    features = list(all_cases[0]["evidence_features"].keys())
    
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Relationship Evidence Analysis — 101 Benchmark Cases</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }
  h1 { color: #38bdf8; font-size: 24px; margin-bottom: 6px; }
  h2 { color: #93c5fd; font-size: 18px; margin-top: 28px; border-bottom: 1px solid #334155; padding-bottom: 6px; }
  .summary-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 24px; }
  .cat-card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 14px; text-align: center; }
  .cat-title { font-size: 15px; font-weight: 600; color: #38bdf8; }
  .cat-count { font-size: 22px; font-weight: bold; margin-top: 4px; color: #f8fafc; }
  table { width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 13px; background: #1e293b; border-radius: 6px; overflow: hidden; }
  th, td { padding: 8px 12px; text-align: right; border-bottom: 1px solid #334155; }
  th:first-child, td:first-child { text-align: left; }
  th { background: #0f172a; color: #38bdf8; font-weight: 600; }
  tr:hover { background: #243247; }
  .highlight-high { color: #f43f5e; font-weight: bold; }
  .highlight-med { color: #facc15; font-weight: bold; }
  .highlight-clean { color: #4ade80; }
</style>
</head>
<body>
<h1>Relationship Evidence Analysis — 101 Cases Across 5 Core GT Categories</h1>
<div style="font-size:14px; color:#94a3b8; margin-bottom:20px;">
  Analysis of physical element displacement, gap collapse, bounding-box intersection, text expansion, and OCR signals.
</div>

<div class="summary-grid">
"""
    for cat in TARGET_CLASSES:
        count = len([c for c in all_cases if c["gt_category"] == cat])
        html += f"""
  <div class="cat-card">
    <div class="cat-title">{cat}</div>
    <div class="cat-count">{count} cases</div>
  </div>
"""
    html += """</div>

<h2>1. Feature Distributions Grouped by Ground Truth Category</h2>
"""
    for feat in features:
        html += f"""
<h3 style="font-size:15px; color:#38bdf8; margin-top:20px;">Feature: <code>{feat}</code></h3>
<table>
  <thead>
    <tr>
      <th>GT Category</th>
      <th>Cases</th>
      <th>Min</th>
      <th>Median</th>
      <th>Mean</th>
      <th>75th %ile</th>
      <th>90th %ile</th>
      <th>Max</th>
    </tr>
  </thead>
  <tbody>
"""
        for cat in TARGET_CLASSES:
            cases_cat = [c for c in all_cases if c["gt_category"] == cat]
            vals = [c["evidence_features"][feat] for c in cases_cat]
            dist = compute_distribution(vals)
            html += f"""
    <tr>
      <td style="font-weight:600; color:#f1f5f9;">{cat}</td>
      <td>{len(cases_cat)}</td>
      <td>{dist['min']}</td>
      <td class="highlight-med">{dist['median']}</td>
      <td>{dist['mean']}</td>
      <td>{dist['p75']}</td>
      <td>{dist['p90']}</td>
      <td class="highlight-high">{dist['max']}</td>
    </tr>
"""
        html += """
  </tbody>
</table>
"""

    # Pairwise comparison tables
    html += """
<h2>2. Pairwise Feature Comparisons (Median Values)</h2>
<table>
  <thead>
    <tr>
      <th>Evidence Feature</th>
      <th>Misalignment (N=19)</th>
      <th>Overlapping (N=19)</th>
      <th>Truncation (N=30)</th>
      <th>Untranslation (N=26)</th>
      <th>Repeated Hotkey (N=7)</th>
    </tr>
  </thead>
  <tbody>
"""
    for feat in features:
        html += f"""
    <tr>
      <td style="font-weight:600; text-align:left;"><code>{feat}</code></td>
"""
        for cat in TARGET_CLASSES:
            cases_cat = [c for c in all_cases if c["gt_category"] == cat]
            vals = [c["evidence_features"][feat] for c in cases_cat]
            dist = compute_distribution(vals)
            html += f"""<td>{dist['median']} (mean: {dist['mean']})</td>"""
        html += """</tr>"""
        
    html += """
  </tbody>
</table>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

def main():
    df = pd.read_excel(EXCEL_PATH, engine='openpyxl')
    print("Loading 101 benchmark cases across the 5 core categories...", flush=True)
    
    cases = []
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
        if gt_cat in TARGET_CLASSES:
            cases.append({
                "case_id": case_idx,
                "product": product,
                "folder": folder,
                "lang": lang,
                "gt_category": gt_cat,
                "en_path": str(en_files[0]),
                "loc_path": str(loc_files[0])
            })
            
    print(f"Filtered {len(cases)} benchmark cases. Starting relationship evidence extraction...", flush=True)
    
    all_results = []
    t_start = time.time()
    
    for i, c in enumerate(cases):
        t0 = time.time()
        img_en = cv2.imread(c["en_path"])
        img_loc = cv2.imread(c["loc_path"])
        
        res = analyze_case_evidence(c, img_en, img_loc)
        all_results.append(res)
        
        ms = res["matching_stats"]
        ef = res["evidence_features"]
        if (i + 1) % 10 == 0 or (i + 1) == len(cases):
            print(f"[{i+1:3d}/{len(cases)}] Case #{c['case_id']:3d}: {c['product']}/{c['folder']} ({c['lang']} - {c['gt_category']}) in {time.time()-t0:.1f}s | MatchRate: {ms['match_rate_pct']}% | MaxDisp: {ef['max_displacement_px']}px, CollapsedGap: {ef['max_gap_collapse_px']}px, InterArea: {ef['total_intersection_area_px2']}px2", flush=True)
            
    print(f"\n=======================================================", flush=True)
    print(f"EVIDENCE EXTRACTION COMPLETE IN {time.time() - t_start:.1f}s", flush=True)
    print(f"Total Cases Processed: {len(all_results)}", flush=True)
    
    # Save JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"Saved complete relationship evidence data to {OUTPUT_JSON.resolve()}", flush=True)
    
    # Generate HTML report
    generate_html_report(None, all_results, OUTPUT_HTML)
    print(f"Saved visual HTML report to {OUTPUT_HTML.resolve()}", flush=True)

if __name__ == '__main__':
    main()
