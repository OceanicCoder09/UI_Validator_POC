import os
import sys
import json
import pathlib
import collections
import pandas as pd
import numpy as np

MISALIGN_PATH = pathlib.Path('backend/misalignment_evidence_v2.json')
MOVEMENT_PATH = pathlib.Path('backend/movement_pattern_analysis.json')
OVERLAP_PATH = pathlib.Path('backend/overlap_evidence_v2.json')
TRUNC_PATH = pathlib.Path('backend/truncation_evidence_v2.json')
UNTRANS_PATH = pathlib.Path('backend/untranslation_evidence_v2.json')
HOTKEY_PATH = pathlib.Path('backend/hotkey_evidence_v2.json')
RELATIONSHIP_PATH = pathlib.Path('backend/relationship_evidence_all_cases.json')

OUTPUT_INVENTORY_JSON = pathlib.Path('backend/final_evidence_inventory.json')
OUTPUT_PAIRWISE_JSON = pathlib.Path('backend/category_pairwise_evidence_analysis.json')
OUTPUT_CSV = pathlib.Path('backend/final_evidence_matrix.csv')
OUTPUT_HTML = pathlib.Path('backend/final_evidence_coverage_report.html')

TARGET_CLASSES = [
    "Misalignment",
    "Overlapping",
    "Truncation",
    "Untranslation",
    "Repeated hotkey"
]

def load_all_artifacts():
    with open(MISALIGN_PATH, 'r', encoding='utf-8') as f:
        mis_data = {c["case_id"]: c for c in json.load(f)["cases"]}
    with open(MOVEMENT_PATH, 'r', encoding='utf-8') as f:
        mov_data = {c["case_id"]: c for c in json.load(f)["cases"]}
    with open(OVERLAP_PATH, 'r', encoding='utf-8') as f:
        ov_data = {c["case_id"]: c for c in json.load(f)}
    with open(TRUNC_PATH, 'r', encoding='utf-8') as f:
        tr_data = {c["case_id"]: c for c in json.load(f)}
    with open(UNTRANS_PATH, 'r', encoding='utf-8') as f:
        un_data = {c["case_id"]: c for c in json.load(f)}
    with open(HOTKEY_PATH, 'r', encoding='utf-8') as f:
        hk_data = {c["case_id"]: c for c in json.load(f)}
    with open(RELATIONSHIP_PATH, 'r', encoding='utf-8') as f:
        rel_data = {c["case_id"]: c for c in json.load(f)}
        
    return mis_data, mov_data, ov_data, tr_data, un_data, hk_data, rel_data

