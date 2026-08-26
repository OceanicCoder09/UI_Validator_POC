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

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from backend.cv_engine import analyze_localization_quality

EXCEL_PATH = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize/Screenshot data list from Welocalize.xlsx')
BASE_DATA_ROOT = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize')
OUTPUT_JSON = pathlib.Path('backend/evidence_validation_report.json')
OUTPUT_HTML = pathlib.Path('backend/evidence_validation_report.html')

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

def audit_finding_evidence(f, title, desc, cat, loc):
    """
    Traces finding evidence back to the originating code path in cv_engine.py.
    Determines whether measurements are DIRECTLY_MEASURED, DERIVED_FROM_MEASUREMENT, or FALLBACK/ESTIMATED.
    """
    ev = f.get("evidence", {})
    bw, bh = loc.get("width", 10), loc.get("height", 10)
    
    provenance_details = {}
    is_fallback = False
    is_directly_measured = False
    is_derived = False
    
    # 1. Truncation Checks
    if cat == "TRUNCATION":
        # Check if ellipsis was genuinely detected in crop or OCR
        has_ellipsis = ev.get("has_ellipsis", False)
        overflow_val = ev.get("overflow_px")
        
        if "Text Cut Short with Ellipsis" in title or has_ellipsis:
            is_directly_measured = True
            provenance_details["overflow_px"] = "DIRECTLY_MEASURED (Ellipsis glyph '...' detected in OCR string/pixel strip)"
        elif overflow_val == int(max(4, bw - 20)):
            # This came from fallback line 1246: ev["overflow_px"] = int(max(4, bw - 20))
            is_fallback = True
            provenance_details["overflow_px"] = f"FALLBACK_FORMULA: max(4, bw - 20) -> {overflow_val}px (fabricated from bounding box width)"
        elif overflow_val is not None:
            is_derived = True
            provenance_details["overflow_px"] = f"DERIVED_FROM_MEASUREMENT: {overflow_val}px overflow past container boundary"
        else:
            is_fallback = True
            provenance_details["overflow_px"] = "FALLBACK/ESTIMATED"

    # 2. Overlapping Checks
    elif cat == "OVERLAPPING":
        overlap_val = ev.get("overlap_pixels")
        if overlap_val == int(max(2, bw // 3)):
            # Fallback line 1255: ev["overlap_pixels"] = int(max(2, bw // 3))
            is_fallback = True
            provenance_details["overlap_pixels"] = f"FALLBACK_FORMULA: max(2, bw // 3) -> {overlap_val}px (fabricated from bounding box width)"
        elif "overlaps" in desc or "collides" in desc:
            # Directly measured collision in line 834 or 863
            is_directly_measured = True
            provenance_details["overlap_pixels"] = f"DIRECTLY_MEASURED: {overlap_val}px actual horizontal collision in line intersection detector"
        else:
            is_derived = True
            provenance_details["overlap_pixels"] = f"DERIVED_FROM_MEASUREMENT: {overlap_val}px"

    # 3. Misalignment Checks
    elif cat == "MISSALIGNMENT":
        shift_val = ev.get("position_shift_x")
        if shift_val == int(max(4, abs(bw - 20))):
            # Fallback line 1261: ev["position_shift_x"] = int(max(4, abs(bw - 20)))
            is_fallback = True
            provenance_details["position_shift_x"] = f"FALLBACK_FORMULA: max(4, abs(bw - 20)) -> {shift_val}px (fabricated from bounding box width)"
        elif "shifted horizontally by" in desc or "Left Anchor Shift" in title:
            is_directly_measured = True
            provenance_details["position_shift_x"] = f"DIRECTLY_MEASURED: {shift_val}px column anchor displacement measured against baseline"
        else:
            is_derived = True
            provenance_details["position_shift_x"] = f"DERIVED_FROM_MEASUREMENT: {shift_val}px"

    # 4. Untranslation Checks
    elif cat == "UNTRANSLATION":
        words = ev.get("untranslated_words", [])
        if "English Text" in title or "is identical to English baseline" in desc:
            is_directly_measured = True
            provenance_details["untranslated_words"] = f"DIRECTLY_MEASURED: Exact token match with English baseline vocabulary ({len(words)} words)"
        else:
            is_derived = True
            provenance_details["untranslated_words"] = f"DERIVED_FROM_MEASUREMENT: {len(words)} words"

    # 5. Hotkey Defect Checks
    elif cat == "HOTKEY_DEFECT":
        if "Duplicate Accelerator" in title:
            is_directly_measured = True
            provenance_details["hotkey_type"] = "DIRECTLY_MEASURED: Duplicate accelerator regex collision"
        else:
            is_derived = True
            provenance_details["hotkey_type"] = "DERIVED_FROM_MEASUREMENT: Hotkey regex analysis"
            
    # 6. Miscellaneous / Fallbacks
    elif cat == "MISC":
        is_derived = True
        provenance_details["control_count_delta"] = f"DERIVED_FROM_MEASUREMENT: header count diff"
    else:
        is_fallback = True
        provenance_details["general"] = "FALLBACK/ESTIMATED"

    if is_directly_measured:
        evidence_tier = "DIRECTLY_MEASURED"
    elif is_derived:
        evidence_tier = "DERIVED_FROM_MEASUREMENT"
    else:
        evidence_tier = "FALLBACK/ESTIMATED"

    # Evaluate whether evidence directly supports the detected category
    # A category is supported ONLY if it contains directly measured physical phenomena matching that defect
    if cat == "TRUNCATION":
        supports_category = (ev.get("has_ellipsis", False) is True) or ("Boundary Border Clipping" in title) or (ev.get("overflow_px", 0) > 0 and not is_fallback)
    elif cat == "OVERLAPPING":
        supports_category = (not is_fallback) and ("Text Labels Colliding" in title or "Colliding with Adjacent Control" in title or "Spilling into" in title)
    elif cat == "MISSALIGNMENT":
        supports_category = (not is_fallback) and ("Column Shift" in title or "Anchor Shift" in title or "Layout Column Alignment" in title)
    elif cat == "UNTRANSLATION":
        supports_category = ("English Text" in title or "identical to English baseline" in desc)
    elif cat == "HOTKEY_DEFECT":
        supports_category = ("Duplicate Accelerator" in title or "Invalid Hotkey" in title)
    else:
        supports_category = False

    return evidence_tier, provenance_details, supports_category

def run_evidence_audit(records):
    print("Running cv_engine.py analysis across 101 benchmark cases for evidence validation...", flush=True)
    
    validation_records = []
    
    total_findings_count = 0
    directly_measured_count = 0
    derived_count = 0
    fallback_count = 0
    supported_findings_count = 0
    unsupported_findings_count = 0
    
    gt_supported_cases = 0
    
    t0 = time.time()
    
    for i, r in enumerate(records):
        img_en = cv2.imread(r["en_path"])
        img_loc = cv2.imread(r["loc_path"])
        
        # Run existing unmodified cv_engine pipeline
        cv_result = analyze_localization_quality(img_en, img_loc)
        raw_findings = cv_result.get("findings", [])
        
        case_findings_audited = []
        gt_category_matched_genuinely = False
        
        for f_idx, f in enumerate(raw_findings):
            total_findings_count += 1
            f_id = f.get("id", f"ERR-{f_idx+1:04d}")
            cat = f.get("category", "UNKNOWN_ERROR")
            title = f.get("title", "")
            desc = f.get("description", "")
            loc = f.get("location", {"x": 0, "y": 0, "width": 10, "height": 10})
            ev = f.get("evidence", {})
            
            tier, provenance, supports_cat = audit_finding_evidence(f, title, desc, cat, loc)
            
            if tier == "DIRECTLY_MEASURED":
                directly_measured_count += 1
            elif tier == "DERIVED_FROM_MEASUREMENT":
                derived_count += 1
            else:
                fallback_count += 1
                
            if supports_cat:
                supported_findings_count += 1
            else:
                unsupported_findings_count += 1
                
            # Check if this finding matches GT category with genuine supporting evidence
            norm_gt = r["gt_category"].upper().replace(" ", "_")
            if norm_gt in {"REPEATED_HOTKEY", "INCORRECT_HOTKEY"}:
                norm_gt = "HOTKEY_DEFECT"
            if norm_gt in {"MISALIGNMENT"}:
                norm_gt = "MISSALIGNMENT"
                
            if cat == norm_gt and supports_cat and tier != "FALLBACK/ESTIMATED":
                gt_category_matched_genuinely = True
                
            case_findings_audited.append({
                "finding_id": f_id,
                "detected_category": cat,
                "title": title,
                "location": loc,
                "evidence_object": ev,
                "evidence_tier": tier,
                "provenance_trace": provenance,
                "affected_ocr_elements": ev.get("localized_text", []),
                "supports_detected_category": bool(supports_cat),
                "is_fallback_formula": bool(tier == "FALLBACK/ESTIMATED")
            })
            
        if gt_category_matched_genuinely:
            gt_supported_cases += 1
            
        validation_records.append({
            "case_id": r["case_id"],
            "product": r["product"],
            "folder": r["folder"],
            "lang": r["lang"],
            "ground_truth_category": r["gt_category"],
            "total_findings_in_case": len(raw_findings),
            "has_genuine_gt_finding": bool(gt_category_matched_genuinely),
            "findings": case_findings_audited
        })
        
        if (i + 1) % 20 == 0 or (i + 1) == len(records):
            print(f"  Audited {i+1}/{len(records)} cases ({total_findings_count} findings audited in {time.time()-t0:.1f}s)", flush=True)

    summary_stats = {
        "total_cases_evaluated": len(records),
        "total_findings_audited": total_findings_count,
        "directly_measured_findings": directly_measured_count,
        "derived_findings": derived_count,
        "fallback_estimated_findings": fallback_count,
        "findings_with_genuinely_supporting_evidence": supported_findings_count,
        "findings_not_supported_by_evidence": unsupported_findings_count,
        "cases_with_genuine_supporting_gt_evidence": gt_supported_cases,
        "cases_without_genuine_supporting_gt_evidence": len(records) - gt_supported_cases
    }
    
    return summary_stats, validation_records

def generate_validation_html_report(summary, records, output_path):
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>CV Engine Evidence Validation & Provenance Audit</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
  h1 {{ color: #38bdf8; font-size: 24px; margin-bottom: 6px; }}
  h2 {{ color: #93c5fd; font-size: 18px; margin-top: 28px; border-bottom: 1px solid #334155; padding-bottom: 6px; }}
  .metrics-banner {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 20px 0; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; text-align: center; }}
  .card-val {{ font-size: 26px; font-weight: bold; margin-top: 4px; }}
  .card-sub {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
  .case-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; margin-bottom: 24px; padding: 18px; }}
  .case-header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 10px; margin-bottom: 12px; }}
  .gt-badge {{ background: #831843; border: 1px solid #f43f5e; color: #ffe4e6; font-weight: 600; padding: 4px 10px; border-radius: 6px; font-size: 13px; }}
  .status-pass {{ background: #064e3b; border: 1px solid #10b981; color: #a7f3d0; font-weight: 600; padding: 4px 10px; border-radius: 6px; font-size: 13px; }}
  .status-fail {{ background: #450a0a; border: 1px solid #ef4444; color: #fecaca; font-weight: 600; padding: 4px 10px; border-radius: 6px; font-size: 13px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; background: #0f172a; border-radius: 6px; overflow: hidden; }}
  th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid #334155; }}
  th {{ background: #020617; color: #38bdf8; font-weight: 600; }}
  tr:hover {{ background: #1e293b; }}
  .tier-direct {{ color: #4ade80; font-weight: bold; }}
  .tier-derived {{ color: #38bdf8; }}
  .tier-fallback {{ color: #f43f5e; font-weight: bold; background: #450a0a; padding: 2px 6px; border-radius: 4px; }}
  .tag-supported {{ color: #4ade80; font-weight: bold; }}
  .tag-unsupported {{ color: #f43f5e; font-weight: bold; }}
</style>
</head>
<body>
<h1>CV Engine Evidence Validation & Provenance Audit Report</h1>
<div style="color: #94a3b8; font-size: 14px;">
  Rigorous code-provenance tracing of all candidate finding measurements produced by <code>cv_engine.py</code> across 101 benchmark cases.
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Total Findings Audited</div>
    <div class="card-val" style="color: #f8fafc;">{summary['total_findings_audited']}</div>
    <div class="card-sub">across {summary['total_cases_evaluated']} cases</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Directly Measured</div>
    <div class="card-val" style="color: #4ade80;">{summary['directly_measured_findings']} ({summary['directly_measured_findings']/max(1,summary['total_findings_audited'])*100:.1f}%)</div>
    <div class="card-sub">genuine physical OCR/pixel measurement</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Fallback / Fabricated Formulations</div>
    <div class="card-val" style="color: #f43f5e;">{summary['fallback_estimated_findings']} ({summary['fallback_estimated_findings']/max(1,summary['total_findings_audited'])*100:.1f}%)</div>
    <div class="card-sub">e.g. max(4, bw - 20) or bw // 3</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Cases with Genuine GT Evidence</div>
    <div class="card-val" style="color: #38bdf8;">{summary['cases_with_genuine_supporting_gt_evidence']} / {summary['total_cases_evaluated']} ({summary['cases_with_genuine_supporting_gt_evidence']/max(1,summary['total_cases_evaluated'])*100:.1f}%)</div>
    <div class="card-sub">supported GT present without fallback</div>
  </div>
</div>

<h2>Audit Breakdown by Case (GT &rarr; Finding &rarr; Evidence Provenance)</h2>
"""
    for c in records:
        status_badge = "<span class='status-pass'>[PASS] Genuine GT Evidence Present</span>" if c["has_genuine_gt_finding"] else "<span class='status-fail'>[FAIL] No Genuine GT Evidence</span>"
        html += f"""
<div class="case-card">
  <div class="case-header">
    <div>
      <span style="font-size:16px; font-weight:600; color:#f8fafc;">Case #{c['case_id']}: {c['product']} / {c['folder']} ({c['lang']})</span>
      <span class="gt-badge" style="margin-left: 10px;">GT Category: {c['ground_truth_category']}</span>
    </div>
    <div>
      {status_badge}
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th>Finding ID</th>
        <th>Detected Category</th>
        <th>Title / Defect Description</th>
        <th>Bounding Box</th>
        <th>Evidence Tier</th>
        <th>Evidence Provenance & Verification</th>
        <th>Supports Category?</th>
      </tr>
    </thead>
    <tbody>
"""
        if not c["findings"]:
            html += "<tr><td colspan='7' style='text-align:center; color:#94a3b8;'>Zero findings detected by cv_engine.</td></tr>"
        else:
            for f in c["findings"]:
                tier_cls = "tier-direct" if f["evidence_tier"] == "DIRECTLY_MEASURED" else ("tier-derived" if f["evidence_tier"] == "DERIVED_FROM_MEASUREMENT" else "tier-fallback")
                supp_cls = "<span class='tag-supported'>YES (Supported)</span>" if f["supports_detected_category"] else "<span class='tag-unsupported'>NO (Unsupported)</span>"
                loc = f["location"]
                loc_str = f"x={loc.get('x',0)}, y={loc.get('y',0)}, w={loc.get('width',0)}, h={loc.get('height',0)}"
                
                prov_lines = "<br>".join([f"<strong>{k}:</strong> {v}" for k, v in f["provenance_trace"].items()])
                html += f"""
      <tr>
        <td style="font-family:monospace; font-weight:bold;">{f['finding_id']}</td>
        <td style="font-weight:600;">{f['detected_category']}</td>
        <td>{f['title']}</td>
        <td style="font-family:monospace; font-size:12px;">{loc_str}</td>
        <td><span class="{tier_cls}">{f['evidence_tier']}</span></td>
        <td style="font-size:12px;">{prov_lines}</td>
        <td>{supp_cls}</td>
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
    with open(output_path, "w", encoding="utf-8") as out_f:
        out_f.write(html)

def main():
    records = load_benchmark_cases()
    print(f"Loaded {len(records)} cases across 5 target categories for cv_engine evidence audit.")
    
    summary, val_records = run_evidence_audit(records)
    
    print("\n" + "="*75)
    print("EVIDENCE VALIDATION & PROVENANCE AUDIT SUMMARY")
    print("="*75)
    print(f"Total Benchmark Cases Evaluated           : {summary['total_cases_evaluated']}")
    print(f"Total Findings Audited                   : {summary['total_findings_audited']}")
    print(f"  - DIRECTLY_MEASURED Findings           : {summary['directly_measured_findings']} ({summary['directly_measured_findings']/max(1,summary['total_findings_audited'])*100:.1f}%)")
    print(f"  - DERIVED_FROM_MEASUREMENT Findings    : {summary['derived_findings']} ({summary['derived_findings']/max(1,summary['total_findings_audited'])*100:.1f}%)")
    print(f"  - FALLBACK/ESTIMATED (Fabricated)      : {summary['fallback_estimated_findings']} ({summary['fallback_estimated_findings']/max(1,summary['total_findings_audited'])*100:.1f}%)")
    print(f"\nCategory Support Integrity:")
    print(f"  - Findings Supported by Evidence       : {summary['findings_with_genuinely_supporting_evidence']} ({summary['findings_with_genuinely_supporting_evidence']/max(1,summary['total_findings_audited'])*100:.1f}%)")
    print(f"  - Findings NOT Supported by Evidence   : {summary['findings_not_supported_by_evidence']} ({summary['findings_not_supported_by_evidence']/max(1,summary['total_findings_audited'])*100:.1f}%)")
    print(f"\nGround Truth Coverage Integrity:")
    print(f"  - Cases with Genuine Supporting GT     : {summary['cases_with_genuine_supporting_gt_evidence']} / {summary['total_cases_evaluated']} ({summary['cases_with_genuine_supporting_gt_evidence']/summary['total_cases_evaluated']*100:.1f}%)")
    print(f"  - Cases Missing Genuine Supporting GT  : {summary['cases_without_genuine_supporting_gt_evidence']} / {summary['total_cases_evaluated']} ({summary['cases_without_genuine_supporting_gt_evidence']/summary['total_cases_evaluated']*100:.1f}%)")
    print("="*75 + "\n")
    
    full_output = {
        "summary": summary,
        "cases": val_records
    }
    
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(full_output, f, indent=2)
    print(f"Saved evidence validation JSON to {OUTPUT_JSON.resolve()}")
    
    generate_validation_html_report(summary, val_records, OUTPUT_HTML)
    print(f"Saved evidence validation visual HTML report to {OUTPUT_HTML.resolve()}")

if __name__ == '__main__':
    main()
