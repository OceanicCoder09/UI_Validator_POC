import os
import sys
import json
import pathlib
import collections
import pandas as pd
import numpy as np

WORKSPACE_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

V2_RESULTS_PATH = pathlib.Path('backend/evidence_arbitration_causal_v2_results.json')
BASELINE_EVAL_PATH = pathlib.Path('backend/end_to_end_evaluation_results.json')
INVENTORY_PATH = pathlib.Path('backend/final_evidence_inventory.json')
MATRIX_PATH = pathlib.Path('backend/final_evidence_matrix.csv')

OUTPUT_JSON = pathlib.Path('backend/causal_v2_error_attribution.json')
OUTPUT_HTML = pathlib.Path('backend/causal_v2_error_attribution.html')

TARGET_CLASSES = [
    "Misalignment",
    "Overlapping",
    "Truncation",
    "Untranslation",
    "Repeated hotkey"
]

def load_all_data():
    with open(V2_RESULTS_PATH, 'r', encoding='utf-8') as f:
        v2_data = json.load(f)
    with open(BASELINE_EVAL_PATH, 'r', encoding='utf-8') as f:
        base_data = {t["case_id"]: t for t in json.load(f)["case_traces"]}
    with open(INVENTORY_PATH, 'r', encoding='utf-8') as f:
        inv_data = {c["case_id"]: c for c in json.load(f)["cases"]}
    df_matrix = pd.read_csv(MATRIX_PATH).set_index("Case_ID")
        
    return v2_data, base_data, inv_data, df_matrix