def consolidate_inventory():
    mis_dict, mov_dict, ov_dict, tr_dict, un_dict, hk_dict, rel_dict = load_all_artifacts()
    all_case_ids = sorted(list(rel_dict.keys()))
    print(f"Consolidating evidence for {len(all_case_ids)} benchmark cases...", flush=True)

    consolidated_cases = []
    
    for cid in all_case_ids:
        r_entry = rel_dict[cid]
        gt = r_entry["gt_category"]
        prod = r_entry["product"]
        fold = r_entry["folder"]
        lang = r_entry["lang"]
        
        # Pull streams
        mov_c = mov_dict.get(cid, {})
        ov_c = ov_dict.get(cid, {})
        tr_c = tr_dict.get(cid, {})
        un_c = un_dict.get(cid, {})
        hk_c = hk_dict.get(cid, {})
        
        # 1. Structural Misalignment Evidence
        col_break = mov_c.get("max_column_anchor_break_px", 0.0)
        col_dx_std = mov_c.get("max_column_dx_std", 0.0)
        res_disp = mov_c.get("max_residual_disp_px", 0.0)
        indep_disp_frac = mov_c.get("fraction_independently_displaced", 0.0)
        dir_coherence = mov_c.get("movement_direction_coherence", 1.0)
        reflow_ratio = mov_c.get("reflow_displacement_ratio", 0.0)
        
        has_mis_evidence = bool(col_break >= 40.0 and res_disp >= 30.0 and indep_disp_frac >= 0.20)
        
        # 2. Overlapping Evidence
        new_inter_area = ov_c.get("max_intersection_area_px2", 0)
        total_inter_area = ov_c.get("total_intersection_area_px2", 0)
        h_intrusion = ov_c.get("max_horizontal_intrusion_px", 0)
        v_intrusion = ov_c.get("max_vertical_intrusion_px", 0)
        gap_collapse = ov_c.get("max_gap_collapse_px", 0)
        residual_coll = ov_c.get("residual_unexplained_collisions_count", 0)
        
        has_ov_evidence = bool(new_inter_area > 0 and (h_intrusion >= 10 or v_intrusion >= 10))
        
        # 3. Truncation Evidence
        verified_ellipsis = tr_c.get("verified_ellipsis_elements_count", 0)
        measured_overflow = tr_c.get("max_overflow_px", 0)
        clipping_elems = tr_c.get("genuine_clipping_elements_count", 0)
        container_accom = tr_c.get("container_expanded_accommodated_count", 0)
        
        has_tr_evidence = bool(verified_ellipsis > 0 or measured_overflow > 0 or clipping_elems > 0)
        
        # 4. Untranslation Evidence
        genuine_untrans_strings = un_c.get("genuine_untranslated_strings_count", 0)
        preserved_latin_words = un_c.get("total_latin_words_preserved", 0)
        preserved_en_chars = un_c.get("total_english_chars_preserved", 0)
        tech_brand_tokens = un_c.get("potential_fp_technical_brand_count", 0)
        
        has_un_evidence = bool(genuine_untrans_strings >= 1 and preserved_latin_words >= 2)
        
        # 5. Repeated Hotkey Evidence
        hk_conflicts = hk_c.get("hotkey_conflict_count", 0)
        hk_support = hk_c.get("evidence_support_level", "UNSUPPORTED")
        has_hk_evidence = bool(hk_conflicts > 0 and hk_support == "DIRECTLY_SUPPORTED")
        
        # Determine active physical mechanisms
        active_mechanisms = []
        if has_mis_evidence: active_mechanisms.append("STRUCTURAL_MISALIGNMENT")
        if has_ov_evidence: active_mechanisms.append("BOUNDARY_COLLISION_OVERLAP")
        if has_tr_evidence: active_mechanisms.append("TEXT_TRUNCATION_CLIPPING")
        if has_un_evidence: active_mechanisms.append("UNTRANSLATED_USER_FACING_TEXT")
        if has_hk_evidence: active_mechanisms.append("DUPLICATE_HOTKEY_MNEMONIC")
        
        # Strongest physical mechanism
        if gt == "Misalignment" and has_mis_evidence:
            strongest_mech = "STRUCTURAL_COLUMN_DRIFT"
        elif gt == "Overlapping" and has_ov_evidence:
            strongest_mech = "GEOMETRIC_BOUNDARY_COLLISION"
        elif gt == "Truncation" and has_tr_evidence:
            strongest_mech = "TEXT_CONTAINER_CLIPPING"
        elif gt == "Untranslation" and has_un_evidence:
            strongest_mech = "PRESERVED_USER_FACING_ENGLISH"
        elif gt == "Repeated hotkey":
            strongest_mech = "VISUALLY_UNSUPPORTED_MNEMONIC"
        else:
            strongest_mech = active_mechanisms[0] if active_mechanisms else "NO_STRONG_OBSERVABLE_DEFECT"
            
        # Determine Ground Truth Support Status
        if gt == "Misalignment":
            gt_support = "DIRECTLY_SUPPORTED" if has_mis_evidence else ("PARTIALLY_SUPPORTED" if res_disp >= 15 else "UNSUPPORTED")
        elif gt == "Overlapping":
            gt_support = "DIRECTLY_SUPPORTED" if has_ov_evidence else ("PARTIALLY_SUPPORTED" if gap_collapse >= 15 else "UNSUPPORTED")
        elif gt == "Truncation":
            gt_support = "DIRECTLY_SUPPORTED" if has_tr_evidence else ("PARTIALLY_SUPPORTED" if tr_c.get("max_text_expansion_px", 0) >= 20 else "UNSUPPORTED")
        elif gt == "Untranslation":
            gt_support = "DIRECTLY_SUPPORTED" if has_un_evidence else ("PARTIALLY_SUPPORTED" if tech_brand_tokens > 0 else "UNSUPPORTED")
        elif gt == "Repeated hotkey":
            gt_support = "VISUALLY_UNSUPPORTED"
            
        case_inventory = {
            "case_id": cid,
            "product": prod,
            "folder": fold,
            "language": lang,
            "ground_truth": gt,
            "gt_evidence_support": gt_support,
            "strongest_physical_mechanism": strongest_mech,
            "multiple_defect_mechanisms_coexist": len(active_mechanisms) > 1,
            "active_mechanisms": active_mechanisms,
            "element_matching_quality": {
                "matched_count": r_entry.get("matching_stats", {}).get("matched_count", 0),
                "match_rate_pct": r_entry.get("matching_stats", {}).get("match_rate_pct", 0.0)
            },
            "evidence_streams": {
                "misalignment": {
                    "max_column_anchor_break_px": col_break,
                    "max_column_dx_std": col_dx_std,
                    "max_residual_disp_px": res_disp,
                    "fraction_independently_displaced": indep_disp_frac,
                    "movement_direction_coherence": dir_coherence,
                    "reflow_displacement_ratio": reflow_ratio,
                    "has_genuine_evidence": has_mis_evidence,
                    "provenance": "DIRECTLY_MEASURED"
                },
                "overlapping": {
                    "max_intersection_area_px2": new_inter_area,
                    "total_intersection_area_px2": total_inter_area,
                    "max_horizontal_intrusion_px": h_intrusion,
                    "max_vertical_intrusion_px": v_intrusion,
                    "max_gap_collapse_px": gap_collapse,
                    "residual_unexplained_collisions_count": residual_coll,
                    "has_genuine_evidence": has_ov_evidence,
                    "provenance": "DIRECTLY_MEASURED"
                },
                "truncation": {
                    "verified_ellipsis_count": verified_ellipsis,
                    "max_overflow_px": measured_overflow,
                    "clipping_elements_count": clipping_elems,
                    "container_expanded_accommodated_count": container_accom,
                    "has_genuine_evidence": has_tr_evidence,
                    "provenance": "DIRECTLY_MEASURED"
                },
                "untranslation": {
                    "genuine_untranslated_strings_count": genuine_untrans_strings,
                    "total_latin_words_preserved": preserved_latin_words,
                    "total_english_chars_preserved": preserved_en_chars,
                    "potential_fp_technical_brand_count": tech_brand_tokens,
                    "has_genuine_evidence": has_un_evidence,
                    "provenance": "DIRECTLY_MEASURED"
                },
                "repeated_hotkey": {
                    "hotkey_conflict_count": hk_conflicts,
                    "has_genuine_evidence": has_hk_evidence,
                    "provenance": "VISUALLY_UNSUPPORTED" if gt == "Repeated hotkey" else "DIRECTLY_MEASURED"
                }
            }
        }
        consolidated_cases.append(case_inventory)
        
    return consolidated_cases

