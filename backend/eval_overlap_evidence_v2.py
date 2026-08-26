import os
import sys
import json
import time
import pathlib
import re
import collections
import pandas as pd
import numpy as np
import cv2

WORKSPACE_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from backend.relationship_evidence_all_cases import extract_all_elements, match_elements

EXCEL_PATH = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize/Screenshot data list from Welocalize.xlsx')
BASE_DATA_ROOT = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize')

OUTPUT_EVIDENCE_JSON = pathlib.Path('backend/overlap_evidence_v2.json')
OUTPUT_EVIDENCE_HTML = pathlib.Path('backend/overlap_evidence_v2.html')
OUTPUT_DISCRIM_JSON = pathlib.Path('backend/overlap_discrimination_analysis.json')
OUTPUT_DISCRIM_HTML = pathlib.Path('backend/overlap_discrimination_analysis.html')

TARGET_CLASSES = [
    "Misalignment",
    "Overlapping",
    "Repeated hotkey",
    "Truncation",
    "Untranslation"
]

def load_benchmark_cases():
    df = pd.read_excel(EXCEL_PATH, engine='openpyxl')
    records = []
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
            records.append({
                "case_id": case_idx,
                "product": product,
                "folder": folder,
                "lang": lang,
                "gt_category": gt_cat,
                "en_path": str(en_files[0]),
                "loc_path": str(loc_files[0])
            })
    return records

def calc_detailed_geometric_intersection(box1, box2):
    """
    Computes exact geometric intrusion, gaps, and overlap area between two bounding boxes.
    """
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    
    # Horizontal gap or intrusion
    if x1 + w1 <= x2:
        h_gap = x2 - (x1 + w1)
        h_intrusion = 0
    elif x2 + w2 <= x1:
        h_gap = x1 - (x2 + w2)
        h_intrusion = 0
    else:
        h_intrusion = min(x1 + w1, x2 + w2) - max(x1, x2)
        h_gap = -h_intrusion

    # Vertical gap or intrusion
    if y1 + h1 <= y2:
        v_gap = y2 - (y1 + h1)
        v_intrusion = 0
    elif y2 + h2 <= y1:
        v_gap = y1 - (y2 + h2)
        v_intrusion = 0
    else:
        v_intrusion = min(y1 + h1, y2 + h2) - max(y1, y2)
        v_gap = -v_intrusion

    inter_w = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
    inter_h = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
    inter_area = int(inter_w * inter_h)
    
    return {
        "h_gap": int(h_gap),
        "v_gap": int(v_gap),
        "h_intrusion": int(h_intrusion),
        "v_intrusion": int(v_intrusion),
        "intersection_area": int(inter_area)
    }

def classify_element_pair_type(e1, e2):
    t1, t2 = e1.get("type", "unknown"), e2.get("type", "unknown")
    pair = sorted([t1, t2])
    if pair == ["text", "text"]: return "text <-> text"
    elif pair in [["button", "text"], ["dropdown", "text"], ["input", "text"]]: return "text <-> control"
    elif "card" in pair or "container" in pair: return "text <-> container"
    elif pair in [["button", "button"], ["button", "input"], ["dropdown", "input"]]: return "control <-> control"
    else: return "text <-> icon/raster element"

