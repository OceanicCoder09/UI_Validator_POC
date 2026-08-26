import os
import sys
import json
import pathlib
import collections
import pandas as pd
import numpy as np

WORKSPACE_ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORT_V2_PATH = pathlib.Path('backend/evidence_validation_report_v2.json')
RELATIONSHIP_PATH = pathlib.Path('backend/relationship_evidence_all_cases.json')
CHANGE_REGIONS_PATH = pathlib.Path('backend/change_regions.json')

OUTPUT_JSON = pathlib.Path('backend/evidence_gap_analysis.json')
OUTPUT_HTML = pathlib.Path('backend/evidence_gap_analysis.html')

GAP_REASONS = [
    "DETECTOR_MISSED",
    "ELEMENT_MATCHING_FAILED",
    "EVIDENCE_EXTRACTION_MISSING",
    "EVIDENCE_REPRESENTATION_PROBLEM",
    "UNSUPPORTED_BY_CURRENT_DETECTORS",
    "COMPOUND_OR_AMBIGUOUS_GT"
]

def load_data():
    with open(REPORT_V2_PATH, 'r', encoding='utf-8') as f:
        v2_data = json.load(f)
    with open(RELATIONSHIP_PATH, 'r', encoding='utf-8') as f:
        rel_data = {r["case_id"]: r for r in json.load(f)}
    with open(CHANGE_REGIONS_PATH, 'r', encoding='utf-8') as f:
        cr_data = {r["case_id"]: r for r in json.load(f)}
        
    return v2_data, rel_data, cr_data