def analyze_v2_errors():
    v2_data, base_data, inv_data, df_matrix = load_all_data()
    diffs = v2_data["case_diffs"]
    
    print(f"Performing post-v2 error attribution analysis across {len(diffs)} cases...", flush=True)

    attributed_cases = []
    
    cat_error_breakdown = collections.defaultdict(lambda: {
        "total_cases": 0,
        "correct_v2_count": 0,
        "error_v2_count": 0,
        "gt_in_secondary_count": 0,
        "gt_absent_count": 0,
        "wrong_predictions": collections.defaultdict(int),
        "competing_streams": collections.defaultdict(int),
        "error_reasons": collections.defaultdict(int),
        "exemplar_cases": []
    })
    
    v2_top1_correct = 0
    v2_top2_correct = 0
    gt_in_secondary_total = 0
    gt_absent_total = 0
    
    arbitration_fixable_count = 0
    evidence_extraction_required_count = 0
    fundamentally_unobservable_count = 0
    
    for d in diffs:
        cid = d["case_id"]
        gt = d["ground_truth"]
        pred_v2 = d["v2_primary"]
        sec_v2 = d["v2_secondary"]
        base_pred = d["baseline_primary"]
        
        is_top1_v2 = (pred_v2 == gt)
        is_top2_v2 = is_top1_v2 or (gt in sec_v2)
        gt_in_sec = (not is_top1_v2 and gt in sec_v2)
        gt_absent = (not is_top1_v2 and gt not in sec_v2)
        
        if is_top1_v2:
            v2_top1_correct += 1
        if is_top2_v2:
            v2_top2_correct += 1
        if gt_in_sec:
            gt_in_secondary_total += 1
        if gt_absent:
            gt_absent_total += 1
            
        inv_case = inv_data[cid]
        base_trace = base_data[cid]
        row = df_matrix.loc[cid]
        
        strengths = base_trace["evidence_strengths_all_categories"]
        gt_strength = strengths.get(gt, 0.0) if gt != "Repeated hotkey" else -1.0
        win_strength = strengths.get(pred_v2, 0.0) if pred_v2 != "NO_STRONG_OBSERVABLE_DEFECT" else 0.0
        
        # Determine Error Classification
        if is_top1_v2:
            error_type = "CORRECT_PREDICTION"
            error_bucket = "NONE"
        elif gt == "Repeated hotkey":
            error_type = "VISUALLY_UNSUPPORTED"
            error_bucket = "FUNDAMENTALLY_UNOBSERVABLE"
            fundamentally_unobservable_count += 1
        elif pred_v2 == "NO_STRONG_OBSERVABLE_DEFECT":
            error_type = "AMBIGUOUS_INSUFFICIENT_EVIDENCE"
            error_bucket = "EVIDENCE_EXTRACTION_REQUIRED"
            evidence_extraction_required_count += 1
        elif gt_in_sec:
            # GT was detected with active evidence but lost primary status
            if gt_strength >= 0.40 and win_strength >= 0.40:
                error_type = "CAUSAL_ATTRIBUTION_FAILURE"
                error_bucket = "ARBITRATION_FIXABLE"
                arbitration_fixable_count += 1
            else:
                error_type = "ARBITRATION_RANKING_FAILURE"
                error_bucket = "ARBITRATION_FIXABLE"
                arbitration_fixable_count += 1
        else:
            # GT was completely absent from detected evidence
            error_type = "EVIDENCE_COVERAGE_FAILURE"
            error_bucket = "EVIDENCE_EXTRACTION_REQUIRED"
            evidence_extraction_required_count += 1

        cat_break = cat_error_breakdown[gt]
        cat_break["total_cases"] += 1
        if is_top1_v2:
            cat_break["correct_v2_count"] += 1
        else:
            cat_break["error_v2_count"] += 1
            cat_break["wrong_predictions"][pred_v2] += 1
            cat_break["competing_streams"][pred_v2] += 1
            cat_break["error_reasons"][error_type] += 1
            if gt_in_sec:
                cat_break["gt_in_secondary_count"] += 1
            if gt_absent:
                cat_break["gt_absent_count"] += 1
                
            if len(cat_break["exemplar_cases"]) < 4:
                cat_break["exemplar_cases"].append({
                    "case_id": cid,
                    "product": d["product"],
                    "language": d["language"],
                    "predicted_primary": pred_v2,
                    "gt_strength": gt_strength,
                    "win_strength": win_strength,
                    "error_type": error_type,
                    "explanation": d["reason_for_change"]
                })

        record = {
            "case_id": cid,
            "product": d["product"],
            "folder": d["folder"],
            "language": d["language"],
            "ground_truth": gt,
            "v2_primary": pred_v2,
            "v2_secondary": sec_v2,
            "gt_evidence_status": "PRIMARY" if is_top1_v2 else ("SECONDARY" if gt_in_sec else "ABSENT"),
            "gt_evidence_strength": gt_strength,
            "winning_category_evidence_strength": win_strength,
            "error_classification": error_type,
            "resolution_bucket": error_bucket,
            "baseline_primary": base_pred,
            "v2_effect": "CORRECTED" if d["corrected"] else ("REGRESSION" if d["new_error"] else ("CHANGED" if d["changed"] else "UNCHANGED")),
            "explanation": d["explanation"]
        }
        attributed_cases.append(record)

    summary = {
        "overall_summary": {
            "total_cases": len(diffs),
            "v2_top1_correct_cases": v2_top1_correct,
            "v2_top2_correct_cases": v2_top2_correct,
            "gt_present_in_secondary_count": gt_in_secondary_total,
            "gt_completely_absent_count": gt_absent_total,
            "cases_corrected_by_v2": v2_data["error_audit_resolution"]["arbitration_errors_fixed_count"],
            "new_regressions_by_v2": v2_data["error_audit_resolution"]["new_regressions_introduced_count"],
            "net_gain": v2_data["error_audit_resolution"]["net_correct_case_gain"]
        },
        "error_resolution_potential": {
            "arbitration_fixable_errors_count": arbitration_fixable_count,
            "evidence_extraction_required_count": evidence_extraction_required_count,
            "fundamentally_unobservable_count": fundamentally_unobservable_count,
            "total_errors": len(diffs) - v2_top1_correct
        },
        "category_specific_error_breakdown": {
            k: {
                "total_cases": v["total_cases"],
                "correct_count": v["correct_v2_count"],
                "error_count": v["error_v2_count"],
                "gt_in_secondary_count": v["gt_in_secondary_count"],
                "gt_absent_count": v["gt_absent_count"],
                "most_common_wrong_prediction": dict(sorted(v["wrong_predictions"].items(), key=lambda x: x[1], reverse=True)),
                "error_reasons_breakdown": dict(v["error_reasons"]),
                "exemplars": v["exemplar_cases"]
            }
            for k, v in cat_error_breakdown.items()
        },
        "detailed_cases": attributed_cases
    }
    
    return summary

