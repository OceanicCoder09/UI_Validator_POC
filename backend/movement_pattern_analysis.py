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

from backend.relationship_evidence_all_cases import extract_all_elements, match_elements, calc_box_gap_and_alignment

EXCEL_PATH = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize/Screenshot data list from Welocalize.xlsx')
BASE_DATA_ROOT = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize')
RELATIONSHIP_PATH = pathlib.Path('backend/relationship_evidence_all_cases.json')

OUTPUT_JSON = pathlib.Path('backend/movement_pattern_analysis.json')
OUTPUT_HTML = pathlib.Path('backend/movement_pattern_analysis.html')

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

def analyze_movement_patterns(records):
    print(f"Analyzing movement patterns across {len(records)} benchmark cases...", flush=True)
    
    analyzed_cases = []
    category_grouped_metrics = collections.defaultdict(lambda: collections.defaultdict(list))
    
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
        
        if not matches:
            continue
            
        all_dx = [m["loc_element"]["x"] - m["enu_element"]["x"] for m in matches]
        all_dy = [m["loc_element"]["y"] - m["enu_element"]["y"] for m in matches]
        global_shift_x = float(np.median(all_dx))
        global_shift_y = float(np.median(all_dy))
        
        # 1. Translation-corrected vectors per matched element
        element_vectors = []
        for m in matches:
            e, l = m["enu_element"], m["loc_element"]
            corr_dx = (l["x"] - e["x"]) - global_shift_x
            corr_dy = (l["y"] - e["y"]) - global_shift_y
            disp_mag = float(np.hypot(corr_dx, corr_dy))
            width_exp = float(l["width"] - e["width"])
            element_vectors.append({
                "enu": e,
                "loc": l,
                "corr_dx": corr_dx,
                "corr_dy": corr_dy,
                "disp_mag": disp_mag,
                "width_exp": width_exp
            })
            
        # 2. Group into Structural Rows and Columns (within ENU coordinate buckets)
        rows = collections.defaultdict(list)
        cols = collections.defaultdict(list)
        for ev in element_vectors:
            e = ev["enu"]
            # Row bucket by Y coordinate (+/- 14px)
            row_key = int(round(e["y"] / 20.0) * 20)
            rows[row_key].append(ev)
            # Column bucket by left-anchor X coordinate (+/- 14px)
            col_key = int(round(e["x"] / 20.0) * 20)
            cols[col_key].append(ev)
            
        # 3. Variance/std across Structural Columns and Rows
        col_dx_stds = []
        col_dy_stds = []
        col_residual_disps = []
        for c_k, ev_list in cols.items():
            if len(ev_list) >= 2:
                dxs = [item["corr_dx"] for item in ev_list]
                dys = [item["corr_dy"] for item in ev_list]
                col_dx_stds.append(float(np.std(dxs)))
                col_dy_stds.append(float(np.std(dys)))
                
                # Residual displacement after removing dominant column vector
                dom_dx, dom_dy = np.median(dxs), np.median(dys)
                res = [np.hypot(item["corr_dx"] - dom_dx, item["corr_dy"] - dom_dy) for item in ev_list]
                col_residual_disps.extend(res)
                
        mean_col_dx_variance = float(np.mean(col_dx_stds)) if col_dx_stds else 0.0
        max_col_dx_variance = float(np.max(col_dx_stds)) if col_dx_stds else 0.0
        mean_col_dy_variance = float(np.mean(col_dy_stds)) if col_dy_stds else 0.0
        
        row_dx_stds = []
        for r_k, ev_list in rows.items():
            if len(ev_list) >= 2:
                dxs = [item["corr_dx"] for item in ev_list]
                row_dx_stds.append(float(np.std(dxs)))
        mean_row_dx_variance = float(np.mean(row_dx_stds)) if row_dx_stds else 0.0
        
        # 4. Movement Direction Coherence (Cosine Similarity against group centroid)
        all_vecs = np.array([[item["corr_dx"], item["corr_dy"]] for item in element_vectors if item["disp_mag"] >= 4.0])
        if len(all_vecs) >= 2:
            mean_v = np.mean(all_vecs, axis=0)
            norm_mean = np.linalg.norm(mean_v) + 1e-7
            cos_sims = [np.dot(v, mean_v) / (np.linalg.norm(v) * norm_mean + 1e-7) for v in all_vecs]
            direction_coherence = float(np.mean(cos_sims))
        else:
            direction_coherence = 1.0 # Uniform/no disparate movement
            
        # 5. Fraction of elements moving together vs independently
        # Elements with disp_mag < 6px move together with dialog; >= 12px move independently
        num_moving_with_dialog = sum(1 for item in element_vectors if item["disp_mag"] < 6.0)
        num_moving_independently = sum(1 for item in element_vectors if item["disp_mag"] >= 12.0)
        fraction_independent = float(num_moving_independently / max(1, len(element_vectors)))
        
        # 6. Mean Residual Displacement across all structural groups
        mean_residual_disp = float(np.mean(col_residual_disps)) if col_residual_disps else 0.0
        max_residual_disp = float(np.max(col_residual_disps)) if col_residual_disps else 0.0
        
        # 7. Column Anchor Consistency Breakdown (Before vs After)
        # Check alignment divergence of element pairs aligned in ENU (delta_x <= 4px)
        enu_aligned_divergences = []
        for i_a in range(len(element_vectors)):
            for i_b in range(i_a + 1, len(element_vectors)):
                e1, e2 = element_vectors[i_a]["enu"], element_vectors[i_b]["enu"]
                l1, l2 = element_vectors[i_a]["loc"], element_vectors[i_b]["loc"]
                if abs(e1["x"] - e2["x"]) <= 4 and abs(e1["y"] - e2["y"]) < 200:
                    loc_diff = abs(l1["x"] - l2["x"])
                    div = max(0, loc_diff - abs(e1["x"] - e2["x"]))
                    enu_aligned_divergences.append(div)
        max_column_anchor_break = float(max(enu_aligned_divergences, default=0.0))
        mean_column_anchor_break = float(np.mean(enu_aligned_divergences)) if enu_aligned_divergences else 0.0
        
        # 8 & 9. Text & Container Expansion Correlation
        # Check if downstream displacement correlates with preceding text expansion on same row
        reflow_displacements = []
        unexplained_displacements = []
        
        for r_k, ev_list in rows.items():
            ev_list_sorted = sorted(ev_list, key=lambda it: it["enu"]["x"])
            for idx in range(len(ev_list_sorted)):
                curr = ev_list_sorted[idx]
                # Preceding expansions on left
                preceding_expansions = sum(max(0.0, prev["width_exp"]) for prev in ev_list_sorted[:idx])
                if curr["corr_dx"] > 4.0:
                    # If displacement is explained by preceding text growth -> Reflow
                    if preceding_expansions >= curr["corr_dx"] * 0.7:
                        reflow_displacements.append(curr["corr_dx"])
                    else:
                        unexplained_displacements.append(curr["corr_dx"])
                        
        reflow_disp_ratio = float(len(reflow_displacements) / max(1, len(reflow_displacements) + len(unexplained_displacements)))
        structurally_independent_disp_count = len(unexplained_displacements)
        
        case_result = {
            "case_id": r["case_id"],
            "product": r["product"],
            "folder": r["folder"],
            "lang": r["lang"],
            "gt_category": r["gt_category"],
            "matched_elements_count": len(matches),
            "global_shift_x": round(global_shift_x, 1),
            "global_shift_y": round(global_shift_y, 1),
            "mean_column_dx_std": round(mean_col_dx_variance, 2),
            "max_column_dx_std": round(max_col_dx_variance, 2),
            "mean_column_dy_std": round(mean_col_dy_variance, 2),
            "mean_row_dx_std": round(mean_row_dx_variance, 2),
            "movement_direction_coherence": round(direction_coherence, 3),
            "fraction_independently_displaced": round(fraction_independent, 3),
            "mean_residual_disp_px": round(mean_residual_disp, 2),
            "max_residual_disp_px": round(max_residual_disp, 2),
            "max_column_anchor_break_px": round(max_column_anchor_break, 1),
            "mean_column_anchor_break_px": round(mean_column_anchor_break, 1),
            "reflow_displacement_ratio": round(reflow_disp_ratio, 3),
            "structurally_independent_displacements_count": structurally_independent_disp_count
        }
        
        analyzed_cases.append(case_result)
        
        gt = r["gt_category"]
        for k, v in case_result.items():
            if isinstance(v, (int, float)) and k not in ["case_id"]:
                category_grouped_metrics[gt][k].append(v)
                
        if (i + 1) % 25 == 0 or (i + 1) == len(records):
            print(f"  Processed {i+1}/{len(records)} cases in {time.time()-t0:.1f}s", flush=True)

    # Compute statistical summaries per category
    category_summary = {}
    features_to_report = [
        "mean_column_dx_std",
        "max_column_dx_std",
        "mean_column_dy_std",
        "mean_row_dx_std",
        "movement_direction_coherence",
        "fraction_independently_displaced",
        "mean_residual_disp_px",
        "max_residual_disp_px",
        "max_column_anchor_break_px",
        "reflow_displacement_ratio",
        "structurally_independent_displacements_count"
    ]
    
    for cat, feats in category_grouped_metrics.items():
        cat_stats = {"count": len(feats["mean_column_dx_std"])}
        for f_name in features_to_report:
            vals = feats[f_name]
            cat_stats[f_name] = {
                "mean": round(float(np.mean(vals)), 2),
                "std": round(float(np.std(vals)), 2),
                "median": round(float(np.median(vals)), 2),
                "q25": round(float(np.percentile(vals, 25)), 2),
                "q75": round(float(np.percentile(vals, 75)), 2),
                "min": round(float(np.min(vals)), 2),
                "max": round(float(np.max(vals)), 2)
            }
        category_summary[cat] = cat_stats

    # Compare Misalignment vs Non-Misalignment separation power across movement patterns
    mis_cases = [c for c in analyzed_cases if c["gt_category"] == "Misalignment"]
    non_mis_cases = [c for c in analyzed_cases if c["gt_category"] != "Misalignment"]
    
    feature_discrimination = []
    for f_name in features_to_report:
        m_vals = [c[f_name] for c in mis_cases]
        nm_vals = [c[f_name] for c in non_mis_cases]
        
        m_mean, m_var = np.mean(m_vals), np.var(m_vals)
        nm_mean, nm_var = np.mean(nm_vals), np.var(nm_vals)
        
        f_ratio = ((m_mean - nm_mean) ** 2) / (m_var + nm_var + 1e-7)
        feature_discrimination.append({
            "feature": f_name,
            "misalignment_mean": round(float(m_mean), 2),
            "non_misalignment_mean": round(float(nm_mean), 2),
            "misalignment_median": round(float(np.median(m_vals)), 2),
            "non_misalignment_median": round(float(np.median(nm_vals)), 2),
            "separation_ratio": round(float(f_ratio), 4)
        })
    feature_discrimination.sort(key=lambda x: x["separation_ratio"], reverse=True)

    # Exemplar Cases:
    # 1. Localization reflow with large displacement but low structural break
    reflow_exemplars = sorted(
        [c for c in non_mis_cases if c["reflow_displacement_ratio"] >= 0.80 and c["max_residual_disp_px"] <= 25.0],
        key=lambda x: x["max_residual_disp_px"]
    )[:5]
    
    # 2. Misalignment with structurally independent movement
    struct_mis_exemplars = sorted(
        [c for c in mis_cases if c["structurally_independent_displacements_count"] >= 5 and c["max_column_anchor_break_px"] >= 50.0],
        key=lambda x: x["max_column_anchor_break_px"],
        reverse=True
    )[:5]

    results = {
        "total_cases_analyzed": len(analyzed_cases),
        "movement_pattern_feature_discrimination": feature_discrimination,
        "category_summary": category_summary,
        "exemplar_reflow_cases": reflow_exemplars,
        "exemplar_misalignment_cases": struct_mis_exemplars,
        "cases": analyzed_cases
    }
    
    return results