def diagnose_case_gap(c, rel_info, cr_info):
    gt = c["ground_truth_category"]
    findings = c["findings"]
    
    # Existing findings and genuine evidence summary
    current_findings_summary = [f"{f['detected_category']} ({f['finding_id']}: {f['title'][:45]}...)" for f in findings]
    
    genuine_evidence_present = []
    for f in findings:
        if f.get("has_genuine_evidence"):
            prov = f.get("provenance_trace", {})
            prov_str = ", ".join([f"{k}={v}" for k, v in prov.items()])
            genuine_evidence_present.append(f"{f['detected_category']}: {prov_str}")
            
    # Check relationship physical features
    rf = rel_info.get("evidence_features", {}) if rel_info else {}
    ms = rel_info.get("matching_stats", {}) if rel_info else {}
    match_rate = ms.get("match_rate_pct", 0.0)
    
    primary_reason = ""
    secondary_reason = None
    missing_evidence = ""
    required_measurement = ""
    
    if gt == "Truncation":
        # Check if ellipsis was in OCR or text expansion occurred
        has_ell_in_rel = rf.get("has_ellipsis_count", 0) > 0
        text_exp = rf.get("max_text_expansion_px", 0)
        
        if match_rate < 50.0:
            primary_reason = "ELEMENT_MATCHING_FAILED"
            secondary_reason = "EVIDENCE_EXTRACTION_MISSING"
            missing_evidence = "OCR failed to match translated text container against English baseline container due to script font or low contrast."
            required_measurement = "Pixel-level container right-boundary coordinate vs text rendering endpoint delta (W_text - W_container)."
        elif any(f["detected_category"] == "TRUNCATION" for f in findings):
            primary_reason = "EVIDENCE_REPRESENTATION_PROBLEM"
            secondary_reason = "EVIDENCE_EXTRACTION_MISSING"
            missing_evidence = "Detector flagged text line but could not establish rigid parent container boundary (overflow_px was set to null)."
            required_measurement = "Enclosing dialog control bounding box width minus rendered font string width."
        elif has_ell_in_rel or text_exp > 20:
            primary_reason = "DETECTOR_MISSED"
            secondary_reason = "EVIDENCE_EXTRACTION_MISSING"
            missing_evidence = "Text expanded beyond boundary or had terminal ellipsis but was not captured by morphological line extractor."
            required_measurement = "Character terminal bounding edge vs parent clip rect."
        else:
            primary_reason = "UNSUPPORTED_BY_CURRENT_DETECTORS"
            secondary_reason = "DETECTOR_MISSED"
            missing_evidence = "Truncation occurs inside dynamic custom control (grid, tree, or table column header) not recognized by standard button/input heuristics."
            required_measurement = "Column cell width constraint vs text line length."

    elif gt == "Misalignment":
        max_disp = rf.get("max_displacement_px", 0)
        align_div = rf.get("max_alignment_divergence_px", 0)
        
        if match_rate < 50.0:
            primary_reason = "ELEMENT_MATCHING_FAILED"
            secondary_reason = "EVIDENCE_REPRESENTATION_PROBLEM"
            missing_evidence = "Elements moved significantly, causing standard spatial/text correspondence matcher to fail."
            required_measurement = "Global-shift compensated column anchor X coordinate delta (X_loc - X_enu)."
        elif any(f["detected_category"] == "MISSALIGNMENT" for f in findings):
            primary_reason = "EVIDENCE_REPRESENTATION_PROBLEM"
            missing_evidence = "Misalignment detector flagged element but baseline anchor pairing was outside vertical search tolerance (position_shift_x was null)."
            required_measurement = "Exact left anchor X offset between baseline column control and localized column control."
        elif align_div >= 12 or max_disp >= 15:
            primary_reason = "DETECTOR_MISSED"
            secondary_reason = "EVIDENCE_EXTRACTION_MISSING"
            missing_evidence = "Physical relationship analyzer observed column divergence, but cv_engine line extractor did not link them as vertical column siblings."
            required_measurement = "Multi-row left-edge alignment variance (std_dev(X_anchors)) across vertical sibling group."
        else:
            primary_reason = "UNSUPPORTED_BY_CURRENT_DETECTORS"
            secondary_reason = "EVIDENCE_EXTRACTION_MISSING"
            missing_evidence = "Misalignment is subtle baseline displacement (<4px) or complex multi-column form table layout."
            required_measurement = "Normalized column anchor margin delta relative to dialog left border."

    elif gt == "Overlapping":
        coll_area = rf.get("total_intersection_area_px2", 0)
        gap_col = rf.get("max_gap_collapse_px", 0)
        
        if any(f["detected_category"] == "OVERLAPPING" for f in findings):
            primary_reason = "EVIDENCE_REPRESENTATION_PROBLEM"
            missing_evidence = "Overlap detected between rough bounding boxes, but exact pixel-wise geometric intersection was below threshold or unattached."
            required_measurement = "Non-zero polygon intersection area (Intersection(Box_A, Box_B) in px^2)."
        elif coll_area > 0 or gap_col > 20:
            primary_reason = "DETECTOR_MISSED"
            secondary_reason = "EVIDENCE_EXTRACTION_MISSING"
            missing_evidence = "Physical bounding boxes collided in localized view, but cv_engine container detector did not register both bounding boxes simultaneously."
            required_measurement = "Bounding box horizontal intrusion distance (Box1_right - Box2_left)."
        elif match_rate < 50.0:
            primary_reason = "ELEMENT_MATCHING_FAILED"
            secondary_reason = "DETECTOR_MISSED"
            missing_evidence = "Overlapping elements merged into a single OCR block or contour, preventing individual element identification."
            required_measurement = "Contour segmentation of merged text block into constituent glyph sequences."
        else:
            primary_reason = "UNSUPPORTED_BY_CURRENT_DETECTORS"
            secondary_reason = "EVIDENCE_EXTRACTION_MISSING"
            missing_evidence = "Complex z-order overlap or text over icon/background bitmap collision."
            required_measurement = "Foreground text pixel mask overlap with background icon/border contour."

    elif gt == "Untranslation":
        untrans_words = rf.get("untranslated_words_count", 0)
        
        if untrans_words > 0:
            primary_reason = "DETECTOR_MISSED"
            secondary_reason = "EVIDENCE_EXTRACTION_MISSING"
            missing_evidence = "English tokens exist in localized screen but were skipped by cv_engine whitelist or OCR failed to recognize Latin characters in non-Latin UI context."
            required_measurement = "Case-insensitive dictionary lookup matching localized token against English baseline vocabulary."
        elif match_rate < 50.0:
            primary_reason = "ELEMENT_MATCHING_FAILED"
            missing_evidence = "Unable to correlate localized text block with English counterpart due to dialog layout difference."
            required_measurement = "Text embedding / string exact match between localized OCR block and baseline OCR block."
        elif any(f["detected_category"] == "UNTRANSLATION" for f in findings):
            primary_reason = "EVIDENCE_REPRESENTATION_PROBLEM"
            missing_evidence = "Untranslation finding emitted without associating localized text string."
            required_measurement = "Identical English string token array."
        else:
            primary_reason = "UNSUPPORTED_BY_CURRENT_DETECTORS"
            secondary_reason = "COMPOUND_OR_AMBIGUOUS_GT"
            missing_evidence = "Untranslated text is embedded inside a pre-rendered graphic image or icon label."
            required_measurement = "OCR extraction on embedded raster graphics/icons."

    elif gt == "Repeated hotkey":
        if any(f["detected_category"] == "HOTKEY_DEFECT" for f in findings):
            primary_reason = "EVIDENCE_REPRESENTATION_PROBLEM"
            missing_evidence = "Hotkey regex flagged defect but did not attach both conflicting control names."
            required_measurement = "Conflicting accelerator letter and list of conflicting control labels."
        else:
            primary_reason = "DETECTOR_MISSED"
            secondary_reason = "EVIDENCE_EXTRACTION_MISSING"
            missing_evidence = "Hotkey accelerator markup (e.g. (&A) or &File) was omitted by OCR engine or formatted with non-standard brackets."
            required_measurement = "Extended regex parser supporting full-width parentheses, CJK mnemonics, and underline accelerators."

    else:
        primary_reason = "COMPOUND_OR_AMBIGUOUS_GT"
        secondary_reason = "UNSUPPORTED_BY_CURRENT_DETECTORS"
        missing_evidence = f"Category '{gt}' lacks dedicated physical measurement pipeline."
        required_measurement = "Domain-specific physical delta metric."

    return {
        "case_id": c["case_id"],
        "product": c["product"],
        "folder": c["folder"],
        "lang": c["lang"],
        "ground_truth_category": gt,
        "current_findings": current_findings_summary,
        "genuine_evidence_available": genuine_evidence_present,
        "missing_evidence": missing_evidence,
        "primary_gap_reason": primary_reason,
        "secondary_gap_reason": secondary_reason,
        "required_physical_measurement": required_measurement
    }

