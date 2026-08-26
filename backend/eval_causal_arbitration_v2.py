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

from backend.evidence_engine import EvidenceEngine
from backend.evidence_arbitrator import EvidenceArbitrator as BaselineArbitrator
from backend.evidence_arbitration_causal_v2 import CausalEvidenceArbitrator

MISALIGN_PATH = pathlib.Path('backend/misalignment_evidence_v2.json')
MOVEMENT_PATH = pathlib.Path('backend/movement_pattern_analysis.json')
OVERLAP_PATH = pathlib.Path('backend/overlap_evidence_v2.json')
TRUNC_PATH = pathlib.Path('backend/truncation_evidence_v2.json')
UNTRANS_PATH = pathlib.Path('backend/untranslation_evidence_v2.json')
HOTKEY_PATH = pathlib.Path('backend/hotkey_evidence_v2.json')
RELATIONSHIP_PATH = pathlib.Path('backend/relationship_evidence_all_cases.json')
BASELINE_RESULTS_PATH = pathlib.Path('backend/end_to_end_evaluation_results.json')
ROOT_AUDIT_PATH = pathlib.Path('backend/root_cause_error_audit.json')

OUTPUT_RESULTS_JSON = pathlib.Path('backend/evidence_arbitration_causal_v2_results.json')
OUTPUT_REPORT_HTML = pathlib.Path('backend/evidence_arbitration_causal_v2_report.html')

CATEGORIES_5 = [
    "Misalignment",
    "Overlapping",
    "Truncation",
    "Untranslation",
    "Repeated hotkey"
]

CATEGORIES_4 = [
    "Misalignment",
    "Overlapping",
    "Truncation",
    "Untranslation"
]

def load_payloads():
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
    with open(BASELINE_RESULTS_PATH, 'r', encoding='utf-8') as f:
        base_results = {t["case_id"]: t for t in json.load(f)["case_traces"]}
    with open(ROOT_AUDIT_PATH, 'r', encoding='utf-8') as f:
        root_audit = {c["case_id"]: c for c in json.load(f)["cases"]}
        
    all_case_ids = sorted(list(rel_data.keys()))
    payloads = []
    for cid in all_case_ids:
        r = rel_data[cid]
        payloads.append({
            "case_id": cid,
            "product": r["product"],
            "folder": r["folder"],
            "language": r["lang"],
            "ground_truth": r["gt_category"],
            "movement_pattern": mov_data.get(cid, {}),
            "misalignment_v2": mis_data.get(cid, {}),
            "overlap_v2": ov_data.get(cid, {}),
            "truncation_v2": tr_data.get(cid, {}),
            "untranslation_v2": un_data.get(cid, {}),
            "hotkey_v2": hk_data.get(cid, {}),
            "baseline_trace": base_results.get(cid, {}),
            "root_audit": root_audit.get(cid, {})
        })
    return payloads