def generate_attribution_html(summary, output_path):
    ov = summary["overall_summary"]
    pot = summary["error_resolution_potential"]
    cats = summary["category_specific_error_breakdown"]
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Post-v2 Error Attribution Analysis Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
  h1 {{ color: #38bdf8; font-size: 24px; margin-bottom: 6px; }}
  h2 {{ color: #93c5fd; font-size: 18px; margin-top: 28px; border-bottom: 1px solid #334155; padding-bottom: 6px; }}
  .metrics-banner {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 20px 0; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; text-align: center; }}
  .card-val {{ font-size: 22px; font-weight: bold; margin-top: 4px; color: #38bdf8; }}
  .card-sub {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; background: #1e293b; border-radius: 6px; overflow: hidden; }}
  th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #334155; }}
  th {{ background: #0f172a; color: #38bdf8; font-weight: 600; }}
  tr:hover {{ background: #243247; }}
  .badge-arb {{ background: #0369a1; color: #e0f2fe; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }}
  .badge-cov {{ background: #831843; color: #ffe4e6; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }}
  .badge-unobs {{ background: #334155; color: #94a3b8; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }}
  .badge-pass {{ background: #064e3b; color: #a7f3d0; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }}
</style>
</head>
<body>
<h1>Post-v2 Error Attribution Analysis Report</h1>
<div style="color: #94a3b8; font-size: 14px;">
  In-depth attribution audit of remaining errors under Causal Precedence Arbitrator v2 across all 101 benchmark cases.
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Arbitration Fixable Errors</div>
    <div class="card-val" style="color: #38bdf8;">{pot['arbitration_fixable_errors_count']} cases</div>
    <div class="card-sub">GT in secondary ({pot['arbitration_fixable_errors_count']/pot['total_errors']*100:.1f}% of errors)</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Evidence Coverage Gaps</div>
    <div class="card-val" style="color: #f43f5e;">{pot['evidence_extraction_required_count']} cases</div>
    <div class="card-sub">GT absent / sub-pixel noise ({pot['evidence_extraction_required_count']/pot['total_errors']*100:.1f}%)</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Fundamentally Unobservable</div>
    <div class="card-val" style="color: #94a3b8;">{pot['fundamentally_unobservable_count']} cases</div>
    <div class="card-sub">Repeated Hotkey native font underlines</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Total Top-2 Captures</div>
    <div class="card-val" style="color: #4ade80;">{ov['v2_top2_correct_cases']} / 101</div>
    <div class="card-sub">66.3% full / 71.3% observable</div>
  </div>
</div>

<h2>1. Category-Specific Error Analysis</h2>
<table>
  <thead>
    <tr>
      <th>Ground Truth Category</th>
      <th>Benchmark N</th>
      <th>Correct Top-1</th>
      <th>GT in Secondary</th>
      <th>GT Absent</th>
      <th>Most Common Wrong Winner</th>
      <th>Dominant Failure Mechanism</th>
    </tr>
  </thead>
  <tbody>
"""
    for cat_name, c in cats.items():
        top_wrong = list(c["most_common_wrong_prediction"].items())
        top_wrong_str = f"{top_wrong[0][0]} ({top_wrong[0][1]}x)" if top_wrong else "None"
        is_hk = (cat_name == "Repeated hotkey")
        html += f"""
    <tr>
      <td style="font-weight:bold; color:#38bdf8;">{cat_name}</td>
      <td>{c['total_cases']}</td>
      <td style="color:#4ade80; font-weight:bold;">{c['correct_count']}</td>
      <td style="color:#38bdf8; font-weight:bold;">{c['gt_in_secondary_count']}</td>
      <td style="color:#f43f5e; font-weight:bold;">{c['gt_absent_count']}</td>
      <td style="font-weight:bold;">{top_wrong_str}</td>
      <td style="font-size:12px; color:#cbd5e1;">{'Fundamentally unobservable via flat OCR.' if is_hk else ('Displacement accompanied by downstream clipping/intrusion.' if cat_name == 'Misalignment' else ('Text expansion triggers collision/clipping dominance.' if cat_name == 'Untranslation' else 'Sibling intrusion vs container boundary balance.'))}</td>
    </tr>
"""
    html += """
  </tbody>
</table>

<h2>2. Case Error Trace Sample (Sample of 30 Cases)</h2>
<table>
  <thead>
    <tr>
      <th>ID</th>
      <th>Ground Truth</th>
      <th>v2 Prediction</th>
      <th>GT Status</th>
      <th>GT vs Winner Strength</th>
      <th>Resolution Path</th>
    </tr>
  </thead>
  <tbody>
"""
    for c in summary["detailed_cases"][:30]:
        if c["error_classification"] == "CORRECT_PREDICTION":
            badge = "<span class='badge-pass'>CORRECT</span>"
        elif c["resolution_bucket"] == "ARBITRATION_FIXABLE":
            badge = "<span class='badge-arb'>ARBITRATION FIXABLE</span>"
        elif c["resolution_bucket"] == "EVIDENCE_EXTRACTION_REQUIRED":
            badge = "<span class='badge-cov'>EVIDENCE GAPS</span>"
        else:
            badge = "<span class='badge-unobs'>UNOBSERVABLE</span>"
            
        html += f"""
    <tr>
      <td style="font-weight:bold;">#{c['case_id']}</td>
      <td style="font-weight:bold; color:#38bdf8;">{c['ground_truth']}</td>
      <td>{c['v2_primary']}</td>
      <td>{c['gt_evidence_status']}</td>
      <td style="font-size:12px;">GT: <code>{c['gt_evidence_strength']}</code> vs Win: <code>{c['winning_category_evidence_strength']}</code></td>
      <td>{badge}</td>
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
    summary = analyze_v2_errors()
    
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    print(f"Saved post-v2 error attribution JSON to {OUTPUT_JSON.resolve()}")
    
    generate_attribution_html(summary, OUTPUT_HTML)
    print(f"Saved visual HTML report to {OUTPUT_HTML.resolve()}")

    ov = summary["overall_summary"]
    pot = summary["error_resolution_potential"]
    
    print("\n" + "="*75)
    print("POST-V2 ERROR ATTRIBUTION ANALYSIS SUMMARY (N = 101)")
    print("="*75)
    print(f"1. Total Benchmark Cases                 : {ov['total_cases']}")
    print(f"2. v2 Top-1 Correct Cases                : {ov['v2_top1_correct_cases']} (29.7%)")
    print(f"3. v2 Top-2 Correct Cases                : {ov['v2_top2_correct_cases']} (66.3%)")
    print(f"4. GT Present in Secondary Stream        : {ov['gt_present_in_secondary_count']} cases")
    print(f"5. GT Completely Absent from Streams     : {ov['gt_completely_absent_count']} cases")
    print(f"6. Total Error Cases                     : {pot['total_errors']}")
    print(f"   - Arbitration Fixable Errors          : {pot['arbitration_fixable_errors_count']} ({pot['arbitration_fixable_errors_count']/pot['total_errors']*100:.1f}%)")
    print(f"   - Evidence Extraction Required        : {pot['evidence_extraction_required_count']} ({pot['evidence_extraction_required_count']/pot['total_errors']*100:.1f}%)")
    print(f"   - Fundamentally Unobservable (Hotkey) : {pot['fundamentally_unobservable_count']} ({pot['fundamentally_unobservable_count']/pot['total_errors']*100:.1f}%)")
    print("="*75 + "\n")

if __name__ == '__main__':
    main()
