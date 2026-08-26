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
from backend.cv_engine import detect_ellipsis_precise

EXCEL_PATH = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize/Screenshot data list from Welocalize.xlsx')
BASE_DATA_ROOT = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize')

OUTPUT_EVIDENCE_JSON = pathlib.Path('backend/truncation_evidence_v2.json')
OUTPUT_EVIDENCE_HTML = pathlib.Path('backend/truncation_evidence_v2.html')
OUTPUT_DISCRIM_JSON = pathlib.Path('backend/truncation_discrimination_analysis.json')
OUTPUT_DISCRIM_HTML = pathlib.Path('backend/truncation_discrimination_analysis.html')

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

def check_glyph_edge_clipping(gray_img, text_box, container_box):
    """
    Directly checks whether text characters are abruptly sliced at the container boundary.
    """
    tx, ty, tw, th = text_box
    cx, cy, cw, ch = container_box
    
    # Check if text right edge directly borders container right edge within 4px
    right_diff = abs((tx + tw) - (cx + cw))
    if right_diff <= 4 and th >= 10:
        h_img, w_img = gray_img.shape[:2]
        crop_strip = gray_img[max(0, ty):min(h_img, ty+th), max(0, tx+tw-4):min(w_img, tx+tw+2)]
        if crop_strip.size > 0 and crop_strip.shape[1] >= 3:
            diff_h = np.abs(crop_strip[:, :-1].astype(int) - crop_strip[:, 1:].astype(int))
            mean_edge_grad = float(np.mean(diff_h))
            if mean_edge_grad > 35.0:
                return True, round(mean_edge_grad, 1)
    return False, 0.0