def evaluate_causal_v2():
    payloads = load_payloads()
    print(f"Evaluating Causal Precedence Arbitrator v2 across {len(payloads)} cases...", flush=True)

    engine = EvidenceEngine()
    causal_arbitrator = CausalEvidenceArbitrator()
    
    v2_traces = []
    case_diffs = []
    
    total_5 = len(payloads)
    obs_4 = [p for p in payloads if p["ground_truth"] in CATEGORIES_4]
    total_4 = len(obs_4)
    
    top1_v2_5 = 0
    top2_v2_5 = 0
    top1_v2_4 = 0
    top2_v2_4 = 0
    abstention_v2 = 0
    
    cm_v2 = collections.defaultdict(lambda: collections.defaultdict(int))
    
    # Audit comparison counters
    arbitration_errors_fixed = 0
    arbitration_errors_remaining = 0
    new_regressions_introduced = 0
    causal_chain_errors_fixed = 0
    
    for p in payloads:
        cid = p["case_id"]
        gt = p["ground_truth"]
        base_trace = p["baseline_trace"]
        base_pred = base_trace.get("primary_category")
        base_sec = [s["category"] for s in base_trace.get("secondary_categories", [])]
        base_top1 = base_trace.get("is_top1_correct", False)
        
        eval_output = engine.evaluate_case(cid, p)
        ev_results = eval_output["evidence_results"]
        
        decision_v2 = causal_arbitrator.arbitrate(cid, ev_results, p)
        pred_v2 = decision_v2.primary_category
        sec_v2 = [s["category"] for s in decision_v2.secondary_categories]
        
        is_top1_v2 = (pred_v2 == gt)
        is_top2_v2 = is_top1_v2 or (gt in sec_v2)
        
        if is_top1_v2:
            top1_v2_5 += 1
            if gt in CATEGORIES_4:
                top1_v2_4 += 1
        if is_top2_v2:
            top2_v2_5 += 1
            if gt in CATEGORIES_4:
                top2_v2_4 += 1
        if pred_v2 == "NO_STRONG_OBSERVABLE_DEFECT":
            abstention_v2 += 1
            
        cm_v2[gt][pred_v2] += 1
        
        # Case Diff tracking
        changed = (base_pred != pred_v2) or (set(base_sec) != set(sec_v2))
        corrected = (not base_top1 and is_top1_v2)
        new_error = (base_top1 and not is_top1_v2)
        
        if corrected:
            arbitration_errors_fixed += 1
            if p["root_audit"].get("identified_causal_chain") not in [None, "Direct Ground-Truth Mechanism Alignment", "Cross-Defect Feature Precedence Competition"]:
                causal_chain_errors_fixed += 1
        elif not is_top1_v2 and not base_top1:
            arbitration_errors_remaining += 1
        elif new_error:
            new_regressions_introduced += 1
            
        reason_change = "Unchanged"
        if corrected:
            reason_change = f"Corrected to {gt} via causal precedence rule."
        elif new_error:
            reason_change = f"Regression: shifted from {base_pred} to {pred_v2}."
        elif changed:
            reason_change = f"Primary shifted from {base_pred} to {pred_v2} (still incorrect)."
            
        diff_record = {
            "case_id": cid,
            "product": p["product"],
            "folder": p["folder"],
            "language": p["language"],
            "ground_truth": gt,
            "baseline_primary": base_pred,
            "v2_primary": pred_v2,
            "baseline_secondary": base_sec,
            "v2_secondary": sec_v2,
            "changed": changed,
            "corrected": corrected,
            "new_error": new_error,
            "reason_for_change": reason_change,
            "explanation": decision_v2.explanation
        }
        case_diffs.append(diff_record)

    # --------------------------------------------------------------------------
    # METRICS SUMMARY COMPARISON
    # --------------------------------------------------------------------------
    
    # 5-Category metrics
    per_cat_v2 = {}
    f1_list_v2 = []
    rec_list_v2 = []
    for cat in CATEGORIES_5:
        tp = cm_v2[cat][cat]
        fp = sum(cm_v2[other][cat] for other in CATEGORIES_5 if other != cat)
        fn = sum(cm_v2[cat][pred] for pred in list(cm_v2[cat].keys()) if pred != cat)
        
        prec = (tp / max(1, tp + fp)) * 100.0 if (tp + fp) > 0 else 0.0
        rec = (tp / max(1, tp + fn)) * 100.0 if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / max(1e-7, prec + rec)) if (prec + rec) > 0 else 0.0
        
        per_cat_v2[cat] = {
            "ground_truth_count": tp + fn,
            "predicted_count": tp + fp,
            "true_positives": tp,
            "precision_pct": round(prec, 2),
            "recall_pct": round(rec, 2),
            "f1_score": round(f1, 2)
        }
        f1_list_v2.append(f1)
        rec_list_v2.append(rec)
        
    macro_f1_5 = round(float(np.mean(f1_list_v2)), 2)
    bal_acc_5 = round(float(np.mean(rec_list_v2)), 2)
    
    macro_f1_4 = round(float(np.mean([per_cat_v2[c]["f1_score"] for c in CATEGORIES_4])), 2)
    bal_acc_4 = round(float(np.mean([per_cat_v2[c]["recall_pct"] for c in CATEGORIES_4])), 2)

    results_doc = {
        "benchmark_comparison": {
            "full_5_category": {
                "baseline_top1_pct": 26.73,
                "v2_top1_pct": round((top1_v2_5 / total_5) * 100.0, 2),
                "top1_delta_pct": round((top1_v2_5 / total_5) * 100.0 - 26.73, 2),
                "baseline_top2_pct": 65.35,
                "v2_top2_pct": round((top2_v2_5 / total_5) * 100.0, 2),
                "top2_delta_pct": round((top2_v2_5 / total_5) * 100.0 - 65.35, 2),
                "baseline_macro_f1": 22.83,
                "v2_macro_f1": macro_f1_5,
                "macro_f1_delta": round(macro_f1_5 - 22.83, 2),
                "baseline_balanced_acc_pct": 23.53,
                "v2_balanced_acc_pct": bal_acc_5
            },
            "observable_4_category": {
                "baseline_top1_pct": 28.72,
                "v2_top1_pct": round((top1_v2_4 / total_4) * 100.0, 2),
                "top1_delta_pct": round((top1_v2_4 / total_4) * 100.0 - 28.72, 2),
                "baseline_top2_pct": 70.21,
                "v2_top2_pct": round((top2_v2_4 / total_4) * 100.0, 2),
                "top2_delta_pct": round((top2_v2_4 / total_4) * 100.0 - 70.21, 2),
                "baseline_macro_f1": 28.54,
                "v2_macro_f1": macro_f1_4,
                "macro_f1_delta": round(macro_f1_4 - 28.54, 2),
                "baseline_balanced_acc_pct": 29.41,
                "v2_balanced_acc_pct": bal_acc_4
            }
        },
        "error_audit_resolution": {
            "arbitration_errors_fixed_count": arbitration_errors_fixed,
            "arbitration_errors_fixed_pct": f"{arbitration_errors_fixed} / 39 ({arbitration_errors_fixed/39*100:.1f}%)",
            "new_regressions_introduced_count": new_regressions_introduced,
            "net_correct_case_gain": arbitration_errors_fixed - new_regressions_introduced,
            "causal_chain_errors_fixed_count": causal_chain_errors_fixed,
            "arbitration_errors_remaining_count": 39 - arbitration_errors_fixed
        },
        "per_category_metrics_v2": per_cat_v2,
        "confusion_matrix_v2": {k: dict(v) for k, v in cm_v2.items()},
        "case_diffs": case_diffs
    }
    
    return results_doc