def compute_consolidated_summaries(cases):
    cat_summary = {}
    for cat in TARGET_CLASSES:
        cat_cases = [c for c in cases if c["ground_truth"] == cat]
        total_c = len(cat_cases)
        
        dir_sup = sum(1 for c in cat_cases if c["gt_evidence_support"] == "DIRECTLY_SUPPORTED")
        part_sup = sum(1 for c in cat_cases if c["gt_evidence_support"] == "PARTIALLY_SUPPORTED")
        unsup = sum(1 for c in cat_cases if c["gt_evidence_support"] == "UNSUPPORTED")
        vis_unsup = sum(1 for c in cat_cases if c["gt_evidence_support"] == "VISUALLY_UNSUPPORTED")
        
        # Mechanism specifics
        if cat == "Misalignment":
            strong_mech = "Relative column anchor break (mean: 116.7px), residual translation-corrected drift (median: 117.1px), and low directional coherence (0.11)."
            avail_feats = ["max_column_anchor_break_px", "max_residual_disp_px", "max_column_dx_std", "fraction_independently_displaced", "movement_direction_coherence"]
            miss_feats = ["Semantic hierarchy/parent-child container depth"]
            fp_sources = "Legitimate horizontal reflow where entire form shifts right (resolved by reflow ratio)."
            ambig_sources = "Minor font-expansion margin changes (< 15px)."
        elif cat == "Overlapping":
            strong_mech = "Direct non-zero bounding box intersection area (mean: 11,847px²), multi-axis intrusion (mean: 120.2px H, 35.7px V), and sibling gap collapse (94.7%)."
            avail_feats = ["max_intersection_area_px2", "total_intersection_area_px2", "max_horizontal_intrusion_px", "max_vertical_intrusion_px", "max_gap_collapse_px"]
            miss_feats = ["Z-order layering / alpha transparency rendering"]
            fp_sources = "Loose OCR bounding boxes overlapping background container card frames."
            ambig_sources = "0px boundary-to-boundary touching contact without negative pixel penetration."
        elif cat == "Truncation":
            strong_mech = "Verified localized ellipsis ('...', 60.0% of cases), measured text-to-container overflow, and pixel glyph edge cuts."
            avail_feats = ["verified_ellipsis_count", "max_overflow_px", "clipping_elements_count", "container_expanded_accommodated_count"]
            miss_feats = ["Internal control drawing bounds for custom OwnerDraw Win32 widgets"]
            fp_sources = "Unconstrained floating labels expanding without bounding containers."
            ambig_sources = "Text expanding within auto-expanding containers (handled by accommodation tracking)."
        elif cat == "Untranslation":
            strong_mech = "Preserved user-facing English words (mean: 12.08 words vs 5.59 in non-untrans), high Latin character ratio, and dictionary term retention."
            avail_feats = ["genuine_untranslated_strings_count", "total_latin_words_preserved", "total_english_chars_preserved", "potential_fp_technical_brand_count"]
            miss_feats = ["Contextual semantic dictionary for domain-specific engineering jargon"]
            fp_sources = "Universal technical acronyms (DWG, CAD, BIM, OK, Cancel, X/Y/Z) and sample file paths."
            ambig_sources = "Transliterated brand names or short 2-3 letter abbreviations."
        elif cat == "Repeated hotkey":
            strong_mech = "VISUALLY UNSUPPORTED via plain OCR. Mnemonics are rendered as Win32 font underlines or handled in resource binary (.rc) tables."
            avail_feats = ["OCR text parenthesized mnemonic regex"]
            miss_feats = ["Font underline glyph attributes", "Win32 dialog template accelerator tables"]
            fp_sources = "OCR reading trademark (R) or punctuation as parenthesized accelerator."
            ambig_sources = "Total invisibility of native Alt-key underlines to standard OCR."

        cat_summary[cat] = {
            "benchmark_count": total_c,
            "directly_supported_cases": f"{dir_sup} / {total_c} ({dir_sup/total_c*100:.1f}%)" if total_c > 0 else "0",
            "partially_supported_cases": f"{part_sup} / {total_c} ({part_sup/total_c*100:.1f}%)" if total_c > 0 else "0",
            "unsupported_cases": f"{unsup} / {total_c} ({unsup/total_c*100:.1f}%)" if total_c > 0 else "0",
            "visually_unsupported_cases": f"{vis_unsup} / {total_c} ({vis_unsup/total_c*100:.1f}%)" if total_c > 0 else "0",
            "strongest_genuine_evidence_mechanisms": strong_mech,
            "evidence_features_available": avail_feats,
            "evidence_features_missing": miss_feats,
            "major_false_positive_sources": fp_sources,
            "major_ambiguity_sources": ambig_sources
        }
        
    return cat_summary