def evaluate_all_truncation_evidence(records):
    print(f"Evaluating physical truncation evidence across {len(records)} benchmark cases...", flush=True)
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
        
        gray_en = cv2.cvtColor(img_en, cv2.COLOR_BGR2GRAY)
        gray_loc = cv2.cvtColor(img_loc, cv2.COLOR_BGR2GRAY)
        
        enu_elements = extract_all_elements(img_en, prefix="E")
        loc_elements = extract_all_elements(img_loc, prefix="L")
        matches, unmatched_enu, unmatched_loc = match_elements(enu_elements, loc_elements, target_w, target_h)
        
        # Enclosing containers in ENU and LOC
        enu_containers = [e for e in enu_elements if e["type"] in ["button", "dropdown", "input", "card", "container"]]
        loc_containers = [l for l in loc_elements if l["type"] in ["button", "dropdown", "input", "card", "container"]]
        
        case_text_expansions = []
        case_overflows = []
        case_fit_ratios_enu = []
        case_fit_ratios_loc = []
        case_right_margins = []
        
        genuine_clipping_count = 0
        verified_ellipsis_count = 0
        container_expanded_accommodated_count = 0
        normal_growth_preserved_layout_count = 0
        
        detailed_text_elements = []
        
        for m in matches:
            e, l = m["enu_element"], m["loc_element"]
            if e["type"] != "text" or l["type"] != "text":
                continue
                
            tw_en, th_en = e["width"], e["height"]
            tw_loc, th_loc = l["width"], l["height"]
            tx_loc, ty_loc = l["x"], l["y"]
            
            # Text expansion
            text_expansion_px = tw_loc - tw_en
            case_text_expansions.append(text_expansion_px)
            
            # Find enclosing container in ENU
            matched_c_en = None
            for c in enu_containers:
                if c["x"] - 6 <= e["x"] and (e["x"] + e["width"]) <= c["x"] + c["width"] + 6 and c["y"] - 6 <= e["y"] and (e["y"] + e["height"]) <= c["y"] + c["height"] + 6:
                    matched_c_en = c
                    break
                    
            # Find enclosing container in LOC
            matched_c_loc = None
            for c in loc_containers:
                if c["x"] - 6 <= l["x"] and c["y"] - 6 <= l["y"] and (l["y"] + l["height"]) <= c["y"] + c["height"] + 6:
                    matched_c_loc = c
                    break
                    
            cw_en = matched_c_en["width"] if matched_c_en else None
            cw_loc = matched_c_loc["width"] if matched_c_loc else None
            
            # Text-to-container fit ratios
            fit_ratio_en = round(tw_en / float(cw_en), 3) if cw_en else None
            fit_ratio_loc = round(tw_loc / float(cw_loc), 3) if cw_loc else None
            if fit_ratio_en: case_fit_ratios_enu.append(fit_ratio_en)
            if fit_ratio_loc: case_fit_ratios_loc.append(fit_ratio_loc)
            
            # Physical Overflow calculation
            overflow_px = None
            right_margin_px = None
            is_clipped = False
            has_glyph_cut = False
            
            if matched_c_loc:
                c_right = matched_c_loc["x"] + matched_c_loc["width"]
                t_right = tx_loc + tw_loc
                right_margin_px = c_right - t_right
                case_right_margins.append(right_margin_px)
                
                if t_right > c_right:
                    overflow_px = int(t_right - c_right)
                    case_overflows.append(overflow_px)
                    is_clipped = True
                else:
                    overflow_px = 0
                    
                # Direct pixel glyph cut check
                has_glyph_cut, edge_grad = check_glyph_edge_clipping(
                    gray_loc, 
                    (tx_loc, ty_loc, tw_loc, th_loc),
                    (matched_c_loc["x"], matched_c_loc["y"], matched_c_loc["width"], matched_c_loc["height"])
                )
                if has_glyph_cut:
                    is_clipped = True
                    
            # Check for trailing ellipsis in OCR text or pixel strip
            txt_str = l.get("text", "").strip()
            ocr_has_ellipsis = bool(re.search(r'(\.{2,4}|…|\.\s\.\s\.)$', txt_str))
            
            crop_loc_g = gray_loc[max(0, ty_loc-2):min(target_h, ty_loc+th_loc+2), max(0, tx_loc-2):min(target_w, tx_loc+tw_loc+2)]
            pixel_has_ellipsis = detect_ellipsis_precise(crop_loc_g) if crop_loc_g.size > 0 else False
            
            # Verify if ENU baseline already had this ellipsis (baseline might be clean)
            enu_txt_str = e.get("text", "").strip()
            enu_has_ellipsis = bool(re.search(r'(\.{2,4}|…|\.\s\.\s\.)$', enu_txt_str))
            
            verified_new_ellipsis = (ocr_has_ellipsis or pixel_has_ellipsis) and not enu_has_ellipsis
            
            # Container accommodation check
            container_expanded_accommodated = False
            if cw_en and cw_loc:
                c_exp = cw_loc - cw_en
                if text_expansion_px > 0 and c_exp >= text_expansion_px * 0.8 and not is_clipped:
                    container_expanded_accommodated = True
                    container_expanded_accommodated_count += 1
                    
            if text_expansion_px > 0 and not is_clipped and not verified_new_ellipsis and (right_margin_px is None or right_margin_px >= 4):
                normal_growth_preserved_layout_count += 1
                
            if is_clipped:
                genuine_clipping_count += 1
            if verified_new_ellipsis:
                verified_ellipsis_count += 1
                
            # Classify element state
            if is_clipped:
                elem_state = "GENUINE_TEXT_CLIPPING"
            elif verified_new_ellipsis:
                elem_state = "ELLIPSIS_TRUNCATION"
            elif container_expanded_accommodated:
                elem_state = "CONTAINER_EXPANSION_ACCOMMODATED"
            elif text_expansion_px > 0:
                elem_state = "NORMAL_TEXT_GROWTH_PRESERVED"
            else:
                elem_state = "UNCHANGED_OR_SHRUNK"
                
            detailed_text_elements.append({
                "element_id": l["id"],
                "text_enu": enu_txt_str[:30],
                "text_loc": txt_str[:30],
                "enu_text_width": tw_en,
                "loc_text_width": tw_loc,
                "text_expansion_px": text_expansion_px,
                "enu_container_width": cw_en,
                "loc_container_width": cw_loc,
                "fit_ratio_enu": fit_ratio_en,
                "fit_ratio_loc": fit_ratio_loc,
                "overflow_px": overflow_px,
                "right_margin_px": right_margin_px,
                "is_clipped": is_clipped,
                "verified_new_ellipsis": verified_new_ellipsis,
                "has_glyph_cut": has_glyph_cut,
                "element_state": elem_state,
                "provenance": {
                    "text_width": "DIRECTLY_MEASURED",
                    "container_width": "DIRECTLY_MEASURED" if cw_loc else "UNAVAILABLE",
                    "overflow": "DIRECTLY_MEASURED" if overflow_px is not None else "UNAVAILABLE",
                    "fit_ratio": "DERIVED_FROM_MEASUREMENT" if fit_ratio_loc else "UNAVAILABLE",
                    "ellipsis": "DIRECTLY_MEASURED"
                }
            })

        max_text_expansion = max(case_text_expansions, default=0)
        max_overflow = max(case_overflows, default=0)
        min_right_margin = min(case_right_margins, default=999) if case_right_margins else None
        mean_fit_ratio_loc = round(float(np.mean(case_fit_ratios_loc)), 3) if case_fit_ratios_loc else None
        
        has_direct_clipping_evidence = (genuine_clipping_count > 0 or max_overflow > 0)
        has_genuine_ellipsis_evidence = (verified_ellipsis_count > 0)
        has_truncation_evidence = (has_direct_clipping_evidence or has_genuine_ellipsis_evidence)
        
        has_text_expansion_only_no_trunc = (max_text_expansion >= 15 and not has_truncation_evidence)
        
        case_record = {
            "case_id": r["case_id"],
            "product": r["product"],
            "folder": r["folder"],
            "lang": r["lang"],
            "gt_category": r["gt_category"],
            "matched_elements_count": len(matches),
            "max_text_expansion_px": max_text_expansion,
            "max_overflow_px": max_overflow,
            "min_right_margin_px": min_right_margin if min_right_margin != 999 else None,
            "mean_fit_ratio_loc": mean_fit_ratio_loc,
            "genuine_clipping_elements_count": genuine_clipping_count,
            "verified_ellipsis_elements_count": verified_ellipsis_count,
            "container_expanded_accommodated_count": container_expanded_accommodated_count,
            "normal_growth_preserved_layout_count": normal_growth_preserved_layout_count,
            "has_direct_clipping_evidence": has_direct_clipping_evidence,
            "has_genuine_ellipsis_evidence": has_genuine_ellipsis_evidence,
            "has_physical_truncation_evidence": has_truncation_evidence,
            "has_text_expansion_only_no_trunc": has_text_expansion_only_no_trunc,
            "detailed_text_elements": detailed_text_elements[:10]
        }
        
        all_case_evaluations.append(case_record)
        if (i + 1) % 25 == 0 or (i + 1) == len(records):
            print(f"  Audited {i+1}/{len(records)} cases in {time.time()-t0:.1f}s", flush=True)

    return all_case_evaluations

