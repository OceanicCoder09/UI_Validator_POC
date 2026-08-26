import os
import sys
import json
import time
import pathlib
import pandas as pd
import numpy as np
import cv2

WORKSPACE_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from backend.cv_engine import analyze_localization_quality

EXCEL_PATH = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize/Screenshot data list from Welocalize.xlsx')
BASE_DATA_ROOT = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize')
RELATIONSHIP_PATH = pathlib.Path('backend/relationship_evidence_all_cases.json')

OUTPUT_JSON = pathlib.Path('backend/misalignment_evidence_v2.json')
OUTPUT_HTML = pathlib.Path('backend/misalignment_evidence_v2.html')

def load_misalignment_cases():
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
        if gt_cat == "Misalignment":
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

def run_misalignment_evaluation():
    records = load_misalignment_cases()
    print(f"Loaded {len(records)} Misalignment benchmark cases.")
    
    with open(RELATIONSHIP_PATH, 'r', encoding='utf-8') as f:
        rel_data = {r["case_id"]: r for r in json.load(f)}
        
    evaluated_cases = []
    improved_count = 0
    has_evidence_count = 0
    no_evidence_count = 0
    
    improved_case_ids = []
    not_improved_case_ids = []
    
    t0 = time.time()
    
    for i, r in enumerate(records):
        cid = r["case_id"]
        img_en = cv2.imread(r["en_path"])
        img_loc = cv2.imread(r["loc_path"])
        
        res = analyze_localization_quality(img_en, img_loc)
        raw_findings = res.get("findings", [])
        
        # Extract relationship stats
        rel_entry = rel_data.get(cid, {})
        mstats = rel_entry.get("matching_stats", {})
        rfeats = rel_entry.get("evidence_features", {})
        
        # Categorize old vs new findings
        old_detector_findings = []
        new_physical_findings = []
        
        for f in raw_findings:
            if f.get("category") == "MISSALIGNMENT":
                ev = f.get("evidence", {})
                title = f.get("title", "")
                if "Translation-Corrected" in title or "global_shift_x" in ev:
                    new_physical_findings.append({
                        "id": f.get("id"),
                        "title": title,
                        "location": f.get("location"),
                        "evidence": ev,
                        "provenance": ev.get("position_shift_provenance", "DIRECTLY_MEASURED")
                    })
                else:
                    old_detector_findings.append({
                        "id": f.get("id"),
                        "title": title,
                        "location": f.get("location"),
                        "evidence": ev,
                        "provenance": ev.get("position_shift_provenance", "UNAVAILABLE")
                    })
                    
        # Extract top 10 displaced element pairs
        all_displacements = []
        for nf in new_physical_findings:
            ev = nf["evidence"]
            all_displacements.append({
                "enu_bbox": ev.get("enu_bbox"),
                "loc_bbox": ev.get("loc_bbox"),
                "corrected_dx": ev.get("corrected_dx"),
                "corrected_dy": ev.get("corrected_dy"),
                "displacement_magnitude": ev.get("displacement_magnitude"),
                "match_confidence": ev.get("element_match_confidence"),
                "provenance": ev.get("position_shift_provenance", "DIRECTLY_MEASURED")
            })
            
        all_displacements.sort(key=lambda d: d.get("displacement_magnitude", 0.0), reverse=True)
        top10_displaced = all_displacements[:10]
        
        max_disp = float(rfeats.get("max_displacement_px", 0.0))
        median_disp = float(rfeats.get("median_displacement_px", 0.0))
        num_indep = int(rfeats.get("num_independently_displaced", 0))
        align_div = float(rfeats.get("max_alignment_divergence_px", 0.0))
        
        global_sx = top10_displaced[0].get("corrected_dx") if top10_displaced else 0.0
        if new_physical_findings:
            global_sx = new_physical_findings[0]["evidence"].get("global_shift_x", 0.0)
            global_sy = new_physical_findings[0]["evidence"].get("global_shift_y", 0.0)
        else:
            global_sx, global_sy = 0.0, 0.0
            
        has_genuine_evidence = len(new_physical_findings) > 0 or max_disp >= 6.0
        
        # Improvement check: Did this case recover genuine physical displacement evidence?
        # In v2 report before this change, only 2/19 cases had genuine evidence
        was_previously_unsupported = cid not in [9, 21] # Cases 9 and 21 had old pair detections
        
        is_improved = len(new_physical_findings) > 0
        if is_improved:
            improved_count += 1
            improved_case_ids.append(cid)
        else:
            not_improved_case_ids.append(cid)
            
        if has_genuine_evidence:
            has_evidence_count += 1
        else:
            no_evidence_count += 1
            
        evaluated_cases.append({
            "case_id": cid,
            "product": r["product"],
            "folder": r["folder"],
            "lang": r["lang"],
            "gt_category": "Misalignment",
            "matched_elements_count": mstats.get("matched_count", 0),
            "match_rate_pct": mstats.get("match_rate_pct", 0.0),
            "global_dialog_shift": {"x": global_sx, "y": global_sy},
            "max_corrected_displacement_px": max_disp,
            "median_corrected_displacement_px": median_disp,
            "num_independently_displaced_elements": num_indep,
            "max_alignment_divergence_px": align_div,
            "old_detector_findings_count": len(old_detector_findings),
            "new_physical_evidence_findings_count": len(new_physical_findings),
            "has_genuine_displacement_evidence": bool(has_genuine_evidence),
            "top_10_displaced_elements": top10_displaced,
            "old_detector_findings": old_detector_findings,
            "new_physical_findings": new_physical_findings
        })
        
        print(f"  [{i+1}/19] Case #{cid:2d} ({r['product']}/{r['folder']}_{r['lang']}): {len(new_physical_findings)} physical displacement findings (Max disp: {max_disp:.1f}px)")

    summary = {
        "total_misalignment_cases": len(records),
        "cases_with_genuine_displacement_evidence": has_evidence_count,
        "cases_without_displacement_evidence": no_evidence_count,
        "improved_cases_count": improved_count,
        "improved_case_ids": improved_case_ids,
        "not_improved_case_ids": not_improved_case_ids
    }
    
    return summary, evaluated_cases