def evaluate_all_overlap_evidence(records):
    print(f"Evaluating physical overlap evidence across {len(records)} benchmark cases...", flush=True)
    all_case_evaluations = []
    
    t0 = time.time()
    
    for i, r in enumerate(records):
        img_en = cv2.imread(r["en_path"])
        img_loc = cv2.imread(r["loc_path"])
        
        h_en, w_en = img_en.shape[:2]
        h_loc, w_loc = img_loc.shape[:2]
        target_w, target_h = max(w_en, w_loc), max(h_en, h_loc)
        if (w_en, h_en) != (target_w, target_h): img_en = cv2.resize(img_en, (target_w, target_h), interpolation=cv2.INTER_AREA)
        if (w_loc, h_loc) != (target_w, target_h): img_loc = cv2.resize(img_loc, (target_w, target_h), interpolation=cv2.INTER_AREA)
        
        enu_elements = extract_all_elements(img_en, prefix="E")
        loc_elements = extract_all_elements(img_loc, prefix="L")
        matches, unmatched_enu, unmatched_loc = match_elements(enu_elements, loc_elements, target_w, target_h)
        
        # Calculate global shift
        all_dx = [m["loc_element"]["x"] - m["enu_element"]["x"] for m in matches]
        all_dy = [m["loc_element"]["y"] - m["enu_element"]["y"] for m in matches]
        global_shift_x = float(np.median(all_dx)) if all_dx else 0.0
        global_shift_y = float(np.median(all_dy)) if all_dy else 0.0
        
        # Track text and container width expansions
        text_expansions = []
        container_expansions = []
        for m in matches:
            e, l = m["enu_element"], m["loc_element"]
            w_exp = l["width"] - e["width"]
            if e["type"] == "text":
                text_expansions.append(w_exp)
            else:
                container_expansions.append(w_exp)
                
        max_text_expansion = max(text_expansions, default=0)
        max_container_expansion = max(container_expansions, default=0)
        
        # Pairwise geometric relationship analysis across matched elements & siblings
        all_intersections_before = []
        all_intersections_after = []
        newly_created_intersections = []
        gap_collapses = []
        gaps_became_zero_or_negative = 0
        collision_types = collections.defaultdict(int)
        
        detailed_collision_pairs = []
        
        for idx1 in range(len(matches)):
            m1 = matches[idx1]
            e1, l1 = m1["enu_element"], m1["loc_element"]
            
            for idx2 in range(idx1 + 1, len(matches)):
                m2 = matches[idx2]
                e2, l2 = m2["enu_element"], m2["loc_element"]
                
                # Check spatial neighborhood in ENU (< 220px)
                dist_e = np.hypot(e1["center"][0] - e2["center"][0], e1["center"][1] - e2["center"][1])
                if dist_e > 220: continue
                
                box_e1 = (e1["x"], e1["y"], e1["width"], e1["height"])
                box_e2 = (e2["x"], e2["y"], e2["width"], e2["height"])
                box_l1 = (l1["x"], l1["y"], l1["width"], l1["height"])
                box_l2 = (l2["x"], l2["y"], l2["width"], l2["height"])
                
                rel_before = calc_detailed_geometric_intersection(box_e1, box_e2)
                rel_after = calc_detailed_geometric_intersection(box_l1, box_l2)
                
                area_before = rel_before["intersection_area"]
                area_after = rel_after["intersection_area"]
                
                all_intersections_before.append(area_before)
                all_intersections_after.append(area_after)
                
                # Gap collapse evaluation
                if rel_before["h_gap"] > 0:
                    collapse = rel_before["h_gap"] - rel_after["h_gap"]
                    if collapse > 0:
                        gap_collapses.append(collapse)
                    if rel_after["h_gap"] <= 0:
                        gaps_became_zero_or_negative += 1
                        
                # Newly created geometric intersection (non-colliding in ENU -> colliding in LOC)
                is_new_collision = (area_before == 0 and area_after > 0)
                if is_new_collision:
                    newly_created_intersections.append(area_after)
                    c_type = classify_element_pair_type(e1, e2)
                    collision_types[c_type] += 1
                    
                    # Reflow explanation: Is the collision caused by upstream text/container expansion?
                    # Determine left vs right element
                    left_e, right_e = (e1, e2) if e1["x"] <= e2["x"] else (e2, e1)
                    left_l, right_l = (l1, l2) if e1["x"] <= e2["x"] else (l2, l1)
                    
                    left_w_exp = max(0, left_l["width"] - left_e["width"])
                    h_intrusion = rel_after["h_intrusion"]
                    
                    # If left expansion pushed its right edge into right box -> Reflow-induced
                    explained_by_reflow = bool(left_w_exp >= h_intrusion * 0.8)
                    
                    detailed_collision_pairs.append({
                        "element_1": {"id": e1["id"], "type": e1["type"], "text": e1.get("text", "")[:30], "loc_box": box_l1},
                        "element_2": {"id": e2["id"], "type": e2["type"], "text": e2.get("text", "")[:30], "loc_box": box_l2},
                        "collision_type": c_type,
                        "intersection_area_px2": area_after,
                        "h_intrusion_px": rel_after["h_intrusion"],
                        "v_intrusion_px": rel_after["v_intrusion"],
                        "before_h_gap_px": rel_before["h_gap"],
                        "after_h_gap_px": rel_after["h_gap"],
                        "explained_by_reflow": explained_by_reflow,
                        "provenance": "DIRECTLY_MEASURED"
                    })

        num_new_intersections = len(newly_created_intersections)
        max_intersection_area = max(newly_created_intersections, default=0)
        total_intersection_area = sum(newly_created_intersections)
        max_h_intrusion = max([p["h_intrusion_px"] for p in detailed_collision_pairs], default=0)
        max_v_intrusion = max([p["v_intrusion_px"] for p in detailed_collision_pairs], default=0)
        max_gap_collapse = max(gap_collapses, default=0)
        
        # Residual collision after reflow explanation
        unexplained_collisions = [p for p in detailed_collision_pairs if not p["explained_by_reflow"]]
        has_residual_collision = len(unexplained_collisions) > 0
        residual_collision_count = len(unexplained_collisions)
        max_residual_area = max([p["intersection_area_px2"] for p in unexplained_collisions], default=0)
        
        has_genuine_intersection = (num_new_intersections > 0)
        has_genuine_gap_collapse = (max_gap_collapse >= 8)
        
        case_data = {
            "case_id": r["case_id"],
            "product": r["product"],
            "folder": r["folder"],
            "lang": r["lang"],
            "gt_category": r["gt_category"],
            "matched_elements_count": len(matches),
            "num_newly_created_intersections": num_new_intersections,
            "max_intersection_area_px2": max_intersection_area,
            "total_intersection_area_px2": total_intersection_area,
            "max_horizontal_intrusion_px": max_h_intrusion,
            "max_vertical_intrusion_px": max_v_intrusion,
            "max_gap_collapse_px": max_gap_collapse,
            "num_gaps_became_non_positive": gaps_became_zero_or_negative,
            "max_text_expansion_px": max_text_expansion,
            "max_container_expansion_px": max_container_expansion,
            "collision_type_breakdown": dict(collision_types),
            "reflow_explained_collisions_count": len(detailed_collision_pairs) - residual_collision_count,
            "residual_unexplained_collisions_count": residual_collision_count,
            "max_residual_collision_area_px2": max_residual_area,
            "has_genuine_new_intersection": has_genuine_intersection,
            "has_genuine_gap_collapse": has_genuine_gap_collapse,
            "detailed_collisions": detailed_collision_pairs[:10],
            "provenance": {
                "intersection_measurements": "DIRECTLY_MEASURED",
                "gap_measurements": "DIRECTLY_MEASURED",
                "intrusion_measurements": "DIRECTLY_MEASURED",
                "reflow_correlation": "DERIVED_FROM_MEASUREMENT"
            }
        }
        
        all_case_evaluations.append(case_data)
        if (i + 1) % 25 == 0 or (i + 1) == len(records):
            print(f"  Audited {i+1}/{len(records)} cases in {time.time()-t0:.1f}s", flush=True)

    return all_case_evaluations