def run_truncation_discrimination_analysis(all_cases):
    trunc_cases = [c for c in all_cases if c["gt_category"] == "Truncation"]
    non_trunc_cases = [c for c in all_cases if c["gt_category"] != "Truncation"]
    misalign_cases = [c for c in all_cases if c["gt_category"] == "Misalignment"]
    overlap_cases = [c for c in all_cases if c["gt_category"] == "Overlapping"]
    untrans_cases = [c for c in all_cases if c["gt_category"] == "Untranslation"]
    hotkey_cases = [c for c in all_cases if c["gt_category"] == "Repeated hotkey"]
    
    # Q_A: Truncation cases with direct physical clipping/overflow evidence
    trunc_with_clipping = sum(1 for c in trunc_cases if c["has_direct_clipping_evidence"])
    # Q_B: Truncation cases with genuine ellipsis evidence
    trunc_with_ellipsis = sum(1 for c in trunc_cases if c["has_genuine_ellipsis_evidence"])
    # Q_C: Cases with text expansion but NO truncation
    trunc_expansion_no_trunc = sum(1 for c in trunc_cases if c["has_text_expansion_only_no_trunc"])
    all_expansion_no_trunc = sum(1 for c in all_cases if c["has_text_expansion_only_no_trunc"])
    
    # Q_D: Non-Truncation cases showing apparent overflow
    non_trunc_with_overflow = sum(1 for c in non_trunc_cases if c["has_direct_clipping_evidence"])
    # Q_E: Container expansion explaining apparent overflow
    cases_with_expansion = [c for c in all_cases if c["max_text_expansion_px"] >= 15]
    expansion_accommodated = sum(1 for c in cases_with_expansion if c["container_expanded_accommodated_count"] > 0)
    
    features_to_compare = [
        "max_text_expansion_px",
        "max_overflow_px",
        "genuine_clipping_elements_count",
        "verified_ellipsis_elements_count",
        "container_expanded_accommodated_count",
        "normal_growth_preserved_layout_count"
    ]
    
    categories = {
        "Truncation": trunc_cases,
        "Misalignment": misalign_cases,
        "Overlapping": overlap_cases,
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

    def calc_fisher(c1_items, c2_items, feat):
        v1 = [x[feat] for x in c1_items]
        v2 = [x[feat] for x in c2_items]
        m1, var1 = np.mean(v1), np.var(v1)
        m2, var2 = np.mean(v2), np.var(v2)
        return float(((m1 - m2) ** 2) / (var1 + var2 + 1e-7))

    disc_vs_all = []
    disc_vs_ov = []
    disc_vs_untrans = []
    disc_vs_mis = []
    
    for f in features_to_compare:
        r_all = calc_fisher(trunc_cases, non_trunc_cases, f)
        r_ov = calc_fisher(trunc_cases, overlap_cases, f)
        r_untrans = calc_fisher(trunc_cases, untrans_cases, f)
        r_mis = calc_fisher(trunc_cases, misalign_cases, f)
        
        disc_vs_all.append({
            "feature": f,
            "truncation_mean": category_summary["Truncation"][f]["mean"],
            "non_truncation_mean": round(float(np.mean([x[f] for x in non_trunc_cases])), 2),
            "separation_ratio": round(r_all, 4)
        })
        disc_vs_ov.append({
            "feature": f,
            "truncation_mean": category_summary["Truncation"][f]["mean"],
            "overlapping_mean": category_summary["Overlapping"][f]["mean"],
            "separation_ratio": round(r_ov, 4)
        })
        disc_vs_untrans.append({
            "feature": f,
            "truncation_mean": category_summary["Truncation"][f]["mean"],
            "untranslation_mean": category_summary["Untranslation"][f]["mean"],
            "separation_ratio": round(r_untrans, 4)
        })
        
    disc_vs_all.sort(key=lambda x: x["separation_ratio"], reverse=True)
    disc_vs_ov.sort(key=lambda x: x["separation_ratio"], reverse=True)
    disc_vs_untrans.sort(key=lambda x: x["separation_ratio"], reverse=True)

    # Exemplars: True Truncation vs False Positive Expansion
    true_trunc_exemplars = sorted(
        [c for c in trunc_cases if c["has_physical_truncation_evidence"]],
        key=lambda x: x["max_overflow_px"] + x["verified_ellipsis_elements_count"] * 50,
        reverse=True
    )[:5]
    
    false_pos_expansion_exemplars = sorted(
        [c for c in non_trunc_cases if c["max_text_expansion_px"] >= 60 and not c["has_physical_truncation_evidence"]],
        key=lambda x: x["max_text_expansion_px"],
        reverse=True
    )[:5]

    discrimination_results = {
        "total_benchmark_cases": len(all_cases),
        "truncation_cases_count": len(trunc_cases),
        "non_truncation_cases_count": len(non_trunc_cases),
        "questions_answered": {
            "Q_A_truncation_with_direct_clipping_overflow": f"{trunc_with_clipping} / {len(trunc_cases)} ({trunc_with_clipping/len(trunc_cases)*100:.1f}%)",
            "Q_B_truncation_with_genuine_ellipsis": f"{trunc_with_ellipsis} / {len(trunc_cases)} ({trunc_with_ellipsis/len(trunc_cases)*100:.1f}%)",
            "Q_C_text_expansion_without_truncation": {
                "in_truncation_category": f"{trunc_expansion_no_trunc} / {len(trunc_cases)}",
                "across_all_benchmark_cases": f"{all_expansion_no_trunc} / {len(all_cases)} ({all_expansion_no_trunc/len(all_cases)*100:.1f}%)"
            },
            "Q_D_non_truncation_cases_showing_apparent_overflow": f"{non_trunc_with_overflow} / {len(non_trunc_cases)} ({non_trunc_with_overflow/len(non_trunc_cases)*100:.1f}%)",
            "Q_E_container_expansion_accommodated_cases": f"{expansion_accommodated} / {len(cases_with_expansion)} ({expansion_accommodated/max(1, len(cases_with_expansion))*100:.1f}%)"
        },
        "discrimination_rankings": {
            "vs_all_non_truncation": disc_vs_all,
            "vs_overlapping": disc_vs_ov,
            "vs_untranslation": disc_vs_untrans
        },
        "category_summary_distributions": category_summary,
        "true_truncation_exemplars": true_trunc_exemplars,
        "false_positive_expansion_exemplars": false_pos_expansion_exemplars
    }
    
    return discrimination_results

def generate_html_reports(eval_data, discrim_data):
    # 1. Generate truncation_evidence_v2.html
    html_ev = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Truncation Physical Evidence Report v2</title>
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
<h1>Truncation Physical Evidence Report (v2)</h1>
<div style="color: #94a3b8; font-size: 14px;">
  Direct text-to-container boundary overflow, physical glyph clipping, and verified ellipsis measurements across all 30 Truncation benchmark cases.
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Total Truncation Cases</div>
    <div class="card-val" style="color: #f8fafc;">30</div>
    <div class="card-sub">ground truth benchmark cases</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Direct Clipping / Overflow</div>
    <div class="card-val" style="color: #4ade80;">{discrim_data['questions_answered']['Q_A_truncation_with_direct_clipping_overflow']}</div>
    <div class="card-sub">measured overflow past container</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Verified Ellipsis ('...')</div>
    <div class="card-val" style="color: #38bdf8;">{discrim_data['questions_answered']['Q_B_truncation_with_genuine_ellipsis']}</div>
    <div class="card-sub">new localized ellipsis detected</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Text Expansion Alone (No Trunc)</div>
    <div class="card-val" style="color: #f59e0b;">{discrim_data['questions_answered']['Q_C_text_expansion_without_truncation']['in_truncation_category']}</div>
    <div class="card-sub">growth without container boundary cut</div>
  </div>
</div>

<h2>Case-by-Case Physical Truncation Audit (30 Truncation Cases)</h2>
"""
    trunc_only = [c for c in eval_data if c["gt_category"] == "Truncation"]
    for c in trunc_only:
        status_badge = "<span class='status-pass'>[PASS] Genuine Truncation Evidence</span>" if c["has_physical_truncation_evidence"] else "<span class='status-fail'>[NO BOUNDARY CLIPPING]</span>"
        
        elem_rows = ""
        for el in c["detailed_text_elements"]:
            state_color = "#4ade80" if el["is_clipped"] or el["verified_new_ellipsis"] else "#94a3b8"
            elem_rows += f"""
      <tr>
        <td>'{el['text_enu']}' &rarr; '{el['text_loc']}'</td>
        <td>{el['enu_text_width']}px &rarr; {el['loc_text_width']}px (<strong>{el['text_expansion_px']:+d}px</strong>)</td>
        <td>{el['loc_container_width'] if el['loc_container_width'] else 'N/A'}px</td>
        <td>{el['overflow_px'] if el['overflow_px'] is not None else 'N/A'}px</td>
        <td>{el['right_margin_px'] if el['right_margin_px'] is not None else 'N/A'}px</td>
        <td>{'Yes' if el['verified_new_ellipsis'] else 'No'}</td>
        <td style="color:{state_color}; font-weight:bold;">{el['element_state']}</td>
      </tr>
"""
        html_ev += f"""
<div class="case-card">
  <div class="case-header">
    <div>
      <span style="font-size:16px; font-weight:600;">Case #{c['case_id']}: {c['product']} / {c['folder']} ({c['lang']})</span>
      <span class="gt-badge" style="margin-left:10px;">GT: Truncation</span>
    </div>
    <div>
      {status_badge}
    </div>
  </div>

  <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; font-size:13px; background:#0f172a; padding:12px; border-radius:6px; margin-bottom:12px;">
    <div><strong>Max Text Expansion:</strong> {c['max_text_expansion_px']:+d}px</div>
    <div><strong>Max Measured Overflow:</strong> <span style="color:#4ade80; font-weight:bold;">{c['max_overflow_px']}px</span></div>
    <div><strong>Clipping Elements:</strong> {c['genuine_clipping_elements_count']}</div>
    <div><strong>Verified Ellipsis:</strong> {c['verified_ellipsis_elements_count']}</div>
  </div>

  <div style="font-size:13px; margin-bottom:6px;"><strong>Directly Measured Text-to-Container Elements:</strong></div>
  <table>
    <thead>
      <tr>
        <th>Label (ENU &rarr; Localized)</th>
        <th>Text Width (ENU &rarr; LOC)</th>
        <th>Container Width</th>
        <th>Overflow</th>
        <th>Right Margin</th>
        <th>Ellipsis?</th>
        <th>Classification State</th>
      </tr>
    </thead>
    <tbody>
      {elem_rows if elem_rows else "<tr><td colspan='7' style='text-align:center; color:#94a3b8;'>No matched text elements found.</td></tr>"}
    </tbody>
  </table>
</div>
"""
    html_ev += "</body></html>"
    with open(OUTPUT_EVIDENCE_HTML, 'w', encoding='utf-8') as f:
        f.write(html_ev)

    # 2. Generate truncation_discrimination_analysis.html
    q = discrim_data["questions_answered"]
    cats = discrim_data["category_summary_distributions"]
    d_all = discrim_data["discrimination_rankings"]["vs_all_non_truncation"]
    d_ov = discrim_data["discrimination_rankings"]["vs_overlapping"]
    d_untrans = discrim_data["discrimination_rankings"]["vs_untranslation"]
    
    html_disc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Truncation Physical Discrimination Analysis</title>
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
<h1>Truncation Physical Discrimination Analysis</h1>
<div style="color: #94a3b8; font-size: 14px;">
  Evaluating the selectivity of measured text boundary overflow, glyph clipping, and verified ellipsis across all 101 benchmark cases (30 Truncation vs. 71 Non-Truncation).
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Truncation with Measured Clipping/Overflow</div>
    <div class="card-val" style="color: #4ade80;">{q['Q_A_truncation_with_direct_clipping_overflow']}</div>
    <div class="card-sub">boundary overflow or glyph cut</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Truncation with Verified Ellipsis</div>
    <div class="card-val" style="color: #38bdf8;">{q['Q_B_truncation_with_genuine_ellipsis']}</div>
    <div class="card-sub">localized ellipsis not in ENU</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Non-Truncation with Apparent Overflow</div>
    <div class="card-val" style="color: #f43f5e;">{q['Q_D_non_truncation_cases_showing_apparent_overflow']}</div>
    <div class="card-sub">unconstrained/floating label expansion</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Container Accommodated Cases</div>
    <div class="card-val" style="color: #4ade80;">{q['Q_E_container_expansion_accommodated_cases']}</div>
    <div class="card-sub">container expanded to fit text</div>
  </div>
</div>

<h2>1. Physical Feature Discrimination Power</h2>

<h3 style="color:#38bdf8; font-size:15px;">A. Truncation vs All Non-Truncation (N = 71)</h3>
<table>
  <thead>
    <tr>
      <th>Feature Measurement</th>
      <th>Truncation Mean</th>
      <th>Non-Truncation Mean</th>
      <th>Separation Ratio (Fisher Criterion)</th>
    </tr>
  </thead>
  <tbody>
"""
    for d in d_all[:5]:
        html_disc += f"""
    <tr>
      <td><code>{d['feature']}</code></td>
      <td style="color:#4ade80; font-weight:bold;">{d['truncation_mean']}</td>
      <td>{d['non_truncation_mean']}</td>
      <td style="color:#38bdf8; font-weight:bold;">{d['separation_ratio']:.4f}</td>
    </tr>
"""
    html_disc += """
  </tbody>
</table>

<h3 style="color:#38bdf8; font-size:15px; margin-top:20px;">B. Truncation vs Overlapping (N = 30 vs N = 19)</h3>
<table>
  <thead>
    <tr>
      <th>Feature Measurement</th>
      <th>Truncation Mean</th>
      <th>Overlapping Mean</th>
      <th>Separation Ratio</th>
    </tr>
  </thead>
  <tbody>
"""
    for d in d_ov[:5]:
        html_disc += f"""
    <tr>
      <td><code>{d['feature']}</code></td>
      <td style="color:#4ade80; font-weight:bold;">{d['truncation_mean']}</td>
      <td>{d['overlapping_mean']}</td>
      <td style="color:#38bdf8; font-weight:bold;">{d['separation_ratio']:.4f}</td>
    </tr>
"""
    html_disc += """
  </tbody>
</table>

<h3 style="color:#38bdf8; font-size:15px; margin-top:20px;">C. Truncation vs Untranslation (N = 30 vs N = 26)</h3>
<table>
  <thead>
    <tr>
      <th>Feature Measurement</th>
      <th>Truncation Mean</th>
      <th>Untranslation Mean</th>
      <th>Separation Ratio</th>
    </tr>
  </thead>
  <tbody>
"""
    for d in d_untrans[:5]:
        html_disc += f"""
    <tr>
      <td><code>{d['feature']}</code></td>
      <td style="color:#4ade80; font-weight:bold;">{d['truncation_mean']}</td>
      <td>{d['untranslation_mean']}</td>
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
      <th>Max Text Expansion (Mean/Med)</th>
      <th>Max Overflow (Mean/Med)</th>
      <th>Verified Ellipsis Count</th>
      <th>Clipping Elements Count</th>
      <th>Container Accommodated</th>
    </tr>
  </thead>
  <tbody>
"""
    for cat_name, cdata in cats.items():
        is_tr = (cat_name == "Truncation")
        style = "background: #1e3a5f; font-weight:bold;" if is_tr else ""
        html_disc += f"""
    <tr style="{style}">
      <td style="color: {'#38bdf8' if is_tr else '#f8fafc'};">{cat_name} (N={cdata['count']})</td>
      <td>{cdata['max_text_expansion_px']['mean']:.1f}px / {cdata['max_text_expansion_px']['median']:.1f}px</td>
      <td>{cdata['max_overflow_px']['mean']:.1f}px / {cdata['max_overflow_px']['median']:.1f}px</td>
      <td>{cdata['verified_ellipsis_elements_count']['mean']:.2f}</td>
      <td>{cdata['genuine_clipping_elements_count']['mean']:.2f}</td>
      <td>{cdata['container_expanded_accommodated_count']['mean']:.2f}</td>
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
    eval_cases = evaluate_all_truncation_evidence(records)
    
    # Save truncation_evidence_v2.json
    with open(OUTPUT_EVIDENCE_JSON, 'w', encoding='utf-8') as f:
        json.dump(eval_cases, f, indent=2)
    print(f"Saved truncation evidence JSON to {OUTPUT_EVIDENCE_JSON.resolve()}")
    
    discrim_results = run_truncation_discrimination_analysis(eval_cases)
    
    # Save truncation_discrimination_analysis.json
    with open(OUTPUT_DISCRIM_JSON, 'w', encoding='utf-8') as f:
        json.dump(discrim_results, f, indent=2)
    print(f"Saved truncation discrimination JSON to {OUTPUT_DISCRIM_JSON.resolve()}")
    
    generate_html_reports(eval_cases, discrim_results)
    print(f"Saved visual HTML reports to {OUTPUT_EVIDENCE_HTML.resolve()} and {OUTPUT_DISCRIM_HTML.resolve()}")

    q = discrim_results["questions_answered"]
    print("\n" + "="*75)
    print("TRUNCATION PHYSICAL DISCRIMINATION SUMMARY")
    print("="*75)
    print(f"Q_A. Truncation cases with direct clipping/overflow : {q['Q_A_truncation_with_direct_clipping_overflow']}")
    print(f"Q_B. Truncation cases with genuine ellipsis          : {q['Q_B_truncation_with_genuine_ellipsis']}")
    print(f"Q_C. Text expansion without truncation (All cases)   : {q['Q_C_text_expansion_without_truncation']['across_all_benchmark_cases']}")
    print(f"Q_D. Non-Truncation cases with apparent overflow     : {q['Q_D_non_truncation_cases_showing_apparent_overflow']}")
    print(f"Q_E. Container expansion accommodated cases          : {q['Q_E_container_expansion_accommodated_cases']}")
    print("\nTop Separating Feature (Truncation vs Non-Truncation):")
    for d in discrim_results["discrimination_rankings"]["vs_all_non_truncation"][:4]:
        print(f"  - {d['feature']:35s}: Ratio = {d['separation_ratio']:.4f} (Tr: {d['truncation_mean']} vs Non-Tr: {d['non_truncation_mean']})")
    print("="*75 + "\n")

if __name__ == '__main__':
    main()