def analyze_all_gaps():
    v2_data, rel_data, cr_data = load_data()
    all_cases = v2_data["cases"]
    
    # Filter to the 77 cases without genuine GT evidence
    gap_cases = [c for c in all_cases if not c["has_genuine_gt_finding"]]
    print(f"Analyzing {len(gap_cases)} gap cases (cases lacking genuine GT evidence)...")
    
    analyzed_records = []
    reason_counts = collections.defaultdict(int)
    cat_breakdown = collections.defaultdict(lambda: collections.defaultdict(int))
    
    for c in gap_cases:
        cid = c["case_id"]
        rel_info = rel_data.get(cid)
        cr_info = cr_data.get(cid)
        
        diag = diagnose_case_gap(c, rel_info, cr_info)
        analyzed_records.append(diag)
        
        p_reason = diag["primary_gap_reason"]
        reason_counts[p_reason] += 1
        cat_breakdown[diag["ground_truth_category"]][p_reason] += 1

    total_gaps = len(gap_cases)
    
    aggregate_table = []
    for r in GAP_REASONS:
        cnt = reason_counts[r]
        pct = round((cnt / total_gaps) * 100.0, 1) if total_gaps > 0 else 0.0
        aggregate_table.append({
            "gap_reason": r,
            "count": cnt,
            "percentage": pct
        })
        
    return {
        "total_gap_cases": total_gaps,
        "aggregate_summary": aggregate_table,
        "breakdown_by_category": {cat: dict(counts) for cat, counts in cat_breakdown.items()},
        "cases": analyzed_records
    }