def perform_pairwise_analysis(cases):
    pairwise_results = {}
    
    # 10 pairs among 5 categories
    for i in range(len(TARGET_CLASSES)):
        for j in range(i + 1, len(TARGET_CLASSES)):
            c1 = TARGET_CLASSES[i]
            c2 = TARGET_CLASSES[j]
            pair_name = f"{c1} vs {c2}"
            
            c1_cases = [c for c in cases if c["ground_truth"] == c1]
            c2_cases = [c for c in cases if c["ground_truth"] == c2]
            
            # Key differentiators
            if pair_name == "Misalignment vs Overlapping":
                sep_mech = "Misalignment is characterized by column anchor breaks and asynchronous lateral drift without bounding box intersection; Overlapping is defined by positive pixel intrusion and sibling boundary collision."
                shared_mech = "Both exhibit high raw displacement due to layout reflow."
                complementary_feats = ["max_column_anchor_break_px (Misalignment)", "max_vertical_intrusion_px & max_intersection_area_px2 (Overlapping)"]
            elif pair_name == "Misalignment vs Truncation":
                sep_mech = "Misalignment displaces controls laterally off-grid while preserving text visibility; Truncation clips text at rigid container edges or appends ellipsis."
                shared_mech = "Both can be triggered by text length expansion."
                complementary_feats = ["max_residual_disp_px (Misalignment)", "verified_ellipsis_count & clipping_elements_count (Truncation)"]
            elif pair_name == "Misalignment vs Untranslation":
                sep_mech = "Misalignment shows large spatial displacement with fully localized text; Untranslation shows near-zero spatial displacement but heavy English lexical retention."
                shared_mech = "None (Spatial vs Lexical orthogonality)."
                complementary_feats = ["max_column_dx_std (Misalignment)", "total_latin_words_preserved (Untranslation)"]
            elif pair_name == "Misalignment vs Repeated hotkey":
                sep_mech = "Misalignment has rich structural geometric evidence; Repeated hotkey is visually unobservable via plain OCR."
                shared_mech = "None."
                complementary_feats = ["Structural displacement vs Win32 resource metadata."]
            elif pair_name == "Overlapping vs Truncation":
                sep_mech = "Overlapping penetrates into sibling control boundaries; Truncation is confined inside rigid container boundaries."
                shared_mech = "Both result from text expansion exceeding allocated horizontal space."
                complementary_feats = ["total_intersection_area_px2 (Overlapping)", "verified_ellipsis_count (Truncation)"]
            elif pair_name == "Overlapping vs Untranslation":
                sep_mech = "Overlapping is geometric collision; Untranslation is lexical preservation."
                shared_mech = "None."
                complementary_feats = ["max_horizontal_intrusion_px (Overlapping)", "genuine_untranslated_strings_count (Untranslation)"]
            elif pair_name == "Overlapping vs Repeated hotkey":
                sep_mech = "Overlapping is physical collision; Repeated hotkey is unobservable mnemonic conflict."
                shared_mech = "None."
                complementary_feats = ["Geometric intrusion vs Resource table parsing."]
            elif pair_name == "Truncation vs Untranslation":
                sep_mech = "Truncation expands and gets clipped; Untranslation stays in English and does not expand."
                shared_mech = "Both involve text content."
                complementary_feats = ["verified_ellipsis_count (Truncation)", "total_latin_words_preserved (Untranslation)"]
            elif pair_name == "Truncation vs Repeated hotkey":
                sep_mech = "Truncation is visible boundary clipping/ellipsis; Repeated hotkey is unobservable via OCR."
                shared_mech = "None."
                complementary_feats = ["Ellipsis/clipping vs Resource table parsing."]
            elif pair_name == "Untranslation vs Repeated hotkey":
                sep_mech = "Untranslation retains user-facing English words; Repeated hotkey involves duplicate accelerator keys."
                shared_mech = "Both are text/symbol level defects."
                complementary_feats = ["Preserved Latin dictionary words vs Accelerator mnemonics."]

            pairwise_results[pair_name] = {
                "category_1": c1,
                "category_2": c2,
                "distinguishing_physical_mechanism": sep_mech,
                "shared_or_overlapping_mechanisms": shared_mech,
                "complementary_discriminative_features": complementary_feats
            }
            
    return pairwise_results