def run_overlap_discrimination_analysis(all_cases):
    overlap_cases = [c for c in all_cases if c["gt_category"] == "Overlapping"]
    non_overlap_cases = [c for c in all_cases if c["gt_category"] != "Overlapping"]
    misalign_cases = [c for c in all_cases if c["gt_category"] == "Misalignment"]
    trunc_cases = [c for c in all_cases if c["gt_category"] == "Truncation"]
    untrans_cases = [c for c in all_cases if c["gt_category"] == "Untranslation"]
    hotkey_cases = [c for c in all_cases if c["gt_category"] == "Repeated hotkey"]
    
    # Q_A: Overlapping cases with genuine newly created intersections
    ov_with_new_inter = sum(1 for c in overlap_cases if c["num_newly_created_intersections"] > 0)
    # Q_B: Non-overlapping cases with intersections
    non_ov_with_new_inter = sum(1 for c in non_overlap_cases if c["num_newly_created_intersections"] > 0)
    # Q_C: Overlapping cases with sibling gap collapse
    ov_with_gap_collapse = sum(1 for c in overlap_cases if c["max_gap_collapse_px"] >= 8)
    # Q_D: Gap collapse occurring without actual collision
    gap_collapse_no_collision_ov = sum(1 for c in overlap_cases if c["max_gap_collapse_px"] >= 8 and c["num_newly_created_intersections"] == 0)
    gap_collapse_no_collision_all = sum(1 for c in all_cases if c["max_gap_collapse_px"] >= 8 and c["num_newly_created_intersections"] == 0)
    
    # Q_E: Collisions fully explained by normal text/container expansion
    cases_with_any_collision = [c for c in all_cases if c["num_newly_created_intersections"] > 0]
    collisions_fully_reflow_explained = sum(1 for c in cases_with_any_collision if c["residual_unexplained_collisions_count"] == 0)
    
    # Category level distribution statistics
    features_to_compare = [
        "num_newly_created_intersections",
        "max_intersection_area_px2",
        "total_intersection_area_px2",
        "max_horizontal_intrusion_px",
        "max_vertical_intrusion_px",
        "max_gap_collapse_px",
        "num_gaps_became_non_positive",
        "residual_unexplained_collisions_count",
        "max_residual_collision_area_px2"
    ]
    
    categories = {
        "Overlapping": overlap_cases,
        "Misalignment": misalign_cases,
        "Truncation": trunc_cases,
        "Untranslation": untrans_cases,
        "Repeated hotkey": hotkey_cases
    }
    
    category_summary = {}
    for cat_name, items in categories.items():
        stats = {"count": len(items)}
        for f in features_to_compare:
            vals = [it[f] for it in items]
            stats[f] = {
                "mean": round(float(np.mean(vals)), 2),
                "std": round(float(np.std(vals)), 2),
                "median": round(float(np.median(vals)), 2),
                "q25": round(float(np.percentile(vals, 25)), 2),
                "q75": round(float(np.percentile(vals, 75)), 2),
                "min": round(float(np.min(vals)), 2),
                "max": round(float(np.max(vals)), 2)
            }
        category_summary[cat_name] = stats

    # Fisher separation: Overlapping vs Non-Overlapping, Overlapping vs Misalignment, Overlapping vs Truncation
    def calc_fisher(c1_items, c2_items, feat):
        v1 = [x[feat] for x in c1_items]
        v2 = [x[feat] for x in c2_items]
        m1, var1 = np.mean(v1), np.var(v1)
        m2, var2 = np.mean(v2), np.var(v2)
        return float(((m1 - m2) ** 2) / (var1 + var2 + 1e-7))

    disc_vs_all = []
    disc_vs_mis = []
    disc_vs_trunc = []
    
    for f in features_to_compare:
        r_all = calc_fisher(overlap_cases, non_overlap_cases, f)
        r_mis = calc_fisher(overlap_cases, misalign_cases, f)
        r_trunc = calc_fisher(overlap_cases, trunc_cases, f)
        
        disc_vs_all.append({
            "feature": f,
            "overlapping_mean": category_summary["Overlapping"][f]["mean"],
            "non_overlapping_mean": round(float(np.mean([x[f] for x in non_overlap_cases])), 2),
            "separation_ratio": round(r_all, 4)
        })
        disc_vs_mis.append({
            "feature": f,
            "overlapping_mean": category_summary["Overlapping"][f]["mean"],
            "misalignment_mean": category_summary["Misalignment"][f]["mean"],
            "separation_ratio": round(r_mis, 4)
        })
        disc_vs_trunc.append({
            "feature": f,
            "overlapping_mean": category_summary["Overlapping"][f]["mean"],
            "truncation_mean": category_summary["Truncation"][f]["mean"],
            "separation_ratio": round(r_trunc, 4)
        })
        
    disc_vs_all.sort(key=lambda x: x["separation_ratio"], reverse=True)
    disc_vs_mis.sort(key=lambda x: x["separation_ratio"], reverse=True)
    disc_vs_trunc.sort(key=lambda x: x["separation_ratio"], reverse=True)

    # Exemplars: True Overlapping Cases vs False-Positive Collision Cases
    true_overlap_exemplars = sorted(
        [c for c in overlap_cases if c["max_intersection_area_px2"] >= 50 and c["max_horizontal_intrusion_px"] >= 8],
        key=lambda x: x["total_intersection_area_px2"],
        reverse=True
    )[:5]
    
    false_pos_exemplars = sorted(
        [c for c in non_overlap_cases if c["num_newly_created_intersections"] > 0],
        key=lambda x: x["total_intersection_area_px2"],
        reverse=True
    )[:5]

    discrimination_results = {
        "total_benchmark_cases": len(all_cases),
        "overlapping_cases_count": len(overlap_cases),
        "non_overlapping_cases_count": len(non_overlap_cases),
        "questions_answered": {
            "Q_A_overlapping_with_genuine_new_intersections": f"{ov_with_new_inter} / {len(overlap_cases)} ({ov_with_new_inter/len(overlap_cases)*100:.1f}%)",
            "Q_B_non_overlapping_with_intersections": f"{non_ov_with_new_inter} / {len(non_overlap_cases)} ({non_ov_with_new_inter/len(non_overlap_cases)*100:.1f}%)",
            "Q_C_overlapping_with_gap_collapse": f"{ov_with_gap_collapse} / {len(overlap_cases)} ({ov_with_gap_collapse/len(overlap_cases)*100:.1f}%)",
            "Q_D_gap_collapse_without_actual_collision": {
                "in_overlapping_category": f"{gap_collapse_no_collision_ov} / {len(overlap_cases)}",
                "across_all_benchmark_cases": f"{gap_collapse_no_collision_all} / {len(all_cases)}"
            },
            "Q_E_collisions_fully_reflow_explained": f"{collisions_fully_reflow_explained} / {len(cases_with_any_collision)} ({collisions_fully_reflow_explained/max(1, len(cases_with_any_collision))*100:.1f}%)"
        },
        "discrimination_rankings": {
            "vs_all_non_overlapping": disc_vs_all,
            "vs_misalignment": disc_vs_mis,
            "vs_truncation": disc_vs_trunc
        },
        "category_summary_distributions": category_summary,
        "true_overlapping_exemplars": true_overlap_exemplars,
        "false_positive_collision_exemplars": false_pos_exemplars
    }
    
    return discrimination_results