def generate_html_report(summary, cases, output_path):
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Misalignment Physical Evidence Report v2</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
  h1 {{ color: #38bdf8; font-size: 24px; margin-bottom: 6px; }}
  h2 {{ color: #93c5fd; font-size: 18px; margin-top: 28px; border-bottom: 1px solid #334155; padding-bottom: 6px; }}
  .metrics-banner {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 20px 0; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; text-align: center; }}
  .card-val {{ font-size: 26px; font-weight: bold; margin-top: 4px; color: #38bdf8; }}
  .card-sub {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
  .case-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; margin-bottom: 24px; padding: 18px; }}
  .case-header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 10px; margin-bottom: 12px; }}
  .status-pass {{ background: #064e3b; border: 1px solid #10b981; color: #a7f3d0; font-weight: 600; padding: 4px 10px; border-radius: 6px; font-size: 13px; }}
  .status-fail {{ background: #450a0a; border: 1px solid #ef4444; color: #fecaca; font-weight: 600; padding: 4px 10px; border-radius: 6px; font-size: 13px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; background: #0f172a; border-radius: 6px; overflow: hidden; }}
  th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid #334155; }}
  th {{ background: #020617; color: #38bdf8; font-weight: 600; }}
  tr:hover {{ background: #1e293b; }}
  .prov-badge {{ background: #064e3b; color: #34d399; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }}
</style>
</head>
<body>
<h1>Misalignment Physical Evidence Report (v2)</h1>
<div style="color: #94a3b8; font-size: 14px;">
  Global-anchor translation-corrected displacement recovery across all 19 benchmark Misalignment cases.
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Total Misalignment Cases</div>
    <div class="card-val" style="color: #f8fafc;">{summary['total_misalignment_cases']}</div>
    <div class="card-sub">19 ground-truth cases</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Cases with Genuine Evidence</div>
    <div class="card-val" style="color: #4ade80;">{summary['cases_with_genuine_displacement_evidence']} / {summary['total_misalignment_cases']}</div>
    <div class="card-sub">{summary['cases_with_genuine_displacement_evidence']/summary['total_misalignment_cases']*100:.1f}% coverage</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Cases Improved</div>
    <div class="card-val" style="color: #38bdf8;">{summary['improved_cases_count']} / {summary['total_misalignment_cases']}</div>
    <div class="card-sub">new physical evidence recovered</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Remaining Without Evidence</div>
    <div class="card-val" style="color: {'#4ade80' if summary['cases_without_displacement_evidence']==0 else '#f43f5e'};">{summary['cases_without_displacement_evidence']}</div>
    <div class="card-sub">cases needing further analysis</div>
  </div>
</div>

<h2>Case-by-Case Physical Evidence Records (19 Misalignment Cases)</h2>
"""
    for c in cases:
        status_badge = "<span class='status-pass'>[PASS] Genuine Physical Evidence</span>" if c["has_genuine_displacement_evidence"] else "<span class='status-fail'>[NO EVIDENCE]</span>"
        
        top10_rows = ""
        for idx, d in enumerate(c["top_10_displaced_elements"]):
            e_box = d.get("enu_bbox", {})
            l_box = d.get("loc_bbox", {})
            top10_rows += f"""
      <tr>
        <td>#{idx+1}</td>
        <td>x={e_box.get('x',0)}, y={e_box.get('y',0)}, w={e_box.get('width',0)}, h={e_box.get('height',0)}</td>
        <td>x={l_box.get('x',0)}, y={l_box.get('y',0)}, w={l_box.get('width',0)}, h={l_box.get('height',0)}</td>
        <td style="font-family:monospace; color:#38bdf8;">dx={d.get('corrected_dx',0):+.1f}px, dy={d.get('corrected_dy',0):+.1f}px</td>
        <td style="font-weight:bold; color:#4ade80;">{d.get('displacement_magnitude',0):.1f}px</td>
        <td>{d.get('match_confidence',0):.3f}</td>
        <td><span class="prov-badge">{d.get('provenance')}</span></td>
      </tr>
"""
        html += f"""
<div class="case-card">
  <div class="case-header">
    <div>
      <span style="font-size:16px; font-weight:600;">Case #{c['case_id']}: {c['product']} / {c['folder']} ({c['lang']})</span>
    </div>
    <div>
      {status_badge}
    </div>
  </div>

  <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; font-size:13px; background:#0f172a; padding:12px; border-radius:6px; margin-bottom:12px;">
    <div><strong>Matched Elements:</strong> {c['matched_elements_count']} ({c['match_rate_pct']}%)</div>
    <div><strong>Global Dialog Shift:</strong> dx={c['global_dialog_shift']['x']:+.1f}px, dy={c['global_dialog_shift']['y']:+.1f}px</div>
    <div><strong>Max Displacement:</strong> <span style="color:#4ade80; font-weight:bold;">{c['max_corrected_displacement_px']:.1f}px</span></div>
    <div><strong>Independently Displaced:</strong> {c['num_independently_displaced_elements']} elements</div>
  </div>

  <div style="font-size:13px; margin-bottom:6px;"><strong>Top Measured Displaced Element Pairs (Translation-Corrected):</strong></div>
  <table>
    <thead>
      <tr>
        <th>Rank</th>
        <th>ENU Bounding Box</th>
        <th>Localized Bounding Box</th>
        <th>Corrected Delta (dx, dy)</th>
        <th>Magnitude</th>
        <th>Confidence</th>
        <th>Provenance</th>
      </tr>
    </thead>
    <tbody>
      {top10_rows if top10_rows else "<tr><td colspan='7' style='text-align:center; color:#94a3b8;'>No displaced elements >= 6.0px detected.</td></tr>"}
    </tbody>
  </table>

  <div style="font-size:12px; color:#94a3b8; margin-top:10px;">
    <strong>Detector Findings Comparison:</strong> Old local-pair findings: {c['old_detector_findings_count']} | New translation-corrected findings: {c['new_physical_evidence_findings_count']}
  </div>
</div>
"""

    html += "</body></html>"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

def main():
    summary, cases = run_misalignment_evaluation()
    
    print("\n" + "="*75)
    print("MISALIGNMENT PHYSICAL EVIDENCE REPORT SUMMARY (N = 19)")
    print("="*75)
    print(f"Total Misalignment Benchmark Cases        : {summary['total_misalignment_cases']}")
    print(f"Cases with Genuine Displacement Evidence  : {summary['cases_with_genuine_displacement_evidence']} / {summary['total_misalignment_cases']} ({summary['cases_with_genuine_displacement_evidence']/summary['total_misalignment_cases']*100:.1f}%)")
    print(f"Cases Without Displacement Evidence       : {summary['cases_without_displacement_evidence']} / {summary['total_misalignment_cases']}")
    print(f"Cases Improved with New Physical Evidence : {summary['improved_cases_count']} / {summary['total_misalignment_cases']}")
    print(f"Improved Case IDs                         : {summary['improved_case_ids']}")
    print(f"Not Improved Case IDs                     : {summary['not_improved_case_ids']}")
    print("="*75 + "\n")
    
    full_output = {
        "summary": summary,
        "cases": cases
    }
    
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(full_output, f, indent=2)
    print(f"Saved misalignment physical evidence JSON to {OUTPUT_JSON.resolve()}")
    
    generate_html_report(summary, cases, OUTPUT_HTML)
    print(f"Saved visual HTML report to {OUTPUT_HTML.resolve()}")

if __name__ == '__main__':
    main()