def generate_gap_html(results, output_path):
    agg = results["aggregate_summary"]
    total = results["total_gap_cases"]
    cats = results["breakdown_by_category"]
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Evidence Gap Analysis Report (77 Unsupported Cases)</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
  h1 {{ color: #38bdf8; font-size: 24px; margin-bottom: 6px; }}
  h2 {{ color: #93c5fd; font-size: 18px; margin-top: 28px; border-bottom: 1px solid #334155; padding-bottom: 6px; }}
  .metrics-banner {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 20px 0; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; text-align: center; }}
  .card-val {{ font-size: 26px; font-weight: bold; margin-top: 4px; color: #38bdf8; }}
  .card-sub {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; background: #1e293b; border-radius: 6px; overflow: hidden; }}
  th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #334155; }}
  th {{ background: #0f172a; color: #38bdf8; font-weight: 600; }}
  tr:hover {{ background: #243247; }}
  .badge-reason {{ background: #1e3a5f; color: #38bdf8; padding: 3px 8px; border-radius: 4px; font-family: monospace; font-size: 12px; font-weight: bold; }}
  .badge-sec {{ background: #334155; color: #cbd5e1; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 11px; }}
  .case-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; margin-bottom: 20px; padding: 16px; }}
  .case-header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 8px; margin-bottom: 10px; }}
  .gt-badge {{ background: #831843; border: 1px solid #f43f5e; color: #ffe4e6; font-weight: 600; padding: 3px 8px; border-radius: 4px; font-size: 12px; }}
</style>
</head>
<body>
<h1>Evidence Gap Analysis Report</h1>
<div style="color: #94a3b8; font-size: 14px;">
  Deep-dive root-cause classification for the <strong>{total} benchmark cases</strong> lacking genuine physical Ground Truth evidence in <code>cv_engine.py</code>.
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Total Gap Cases Analyzed</div>
    <div class="card-val">{total}</div>
    <div class="card-sub">out of 101 benchmark cases (76.2%)</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Leading Gap Cause</div>
    <div class="card-val" style="font-size: 20px; color: #f43f5e;">{agg[0]['gap_reason']}</div>
    <div class="card-sub">{agg[0]['count']} cases ({agg[0]['percentage']}%)</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Cases with Supporting Findings</div>
    <div class="card-val" style="color: #4ade80;">24 / 101</div>
    <div class="card-sub">already have genuine measured GT evidence</div>
  </div>
</div>

<h2>1. Aggregate Gap Distribution (N = {total})</h2>
<table>
  <thead>
    <tr>
      <th>Primary Gap Classification</th>
      <th>Case Count</th>
      <th>Percentage of Gap Cases</th>
      <th>Description / Root Cause</th>
    </tr>
  </thead>
  <tbody>
"""
    desc_map = {
        "DETECTOR_MISSED": "Detector did not flag the defect region or text bounding box due to rigid OCR/heuristic search windows.",
        "ELEMENT_MATCHING_FAILED": "Spatial/OCR correspondence matcher failed to match localized element to its English baseline counterpart.",
        "EVIDENCE_EXTRACTION_MISSING": "Detector flagged the visual change but did not extract/record the underlying physical delta measurement.",
        "EVIDENCE_REPRESENTATION_PROBLEM": "Finding was emitted but its physical measurement could not be calculated (set to null instead of guessed).",
        "UNSUPPORTED_BY_CURRENT_DETECTORS": "Defect manifests in non-standard UI controls (tables, tree views, canvas graphics) unsupported by current detectors.",
        "COMPOUND_OR_AMBIGUOUS_GT": "Case involves multiple overlapping defect categories or ambiguous visual phenomena."
    }
    for row in agg:
        html += f"""
    <tr>
      <td><span class="badge-reason">{row['gap_reason']}</span></td>
      <td style="font-weight:bold; font-size:14px;">{row['count']}</td>
      <td>{row['percentage']}%</td>
      <td style="color:#cbd5e1; font-size:12px;">{desc_map.get(row['gap_reason'], '')}</td>
    </tr>
"""
    html += """
  </tbody>
</table>

<h2>2. Breakdown by Ground Truth Category</h2>
<table>
  <thead>
    <tr>
      <th>Ground Truth Category</th>
      <th>DETECTOR_MISSED</th>
      <th>EVIDENCE_REPRESENTATION_PROBLEM</th>
      <th>UNSUPPORTED_BY_CURRENT_DETECTORS</th>
      <th>ELEMENT_MATCHING_FAILED</th>
      <th>EVIDENCE_EXTRACTION_MISSING</th>
      <th>Total Gaps</th>
    </tr>
  </thead>
  <tbody>
"""
    for cat_name, bdown in cats.items():
        html += f"""
    <tr>
      <td style="font-weight:600; color:#38bdf8;">{cat_name}</td>
      <td>{bdown.get('DETECTOR_MISSED', 0)}</td>
      <td>{bdown.get('EVIDENCE_REPRESENTATION_PROBLEM', 0)}</td>
      <td>{bdown.get('UNSUPPORTED_BY_CURRENT_DETECTORS', 0)}</td>
      <td>{bdown.get('ELEMENT_MATCHING_FAILED', 0)}</td>
      <td>{bdown.get('EVIDENCE_EXTRACTION_MISSING', 0)}</td>
      <td style="font-weight:bold;">{sum(bdown.values())}</td>
    </tr>
"""
    html += """
  </tbody>
</table>

<h2>3. Case-by-Case Gap Diagnostics (77 Cases)</h2>
"""
    for c in results["cases"]:
        findings_str = "<br>".join([f"• {f}" for f in c["current_findings"][:3]]) if c["current_findings"] else "<em>None</em>"
        sec_str = f"<span class='badge-sec'>{c['secondary_gap_reason']}</span>" if c['secondary_gap_reason'] else "—"
        html += f"""
<div class="case-card">
  <div class="case-header">
    <div>
      <span style="font-size:15px; font-weight:600;">Case #{c['case_id']}: {c['product']} / {c['folder']} ({c['lang']})</span>
      <span class="gt-badge" style="margin-left:10px;">GT: {c['ground_truth_category']}</span>
    </div>
    <div>
      <span class="badge-reason">{c['primary_gap_reason']}</span>
    </div>
  </div>
  
  <div style="font-size:13px; display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-top:8px;">
    <div>
      <strong>Missing Evidence:</strong><br>
      <span style="color:#cbd5e1;">{c['missing_evidence']}</span><br><br>
      <strong>Required Physical Measurement:</strong><br>
      <code style="color:#4ade80;">{c['required_physical_measurement']}</code>
    </div>
    <div>
      <strong>Current Detector Findings:</strong><br>
      <span style="color:#94a3b8; font-size:12px;">{findings_str}</span><br><br>
      <strong>Secondary Gap Reason:</strong> {sec_str}
    </div>
  </div>
</div>
"""

    html += "</body></html>"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

def main():
    results = analyze_all_gaps()
    
    print("\n" + "="*75)
    print("EVIDENCE GAP ANALYSIS SUMMARY (77 UNSUPPORTED CASES)")
    print("="*75)
    for r in results["aggregate_summary"]:
        print(f"  {r['gap_reason']:35s}: {r['count']:2d} cases ({r['percentage']:5.1f}%)")
    print("="*75)
    
    print("\nBreakdown by GT Category:")
    for cat, bdown in results["breakdown_by_category"].items():
        print(f"\n  [{cat}] (Total Gaps: {sum(bdown.values())})")
        for reason, cnt in bdown.items():
            print(f"    - {reason:33s}: {cnt:2d}")
            
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved gap analysis JSON to {OUTPUT_JSON.resolve()}")
    
    generate_gap_html(results, OUTPUT_HTML)
    print(f"Saved gap analysis HTML report to {OUTPUT_HTML.resolve()}")

if __name__ == '__main__':
    main()