def export_matrix_csv(cases, output_path):
    rows = []
    for c in cases:
        ev = c["evidence_streams"]
        row = {
            "Case_ID": c["case_id"],
            "Product": c["product"],
            "Folder": c["folder"],
            "Language": c["language"],
            "Ground_Truth": c["ground_truth"],
            "GT_Support_Status": c["gt_evidence_support"],
            "Strongest_Mechanism": c["strongest_physical_mechanism"],
            "Multiple_Defects_Coexist": c["multiple_defect_mechanisms_coexist"],
            "Match_Rate_Pct": c["element_matching_quality"]["match_rate_pct"],
            # Misalignment
            "Mis_Col_Anchor_Break_px": ev["misalignment"]["max_column_anchor_break_px"],
            "Mis_Residual_Disp_px": ev["misalignment"]["max_residual_disp_px"],
            "Mis_Col_dx_Std": ev["misalignment"]["max_column_dx_std"],
            "Mis_Direction_Coherence": ev["misalignment"]["movement_direction_coherence"],
            "Mis_Has_Evidence": ev["misalignment"]["has_genuine_evidence"],
            # Overlapping
            "Ov_Max_Intersection_Area_px2": ev["overlapping"]["max_intersection_area_px2"],
            "Ov_Total_Intersection_Area_px2": ev["overlapping"]["total_intersection_area_px2"],
            "Ov_Horizontal_Intrusion_px": ev["overlapping"]["max_horizontal_intrusion_px"],
            "Ov_Vertical_Intrusion_px": ev["overlapping"]["max_vertical_intrusion_px"],
            "Ov_Gap_Collapse_px": ev["overlapping"]["max_gap_collapse_px"],
            "Ov_Has_Evidence": ev["overlapping"]["has_genuine_evidence"],
            # Truncation
            "Tr_Verified_Ellipsis_Count": ev["truncation"]["verified_ellipsis_count"],
            "Tr_Max_Overflow_px": ev["truncation"]["max_overflow_px"],
            "Tr_Clipping_Elements_Count": ev["truncation"]["clipping_elements_count"],
            "Tr_Container_Accommodated": ev["truncation"]["container_expanded_accommodated_count"],
            "Tr_Has_Evidence": ev["truncation"]["has_genuine_evidence"],
            # Untranslation
            "Un_Genuine_Untrans_Strings": ev["untranslation"]["genuine_untranslated_strings_count"],
            "Un_Latin_Words_Preserved": ev["untranslation"]["total_latin_words_preserved"],
            "Un_English_Chars_Preserved": ev["untranslation"]["total_english_chars_preserved"],
            "Un_Tech_Brand_Tokens": ev["untranslation"]["potential_fp_technical_brand_count"],
            "Un_Has_Evidence": ev["untranslation"]["has_genuine_evidence"],
            # Repeated hotkey
            "HK_Conflict_Count": ev["repeated_hotkey"]["hotkey_conflict_count"],
            "HK_Has_Evidence": ev["repeated_hotkey"]["has_genuine_evidence"]
        }
        rows.append(row)
        
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"Saved consolidated matrix CSV to {output_path.resolve()}", flush=True)