def generate_html_report(results, output_path):
    disc = results["movement_pattern_feature_discrimination"]
    cats = results["category_summary"]
    reflow_ex = results["exemplar_reflow_cases"]
    mis_ex = results["exemplar_misalignment_cases"]
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Structural Movement Pattern Analysis Report</title>
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
  .badge-pos {{ color: #4ade80; font-weight: bold; }}
  .badge-neg {{ color: #f43f5e; font-weight: bold; }}
</style>
</head>
<body>
<h1>Structural Movement Pattern Analysis Report</h1>
<div style="color: #94a3b8; font-size: 14px;">
  Distinguishing <strong>Misalignment defects</strong> from <strong>benign localization reflow</strong> across 101 benchmark cases via structural column consistency, direction coherence, and residual displacement.
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Top Discriminative Metric</div>
    <div class="card-val" style="font-size:16px;"><code>{disc[0]['feature']}</code></div>
    <div class="card-sub">Fisher ratio: {disc[0]['separation_ratio']}</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Column Anchor Break (Misalignment)</div>
    <div class="card-val" style="color: #4ade80;">{cats['Misalignment']['max_column_anchor_break_px']['median']}px (median)</div>
    <div class="card-sub">mean: {cats['Misalignment']['max_column_anchor_break_px']['mean']}px</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Column Anchor Break (Reflow/Non-Mis)</div>
    <div class="card-val" style="color: #cbd5e1;">{cats['Truncation']['max_column_anchor_break_px']['median']}px / {cats['Untranslation']['max_column_anchor_break_px']['median']}px</div>
    <div class="card-sub">columns stay aligned in benign reflow</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Reflow Ratio (Non-Misalignment)</div>
    <div class="card-val" style="color: #38bdf8;">{cats['Truncation']['reflow_displacement_ratio']['mean']*100:.1f}%</div>
    <div class="card-sub">movement explained by text width growth</div>
  </div>
</div>

<h2>1. Feature Discrimination Ranking (Movement Patterns vs Pure Displacement)</h2>
<table>
  <thead>
    <tr>
      <th>Movement Pattern Feature</th>
      <th>Misalignment (Mean / Median)</th>
      <th>Non-Misalignment (Mean / Median)</th>
      <th>Separation Ratio (Fisher Criterion)</th>
      <th>Physical Diagnostic Meaning</th>
    </tr>
  </thead>
  <tbody>
"""
    meaning_map = {
        "max_column_anchor_break_px": "Maximum anchor break for elements vertically aligned in baseline.",
        "max_column_dx_std": "Standard deviation of horizontal displacement within column peers.",
        "max_residual_disp_px": "Displacement remaining after subtracting dominant column reflow vector.",
        "structurally_independent_displacements_count": "Count of displaced elements not explained by upstream text growth.",
        "mean_residual_disp_px": "Mean residual unaligned movement across all structural groups.",
        "mean_column_dx_std": "Mean intra-column variance in horizontal anchor shift.",
        "fraction_independently_displaced": "Proportion of dialog elements moving independently.",
        "reflow_displacement_ratio": "Fraction of displacement directly preceded by text width expansion.",
        "movement_direction_coherence": "Uniformity of movement direction across displaced elements.",
        "mean_row_dx_std": "Standard deviation of horizontal displacement along same row.",
        "mean_column_dy_std": "Vertical anchor instability within column peers."
    }
    for d in disc:
        html += f"""
    <tr>
      <td><code>{d['feature']}</code></td>
      <td style="color:#4ade80; font-weight:bold;">{d['misalignment_mean']} / {d['misalignment_median']}</td>
      <td style="color:#cbd5e1;">{d['non_misalignment_mean']} / {d['non_misalignment_median']}</td>
      <td style="color:#38bdf8; font-weight:bold;">{d['separation_ratio']:.4f}</td>
      <td style="font-size:12px; color:#94a3b8;">{meaning_map.get(d['feature'], '')}</td>
    </tr>
"""
    html += """
  </tbody>
</table>

<h2>2. Full Movement Pattern Metrics Across All 5 Target Categories</h2>
<table>
  <thead>
    <tr>
      <th>Ground Truth Category</th>
      <th>Max Column Anchor Break (Mean / Med)</th>
      <th>Max Residual Disp (Mean / Med)</th>
      <th>Max Column dx Std (Mean / Med)</th>
      <th>Independent Elements Count</th>
      <th>Reflow Ratio %</th>
    </tr>
  </thead>
  <tbody>
"""
    for cat_name, cdata in cats.items():
        is_mis = (cat_name == "Misalignment")
        style = "background: #1e3a5f; font-weight:bold;" if is_mis else ""
        html += f"""
    <tr style="{style}">
      <td style="color: {'#38bdf8' if is_mis else '#f8fafc'};">{cat_name} (N={cdata['count']})</td>
      <td style="color:#4ade80;">{cdata['max_column_anchor_break_px']['mean']:.1f}px / {cdata['max_column_anchor_break_px']['median']:.1f}px</td>
      <td>{cdata['max_residual_disp_px']['mean']:.1f}px / {cdata['max_residual_disp_px']['median']:.1f}px</td>
      <td>{cdata['max_column_dx_std']['mean']:.1f}px / {cdata['max_column_dx_std']['median']:.1f}px</td>
      <td>{cdata['structurally_independent_displacements_count']['mean']:.1f} / {cdata['structurally_independent_displacements_count']['median']:.1f}</td>
      <td>{cdata['reflow_displacement_ratio']['mean']*100:.1f}%</td>
    </tr>
"""
    html += """
  </tbody>
</table>

<h2>3. Case Exemplars: Benign Reflow vs Structurally Independent Misalignment</h2>

<h3 style="color:#38bdf8; font-size:15px;">A. Benign Localization Reflow (Large Displacement, but High Reflow Ratio & Columns Intact)</h3>
<table>
  <thead>
    <tr>
      <th>Case ID</th>
      <th>Product / Folder (Lang)</th>
      <th>GT Category</th>
      <th>Max Residual Disp</th>
      <th>Reflow Ratio</th>
      <th>Column Anchor Break</th>
      <th>Physical Explanation</th>
    </tr>
  </thead>
  <tbody>
"""
    for ex in reflow_ex:
        html += f"""
    <tr>
      <td style="font-weight:bold;">#{ex['case_id']}</td>
      <td>{ex['product']} / {ex['folder']} ({ex['lang']})</td>
      <td>{ex['gt_category']}</td>
      <td>{ex['max_residual_disp_px']:.1f}px</td>
      <td style="color:#4ade80; font-weight:bold;">{ex['reflow_displacement_ratio']*100:.1f}%</td>
      <td>{ex['max_column_anchor_break_px']:.1f}px</td>
      <td style="font-size:12px; color:#cbd5e1;">Buttons/inputs pushed downstream strictly due to translated string expansion.</td>
    </tr>
"""
    html += """
  </tbody>
</table>

<h3 style="color:#38bdf8; font-size:15px; margin-top:20px;">B. True Structural Misalignment (High Anchor Break & Independent Displacements)</h3>
<table>
  <thead>
    <tr>
      <th>Case ID</th>
      <th>Product / Folder (Lang)</th>
      <th>GT Category</th>
      <th>Max Column Anchor Break</th>
      <th>Max Column dx Std</th>
      <th>Independent Count</th>
      <th>Physical Explanation</th>
    </tr>
  </thead>
  <tbody>
"""
    for ex in mis_ex:
        html += f"""
    <tr>
      <td style="font-weight:bold;">#{ex['case_id']}</td>
      <td>{ex['product']} / {ex['folder']} ({ex['lang']})</td>
      <td>{ex['gt_category']}</td>
      <td style="color:#4ade80; font-weight:bold;">{ex['max_column_anchor_break_px']:.1f}px</td>
      <td>{ex['max_column_dx_std']:.1f}px</td>
      <td>{ex['structurally_independent_displacements_count']}</td>
      <td style="font-size:12px; color:#cbd5e1;">Column anchor broken independently of text width growth.</td>
    </tr>
"""
    html += """
  </tbody>
</table>

</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

def main():
    records = load_benchmark_cases()
    results = analyze_movement_patterns(records)
    
    print("\n" + "="*75)
    print("STRUCTURAL MOVEMENT PATTERN ANALYSIS SUMMARY (N = 101)")
    print("="*75)
    print("Top Discriminative Movement Features (Ranked by Fisher Criterion):")
    for d in results["movement_pattern_feature_discrimination"][:6]:
        print(f"  - {d['feature']:45s}: Ratio = {d['separation_ratio']:.4f} (Mis: {d['misalignment_mean']:.1f} vs Non: {d['non_misalignment_mean']:.1f})")
    print("="*75)
    
    print("\nMovement Pattern Distribution Across 5 Categories:")
    for cat, stats in results["category_summary"].items():
        print(f"\n  [{cat}] (N={stats['count']})")
        print(f"    * Max Column Anchor Break : Mean = {stats['max_column_anchor_break_px']['mean']:5.1f}px | Median = {stats['max_column_anchor_break_px']['median']:5.1f}px")
        print(f"    * Max Column dx Std       : Mean = {stats['max_column_dx_std']['mean']:5.1f}px | Median = {stats['max_column_dx_std']['median']:5.1f}px")
        print(f"    * Max Residual Disp       : Mean = {stats['max_residual_disp_px']['mean']:5.1f}px | Median = {stats['max_residual_disp_px']['median']:5.1f}px")
        print(f"    * Reflow Ratio            : Mean = {stats['reflow_displacement_ratio']['mean']*100:5.1f}%")
        
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved movement pattern analysis JSON to {OUTPUT_JSON.resolve()}")
    
    generate_html_report(results, OUTPUT_HTML)
    print(f"Saved visual HTML report to {OUTPUT_HTML.resolve()}")

if __name__ == '__main__':
    main()