def generate_causal_html_report(results, output_path):
    cmp5 = results["benchmark_comparison"]["full_5_category"]
    cmp4 = results["benchmark_comparison"]["observable_4_category"]
    res = results["error_audit_resolution"]
    pc = results["per_category_metrics_v2"]
    cm = results["confusion_matrix_v2"]
    diffs = results["case_diffs"]
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Causal Precedence Hierarchy (v2) Evaluation Report</title>
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
  .badge-gain {{ background: #064e3b; color: #a7f3d0; border: 1px solid #10b981; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }}
  .badge-reg {{ background: #450a0a; color: #fecaca; border: 1px solid #ef4444; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }}
  .badge-same {{ color: #94a3b8; font-size: 11px; }}
</style>
</head>
<body>
<h1>Causal Precedence Hierarchy (v2) Evaluation Report</h1>
<div style="color: #94a3b8; font-size: 14px;">
  Evaluating the 3-tier causal precedence arbitration layer against the baseline arbitration across all 101 benchmark cases.
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">4-Category Top-1 (v2 vs Base)</div>
    <div class="card-val" style="color: #4ade80;">{cmp4['v2_top1_pct']}%</div>
    <div class="card-sub">{cmp4['top1_delta_pct']:+0.2f}% vs {cmp4['baseline_top1_pct']}% baseline</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Arbitration Errors Fixed</div>
    <div class="card-val" style="color: #38bdf8;">{res['arbitration_errors_fixed_pct']}</div>
    <div class="card-sub">{res['causal_chain_errors_fixed_count']} causal-chain errors resolved</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">New Regressions</div>
    <div class="card-val" style="color: #4ade80;">{res['new_regressions_introduced_count']} cases</div>
    <div class="card-sub"><span class="badge-gain">NET GAIN: +{res['net_correct_case_gain']} CASES</span></div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">4-Category Top-2 (v2 vs Base)</div>
    <div class="card-val" style="color: #38bdf8;">{cmp4['v2_top2_pct']}%</div>
    <div class="card-sub">{cmp4['top2_delta_pct']:+0.2f}% vs {cmp4['baseline_top2_pct']}% baseline</div>
  </div>
</div>

<h2>1. Overall Benchmark Accuracy Comparison (Baseline vs. Causal v2)</h2>
<table>
  <thead>
    <tr>
      <th>Evaluation Metric</th>
      <th>Baseline Arbitrator</th>
      <th>Causal Precedence v2</th>
      <th>Absolute Delta</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>4-Category Observable Top-1 Accuracy</strong></td>
      <td>{cmp4['baseline_top1_pct']}%</td>
      <td style="color:#4ade80; font-weight:bold;">{cmp4['v2_top1_pct']}%</td>
      <td style="color:#4ade80; font-weight:bold;">{cmp4['top1_delta_pct']:+0.2f}%</td>
    </tr>
    <tr>
      <td><strong>4-Category Observable Top-2 Accuracy</strong></td>
      <td>{cmp4['baseline_top2_pct']}%</td>
      <td style="color:#38bdf8; font-weight:bold;">{cmp4['v2_top2_pct']}%</td>
      <td style="color:#38bdf8; font-weight:bold;">{cmp4['top2_delta_pct']:+0.2f}%</td>
    </tr>
    <tr>
      <td><strong>4-Category Observable Macro F1</strong></td>
      <td>{cmp4['baseline_macro_f1']}</td>
      <td style="color:#4ade80; font-weight:bold;">{cmp4['v2_macro_f1']}</td>
      <td style="color:#4ade80; font-weight:bold;">{cmp4['macro_f1_delta']:+0.2f}</td>
    </tr>
    <tr>
      <td><strong>Full 5-Category Top-1 Accuracy</strong></td>
      <td>{cmp5['baseline_top1_pct']}%</td>
      <td style="color:#4ade80; font-weight:bold;">{cmp5['v2_top1_pct']}%</td>
      <td style="color:#4ade80; font-weight:bold;">{cmp5['top1_delta_pct']:+0.2f}%</td>
    </tr>
    <tr>
      <td><strong>Full 5-Category Top-2 Accuracy</strong></td>
      <td>{cmp5['baseline_top2_pct']}%</td>
      <td style="color:#38bdf8; font-weight:bold;">{cmp5['v2_top2_pct']}%</td>
      <td style="color:#38bdf8; font-weight:bold;">{cmp5['top2_delta_pct']:+0.2f}%</td>
    </tr>
  </tbody>
</table>

<h2>2. Category-Level Performance (v2)</h2>
<table>
  <thead>
    <tr>
      <th>Ground Truth Category</th>
      <th>Benchmark Cases</th>
      <th>True Positives</th>
      <th>Precision</th>
      <th>Recall</th>
      <th>F1 Score</th>
    </tr>
  </thead>
  <tbody>
"""
    for cat_name, p in pc.items():
        is_hk = (cat_name == "Repeated hotkey")
        style = "background: #182234; font-style: italic;" if is_hk else ""
        html += f"""
    <tr style="{style}">
      <td style="font-weight:bold; color:{'#94a3b8' if is_hk else '#38bdf8'};">{cat_name} {'(Visually Unsupported)' if is_hk else ''}</td>
      <td>{p['ground_truth_count']}</td>
      <td style="font-weight:bold; color:#4ade80;">{p['true_positives']}</td>
      <td>{p['precision_pct']:.1f}%</td>
      <td>{p['recall_pct']:.1f}%</td>
      <td style="font-weight:bold; color:#38bdf8;">{p['f1_score']:.1f}</td>
    </tr>
"""
    html += """
  </tbody>
</table>

<h2>3. 5-Class Confusion Matrix (v2)</h2>
<table>
  <thead>
    <tr>
      <th>Ground Truth \\ Predicted</th>
      <th>Misalignment</th>
      <th>Overlapping</th>
      <th>Truncation</th>
      <th>Untranslation</th>
      <th>Repeated hotkey</th>
      <th>Abstained / No Evidence</th>
    </tr>
  </thead>
  <tbody>
"""
    for gt_cat in CATEGORIES_5:
        row = cm.get(gt_cat, {})
        html += f"""
    <tr>
      <td style="font-weight:bold; color:#38bdf8;">{gt_cat}</td>
      <td>{row.get('Misalignment', 0)}</td>
      <td>{row.get('Overlapping', 0)}</td>
      <td>{row.get('Truncation', 0)}</td>
      <td>{row.get('Untranslation', 0)}</td>
      <td>{row.get('Repeated hotkey', 0)}</td>
      <td style="color:#f59e0b;">{row.get('NO_STRONG_OBSERVABLE_DEFECT', 0)}</td>
    </tr>
"""
    html += """
  </tbody>
</table>

<h2>4. Case-by-Case Diff Sample (Baseline vs. Causal v2)</h2>
<table>
  <thead>
    <tr>
      <th>ID</th>
      <th>Product / Folder (Lang)</th>
      <th>Ground Truth</th>
      <th>Baseline Primary</th>
      <th>v2 Primary</th>
      <th>Correction Status</th>
      <th>Explanation of Change</th>
    </tr>
  </thead>
  <tbody>
"""
    for d in diffs[:35]:
        if d["corrected"]:
            status_badge = "<span class='badge-gain'>CORRECTED (+1)</span>"
        elif d["new_error"]:
            status_badge = "<span class='badge-reg'>REGRESSION (-1)</span>"
        elif d["changed"]:
            status_badge = "<span class='badge-arb'>SHIFTED (INCORRECT)</span>"
        else:
            status_badge = "<span class='badge-same'>UNCHANGED</span>"
            
        html += f"""
    <tr>
      <td style="font-weight:bold;">#{d['case_id']}</td>
      <td>{d['product']} / {d['folder']} ({d['language']})</td>
      <td style="font-weight:bold; color:#38bdf8;">{d['ground_truth']}</td>
      <td>{d['baseline_primary']}</td>
      <td style="font-weight:bold;">{d['v2_primary']}</td>
      <td>{status_badge}</td>
      <td style="font-size:11px; color:#cbd5e1;">{d['reason_for_change']}</td>
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
    results = evaluate_causal_v2()
    
    with open(OUTPUT_RESULTS_JSON, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"Saved causal arbitration v2 results JSON to {OUTPUT_RESULTS_JSON.resolve()}")
    
    generate_causal_html_report(results, OUTPUT_REPORT_HTML)
    print(f"Saved visual HTML report to {OUTPUT_REPORT_HTML.resolve()}")

    cmp5 = results["benchmark_comparison"]["full_5_category"]
    cmp4 = results["benchmark_comparison"]["observable_4_category"]
    res = results["error_audit_resolution"]

    print("\n" + "="*75)
    print("CAUSAL PRECEDENCE ARBITRATION V2 EVALUATION SUMMARY")
    print("="*75)
    print(f"1. 4-Category Top-1 Accuracy : {cmp4['v2_top1_pct']}% (Baseline: {cmp4['baseline_top1_pct']}%, Delta: {cmp4['top1_delta_pct']:+0.2f}%)")
    print(f"2. 4-Category Top-2 Accuracy : {cmp4['v2_top2_pct']}% (Baseline: {cmp4['baseline_top2_pct']}%, Delta: {cmp4['top2_delta_pct']:+0.2f}%)")
    print(f"3. 4-Category Macro F1       : {cmp4['v2_macro_f1']} (Baseline: {cmp4['baseline_macro_f1']}, Delta: {cmp4['macro_f1_delta']:+0.2f})")
    print(f"4. Full 5-Category Top-1     : {cmp5['v2_top1_pct']}% (Baseline: {cmp5['baseline_top1_pct']}%, Delta: {cmp5['top1_delta_pct']:+0.2f}%)")
    print(f"5. Full 5-Category Top-2     : {cmp5['v2_top2_pct']}% (Baseline: {cmp5['baseline_top2_pct']}%, Delta: {cmp5['top2_delta_pct']:+0.2f}%)")
    print(f"6. Arbitration Errors Fixed  : {res['arbitration_errors_fixed_pct']}")
    print(f"7. New Regressions           : {res['new_regressions_introduced_count']} cases")
    print(f"8. Net Correct Case Gain     : +{res['net_correct_case_gain']} cases")
    print("="*75 + "\n")

if __name__ == '__main__':
    main()