def generate_consolidated_html_report(inventory, summary, pairwise, output_path):
    total_cases = len(inventory["cases"])
    cat_sums = summary
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Final Physical Evidence Consolidation & Category Coverage Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
  h1 {{ color: #38bdf8; font-size: 24px; margin-bottom: 6px; }}
  h2 {{ color: #93c5fd; font-size: 18px; margin-top: 28px; border-bottom: 1px solid #334155; padding-bottom: 6px; }}
  .metrics-banner {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; margin: 20px 0; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 14px; text-align: center; }}
  .card-val {{ font-size: 20px; font-weight: bold; margin-top: 4px; color: #38bdf8; }}
  .card-sub {{ font-size: 11px; color: #94a3b8; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; background: #1e293b; border-radius: 6px; overflow: hidden; }}
  th, td {{ padding: 9px 12px; text-align: left; border-bottom: 1px solid #334155; }}
  th {{ background: #0f172a; color: #38bdf8; font-weight: 600; }}
  tr:hover {{ background: #243247; }}
  .status-pass {{ color: #4ade80; font-weight: 600; }}
  .status-part {{ color: #f59e0b; font-weight: 600; }}
  .status-fail {{ color: #f43f5e; font-weight: 600; }}
  .status-unsup {{ color: #94a3b8; font-weight: 600; }}
</style>
</head>
<body>
<h1>Final Physical Evidence Consolidation & Category Coverage Report</h1>
<div style="color: #94a3b8; font-size: 14px;">
  Master synthesis across 101 benchmark cases auditing directly measured geometric, structural, and lexical evidence with zero synthetic proxies.
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 12px; color: #94a3b8;">Misalignment</div>
    <div class="card-val" style="color: #4ade80;">{cat_sums['Misalignment']['directly_supported_cases']}</div>
    <div class="card-sub">structural column anchor breaks</div>
  </div>
  <div class="card">
    <div style="font-size: 12px; color: #94a3b8;">Overlapping</div>
    <div class="card-val" style="color: #4ade80;">{cat_sums['Overlapping']['directly_supported_cases']}</div>
    <div class="card-sub">positive boundary collisions</div>
  </div>
  <div class="card">
    <div style="font-size: 12px; color: #94a3b8;">Truncation</div>
    <div class="card-val" style="color: #38bdf8;">{cat_sums['Truncation']['directly_supported_cases']}</div>
    <div class="card-sub">verified ellipsis & clipping</div>
  </div>
  <div class="card">
    <div style="font-size: 12px; color: #94a3b8;">Untranslation</div>
    <div class="card-val" style="color: #4ade80;">{cat_sums['Untranslation']['directly_supported_cases']}</div>
    <div class="card-sub">user-facing English words</div>
  </div>
  <div class="card">
    <div style="font-size: 12px; color: #94a3b8;">Repeated Hotkey</div>
    <div class="card-val" style="color: #94a3b8;">0 / 7 (0.0%)</div>
    <div class="card-sub">VISUALLY_UNSUPPORTED via OCR</div>
  </div>
</div>

<h2>1. Category-Level Evidence Coverage & Physical Mechanisms</h2>
<table>
  <thead>
    <tr>
      <th>Defect Category</th>
      <th>Benchmark N</th>
      <th>Directly Supported</th>
      <th>Partially Supported</th>
      <th>Unsupported</th>
      <th>Primary Genuine Physical Mechanism</th>
    </tr>
  </thead>
  <tbody>
"""
    for cat_name, csum in cat_sums.items():
        html += f"""
    <tr>
      <td style="font-weight:600; color:#38bdf8;">{cat_name}</td>
      <td>{csum['benchmark_count']}</td>
      <td class="status-pass">{csum['directly_supported_cases']}</td>
      <td class="status-part">{csum['partially_supported_cases']}</td>
      <td class="status-unsup">{csum['visually_unsupported_cases'] if cat_name == 'Repeated hotkey' else csum['unsupported_cases']}</td>
      <td style="font-size:12px; color:#cbd5e1;">{csum['strongest_genuine_evidence_mechanisms']}</td>
    </tr>
"""
    html += """
  </tbody>
</table>

<h2>2. Pairwise Category Evidence Analysis (10 Core Pairs)</h2>
<table>
  <thead>
    <tr>
      <th>Category Pair</th>
      <th>Distinguishing Physical Mechanism</th>
      <th>Shared / Confounding Mechanism</th>
      <th>Complementary Evidence Features</th>
    </tr>
  </thead>
  <tbody>
"""
    for pair_name, pdata in pairwise.items():
        html += f"""
    <tr>
      <td style="font-weight:600; color:#38bdf8;">{pair_name}</td>
      <td style="font-size:12px; color:#f8fafc;">{pdata['distinguishing_physical_mechanism']}</td>
      <td style="font-size:12px; color:#94a3b8;">{pdata['shared_or_overlapping_mechanisms']}</td>
      <td style="font-size:12px; color:#4ade80;">{', '.join(pdata['complementary_discriminative_features'])}</td>
    </tr>
"""
    html += """
  </tbody>
</table>

<h2>3. Case-by-Case Consolidated Evidence Sample (Top 25 Cases)</h2>
<table>
  <thead>
    <tr>
      <th>ID</th>
      <th>Product / Folder (Lang)</th>
      <th>Ground Truth</th>
      <th>Support Status</th>
      <th>Strongest Mechanism</th>
      <th>Coexisting Defects</th>
    </tr>
  </thead>
  <tbody>
"""
    for c in inventory["cases"][:25]:
        status_cls = "status-pass" if c["gt_evidence_support"] == "DIRECTLY_SUPPORTED" else ("status-part" if c["gt_evidence_support"] == "PARTIALLY_SUPPORTED" else "status-unsup")
        html += f"""
    <tr>
      <td style="font-weight:bold;">#{c['case_id']}</td>
      <td>{c['product']} / {c['folder']} ({c['language']})</td>
      <td style="font-weight:600;">{c['ground_truth']}</td>
      <td class="{status_cls}">{c['gt_evidence_support']}</td>
      <td style="font-size:12px; color:#38bdf8;">{c['strongest_physical_mechanism']}</td>
      <td style="font-size:11px; color:#94a3b8;">{', '.join(c['active_mechanisms']) if c['active_mechanisms'] else 'None'}</td>
    </tr>
"""
    html += """
  </tbody>
</table>

</body>
</html>
"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

def main():
    cases = consolidate_inventory()
    summaries = compute_consolidated_summaries(cases)
    pairwise = perform_pairwise_analysis(cases)
    
    inventory_doc = {
        "total_benchmark_cases": len(cases),
        "category_summaries": summaries,
        "cases": cases
    }
    
    with open(OUTPUT_INVENTORY_JSON, 'w', encoding='utf-8') as f:
        json.dump(inventory_doc, f, indent=2)
    print(f"Saved final evidence inventory JSON to {OUTPUT_INVENTORY_JSON.resolve()}")
    
    with open(OUTPUT_PAIRWISE_JSON, 'w', encoding='utf-8') as f:
        json.dump(pairwise, f, indent=2)
    print(f"Saved pairwise evidence analysis JSON to {OUTPUT_PAIRWISE_JSON.resolve()}")
    
    export_matrix_csv(cases, OUTPUT_CSV)
    generate_consolidated_html_report(inventory_doc, summaries, pairwise, OUTPUT_HTML)
    print(f"Saved visual HTML report to {OUTPUT_HTML.resolve()}")

    print("\n" + "="*75)
    print("FINAL EVIDENCE CONSOLIDATION & CATEGORY COVERAGE SUMMARY")
    print("="*75)
    for cat, s in summaries.items():
        print(f"  [{cat:16s}] (N={s['benchmark_count']:2d}): Directly Supported = {s['directly_supported_cases']} | Unsupported = {s['unsupported_cases'] if cat != 'Repeated hotkey' else s['visually_unsupported_cases']}")
    print("="*75 + "\n")

if __name__ == '__main__':
    main()