def generate_html_reports(eval_data, discrim_data):
    # 1. Generate overlap_evidence_v2.html
    html_ev = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Overlapping Physical Evidence Report v2</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
  h1 {{ color: #38bdf8; font-size: 24px; margin-bottom: 6px; }}
  h2 {{ color: #93c5fd; font-size: 18px; margin-top: 28px; border-bottom: 1px solid #334155; padding-bottom: 6px; }}
  .metrics-banner {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 20px 0; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; text-align: center; }}
  .card-val {{ font-size: 24px; font-weight: bold; margin-top: 4px; color: #38bdf8; }}
  .card-sub {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; background: #0f172a; border-radius: 6px; overflow: hidden; }}
  th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid #334155; }}
  th {{ background: #020617; color: #38bdf8; font-weight: 600; }}
  tr:hover {{ background: #1e293b; }}
  .case-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; margin-bottom: 24px; padding: 18px; }}
  .case-header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 10px; margin-bottom: 12px; }}
  .gt-badge {{ background: #831843; border: 1px solid #f43f5e; color: #ffe4e6; font-weight: 600; padding: 4px 10px; border-radius: 6px; font-size: 13px; }}
  .status-pass {{ background: #064e3b; border: 1px solid #10b981; color: #a7f3d0; font-weight: 600; padding: 4px 10px; border-radius: 6px; font-size: 13px; }}
  .status-fail {{ background: #334155; color: #94a3b8; font-weight: 600; padding: 4px 10px; border-radius: 6px; font-size: 13px; }}
</style>
</head>
<body>
<h1>Overlapping Physical Evidence Report (v2)</h1>
<div style="color: #94a3b8; font-size: 14px;">
  Direct geometric intersection area, horizontal intrusion, and sibling gap collapse measurements across all 19 Overlapping benchmark cases.
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Total Overlapping Cases</div>
    <div class="card-val" style="color: #f8fafc;">19</div>
    <div class="card-sub">ground truth benchmark cases</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Cases with New Geometric Collision</div>
    <div class="card-val" style="color: #4ade80;">{discrim_data['questions_answered']['Q_A_overlapping_with_genuine_new_intersections']}</div>
    <div class="card-sub">measured non-zero intersection area</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Cases with Sibling Gap Collapse</div>
    <div class="card-val" style="color: #38bdf8;">{discrim_data['questions_answered']['Q_C_overlapping_with_gap_collapse']}</div>
    <div class="card-sub">gutter spacing collapsed &ge; 8px</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Mean Max Intersection Area</div>
    <div class="card-val" style="color: #f59e0b;">{discrim_data['category_summary_distributions']['Overlapping']['max_intersection_area_px2']['mean']:.0f} px&sup2;</div>
    <div class="card-sub">median: {discrim_data['category_summary_distributions']['Overlapping']['max_intersection_area_px2']['median']:.0f} px&sup2;</div>
  </div>
</div>

<h2>Case-by-Case Physical Collision Audit (19 Overlapping Cases)</h2>
"""
    overlap_only = [c for c in eval_data if c["gt_category"] == "Overlapping"]
    for c in overlap_only:
        status_badge = "<span class='status-pass'>[PASS] Genuine Collision Detected</span>" if c["has_genuine_new_intersection"] else "<span class='status-fail'>[NO COLLISION]</span>"
        
        col_rows = ""
        for p in c["detailed_collisions"]:
            reflow_tag = "<span style='color:#38bdf8;'>Yes (Reflow)</span>" if p["explained_by_reflow"] else "<span style='color:#f43f5e; font-weight:bold;'>No (Residual)</span>"
            col_rows += f"""
      <tr>
        <td><code>{p['element_1']['type']}</code> ('{p['element_1']['text']}')</td>
        <td><code>{p['element_2']['type']}</code> ('{p['element_2']['text']}')</td>
        <td>{p['collision_type']}</td>
        <td style="font-weight:bold; color:#4ade80;">{p['intersection_area_px2']} px&sup2;</td>
        <td>{p['h_intrusion_px']} px</td>
        <td>{p['before_h_gap_px']} px &rarr; {p['after_h_gap_px']} px</td>
        <td>{reflow_tag}</td>
      </tr>
"""
        html_ev += f"""
<div class="case-card">
  <div class="case-header">
    <div>
      <span style="font-size:16px; font-weight:600;">Case #{c['case_id']}: {c['product']} / {c['folder']} ({c['lang']})</span>
      <span class="gt-badge" style="margin-left:10px;">GT: Overlapping</span>
    </div>
    <div>
      {status_badge}
    </div>
  </div>

  <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; font-size:13px; background:#0f172a; padding:12px; border-radius:6px; margin-bottom:12px;">
    <div><strong>New Collisions:</strong> {c['num_newly_created_intersections']}</div>
    <div><strong>Max Overlap Area:</strong> <span style="color:#4ade80; font-weight:bold;">{c['max_intersection_area_px2']} px&sup2;</span></div>
    <div><strong>Max Horizontal Intrusion:</strong> {c['max_horizontal_intrusion_px']} px</div>
    <div><strong>Max Gap Collapse:</strong> {c['max_gap_collapse_px']} px</div>
  </div>

  <div style="font-size:13px; margin-bottom:6px;"><strong>Directly Measured Physical Collision Pairs:</strong></div>
  <table>
    <thead>
      <tr>
        <th>Element 1</th>
        <th>Element 2</th>
        <th>Collision Type</th>
        <th>Overlap Area</th>
        <th>Intrusion</th>
        <th>Gap Delta</th>
        <th>Reflow Explained?</th>
      </tr>
    </thead>
    <tbody>
      {col_rows if col_rows else "<tr><td colspan='7' style='text-align:center; color:#94a3b8;'>Zero newly created bounding box intersections.</td></tr>"}
    </tbody>
  </table>
</div>
"""
    html_ev += "</body></html>"
    with open(OUTPUT_EVIDENCE_HTML, 'w', encoding='utf-8') as f:
        f.write(html_ev)

    # 2. Generate overlap_discrimination_analysis.html
    q = discrim_data["questions_answered"]
    cats = discrim_data["category_summary_distributions"]
    d_all = discrim_data["discrimination_rankings"]["vs_all_non_overlapping"]
    d_mis = discrim_data["discrimination_rankings"]["vs_misalignment"]
    d_trunc = discrim_data["discrimination_rankings"]["vs_truncation"]
    
    html_disc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Overlapping Physical Discrimination Analysis</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
  h1 {{ color: #38bdf8; font-size: 24px; margin-bottom: 6px; }}
  h2 {{ color: #93c5fd; font-size: 18px; margin-top: 28px; border-bottom: 1px solid #334155; padding-bottom: 6px; }}
  .metrics-banner {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 20px 0; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; text-align: center; }}
  .card-val {{ font-size: 20px; font-weight: bold; margin-top: 4px; color: #38bdf8; }}
  .card-sub {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; background: #1e293b; border-radius: 6px; overflow: hidden; }}
  th, td {{ padding: 9px 12px; text-align: right; border-bottom: 1px solid #334155; }}
  th:first-child, td:first-child {{ text-align: left; }}
  th {{ background: #0f172a; color: #38bdf8; font-weight: 600; }}
  tr:hover {{ background: #243247; }}
</style>
</head>
<body>
<h1>Overlapping Physical Discrimination Analysis</h1>
<div style="color: #94a3b8; font-size: 14px;">
  Evaluating the selectivity of geometric collision, bounding-box intrusion, and sibling gap collapse across all 101 benchmark cases (19 Overlapping vs. 82 Non-Overlapping).
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Overlapping with Geometric Collision</div>
    <div class="card-val" style="color: #4ade80;">{q['Q_A_overlapping_with_genuine_new_intersections']}</div>
    <div class="card-sub">new non-zero intersection area</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Non-Overlapping with Collision</div>
    <div class="card-val" style="color: #f43f5e;">{q['Q_B_non_overlapping_with_intersections']}</div>
    <div class="card-sub">spurious / reflow bounding box collisions</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Overlapping with Gap Collapse</div>
    <div class="card-val" style="color: #38bdf8;">{q['Q_C_overlapping_with_gap_collapse']}</div>
    <div class="card-sub">gutter spacing shrunk &ge; 8px</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Top Separating Feature</div>
    <div class="card-val" style="font-size:15px;"><code>{d_all[0]['feature']}</code></div>
    <div class="card-sub">Fisher ratio: {d_all[0]['separation_ratio']}</div>
  </div>
</div>

<h2>1. Physical Feature Discrimination Power</h2>

<h3 style="color:#38bdf8; font-size:15px;">A. Overlapping vs All Non-Overlapping (N = 82)</h3>
<table>
  <thead>
    <tr>
      <th>Feature Measurement</th>
      <th>Overlapping Mean</th>
      <th>Non-Overlapping Mean</th>
      <th>Separation Ratio (Fisher Criterion)</th>
    </tr>
  </thead>
  <tbody>
"""
    for d in d_all[:6]:
        html_disc += f"""
    <tr>
      <td><code>{d['feature']}</code></td>
      <td style="color:#4ade80; font-weight:bold;">{d['overlapping_mean']}</td>
      <td>{d['non_overlapping_mean']}</td>
      <td style="color:#38bdf8; font-weight:bold;">{d['separation_ratio']:.4f}</td>
    </tr>
"""
    html_disc += """
  </tbody>
</table>

<h3 style="color:#38bdf8; font-size:15px; margin-top:20px;">B. Overlapping vs Misalignment (N = 19 vs N = 19)</h3>
<table>
  <thead>
    <tr>
      <th>Feature Measurement</th>
      <th>Overlapping Mean</th>
      <th>Misalignment Mean</th>
      <th>Separation Ratio</th>
    </tr>
  </thead>
  <tbody>
"""
    for d in d_mis[:6]:
        html_disc += f"""
    <tr>
      <td><code>{d['feature']}</code></td>
      <td style="color:#4ade80; font-weight:bold;">{d['overlapping_mean']}</td>
      <td>{d['misalignment_mean']}</td>
      <td style="color:#38bdf8; font-weight:bold;">{d['separation_ratio']:.4f}</td>
    </tr>
"""
    html_disc += """
  </tbody>
</table>

<h3 style="color:#38bdf8; font-size:15px; margin-top:20px;">C. Overlapping vs Truncation (N = 19 vs N = 30)</h3>
<table>
  <thead>
    <tr>
      <th>Feature Measurement</th>
      <th>Overlapping Mean</th>
      <th>Truncation Mean</th>
      <th>Separation Ratio</th>
    </tr>
  </thead>
  <tbody>
"""
    for d in d_trunc[:6]:
        html_disc += f"""
    <tr>
      <td><code>{d['feature']}</code></td>
      <td style="color:#4ade80; font-weight:bold;">{d['overlapping_mean']}</td>
      <td>{d['truncation_mean']}</td>
      <td style="color:#38bdf8; font-weight:bold;">{d['separation_ratio']:.4f}</td>
    </tr>
"""
    html_disc += """
  </tbody>
</table>

<h2>2. Full Physical Metrics Across All 5 Categories</h2>
<table>
  <thead>
    <tr>
      <th>Category</th>
      <th>Total Inter Area (Mean/Med)</th>
      <th>Max Inter Area (Mean/Med)</th>
      <th>Max Intrusion (Mean/Med)</th>
      <th>Max Gap Collapse (Mean/Med)</th>
      <th>Gaps &le; 0 Count</th>
    </tr>
  </thead>
  <tbody>
"""
    for cat_name, cdata in cats.items():
        is_ov = (cat_name == "Overlapping")
        style = "background: #1e3a5f; font-weight:bold;" if is_ov else ""
        html_disc += f"""
    <tr style="{style}">
      <td style="color: {'#38bdf8' if is_ov else '#f8fafc'};">{cat_name} (N={cdata['count']})</td>
      <td>{cdata['total_intersection_area_px2']['mean']:.0f} px&sup2; / {cdata['total_intersection_area_px2']['median']:.0f} px&sup2;</td>
      <td>{cdata['max_intersection_area_px2']['mean']:.0f} px&sup2; / {cdata['max_intersection_area_px2']['median']:.0f} px&sup2;</td>
      <td>{cdata['max_horizontal_intrusion_px']['mean']:.1f} px / {cdata['max_horizontal_intrusion_px']['median']:.1f} px</td>
      <td>{cdata['max_gap_collapse_px']['mean']:.1f} px / {cdata['max_gap_collapse_px']['median']:.1f} px</td>
      <td>{cdata['num_gaps_became_non_positive']['mean']:.1f}</td>
    </tr>
"""
    html_disc += """
  </tbody>
</table>

</body>
</html>
"""
    with open(OUTPUT_DISCRIM_HTML, 'w', encoding='utf-8') as f:
        f.write(html_disc)

def main():
    records = load_benchmark_cases()
    eval_cases = evaluate_all_overlap_evidence(records)
    
    # Save overlap_evidence_v2.json
    with open(OUTPUT_EVIDENCE_JSON, 'w', encoding='utf-8') as f:
        json.dump(eval_cases, f, indent=2)
    print(f"Saved overlap evidence JSON to {OUTPUT_EVIDENCE_JSON.resolve()}")
    
    discrim_results = run_overlap_discrimination_analysis(eval_cases)
    
    # Save overlap_discrimination_analysis.json
    with open(OUTPUT_DISCRIM_JSON, 'w', encoding='utf-8') as f:
        json.dump(discrim_results, f, indent=2)
    print(f"Saved overlap discrimination JSON to {OUTPUT_DISCRIM_JSON.resolve()}")
    
    generate_html_reports(eval_cases, discrim_results)
    print(f"Saved visual HTML reports to {OUTPUT_EVIDENCE_HTML.resolve()} and {OUTPUT_DISCRIM_HTML.resolve()}")

    # Print summary to console
    q = discrim_results["questions_answered"]
    print("\n" + "="*75)
    print("OVERLAPPING PHYSICAL DISCRIMINATION SUMMARY")
    print("="*75)
    print(f"Q_A. Overlapping cases with genuine new intersections : {q['Q_A_overlapping_with_genuine_new_intersections']}")
    print(f"Q_B. Non-Overlapping cases with intersections          : {q['Q_B_non_overlapping_with_intersections']}")
    print(f"Q_C. Overlapping cases with sibling gap collapse       : {q['Q_C_overlapping_with_gap_collapse']}")
    print(f"Q_D. Gap collapse without actual collision (All cases) : {q['Q_D_gap_collapse_without_actual_collision']['across_all_benchmark_cases']}")
    print(f"Q_E. Collisions fully reflow-explained (All cases)     : {q['Q_E_collisions_fully_reflow_explained']}")
    print("\nTop Separating Feature (Overlapping vs Non-Overlapping):")
    for d in discrim_results["discrimination_rankings"]["vs_all_non_overlapping"][:4]:
        print(f"  - {d['feature']:35s}: Ratio = {d['separation_ratio']:.4f} (Ov: {d['overlapping_mean']} vs Non-Ov: {d['non_overlapping_mean']})")
    print("="*75 + "\n")

if __name__ == '__main__':
    main()
