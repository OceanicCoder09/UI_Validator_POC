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
from backend.evidence_arbitration_causal_v2 import CausalEvidenceArbitrator as ArbitratorV2
from backend.evidence_arbitration_causal_v3 import CausalArbitratorV3 as ArbitratorV3

MISALIGN_PATH = pathlib.Path('backend/misalignment_evidence_v2.json')
MOVEMENT_PATH = pathlib.Path('backend/movement_pattern_analysis.json')
OVERLAP_PATH = pathlib.Path('backend/overlap_evidence_v2.json')
TRUNC_PATH = pathlib.Path('backend/truncation_evidence_v2.json')
UNTRANS_PATH = pathlib.Path('backend/untranslation_evidence_v2.json')
HOTKEY_PATH = pathlib.Path('backend/hotkey_evidence_v2.json')
RELATIONSHIP_PATH = pathlib.Path('backend/relationship_evidence_all_cases.json')
V2_RESULTS_PATH = pathlib.Path('backend/evidence_arbitration_causal_v2_results.json')
BASELINE_PATH = pathlib.Path('backend/end_to_end_evaluation_results.json')

OUTPUT_V3_RESULTS_JSON = pathlib.Path('backend/causal_v3_results.json')
OUTPUT_V3_ATTRIBUTION_JSON = pathlib.Path('backend/causal_v3_error_attribution.json')
OUTPUT_V3_REPORT_HTML = pathlib.Path('backend/causal_v3_comparison_report.html')

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

def load_all_payloads():
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
    with open(V2_RESULTS_PATH, 'r', encoding='utf-8') as f:
        v2_results = {c["case_id"]: c for c in json.load(f)["case_diffs"]}
    with open(BASELINE_PATH, 'r', encoding='utf-8') as f:
        base_results = {t["case_id"]: t for t in json.load(f)["case_traces"]}
        
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
            "v2_diff": v2_results.get(cid, {}),
            "base_trace": base_results.get(cid, {})
        })
    return payloads

def run_v3_evaluation():
    payloads = load_all_payloads()
    print(f"Evaluating Causal Precedence Arbitrator v3 across {len(payloads)} benchmark cases...", flush=True)

    engine = EvidenceEngine()
    arbitrator_v3 = ArbitratorV3()
    
    total_5 = len(payloads)
    obs_4 = [p for p in payloads if p["ground_truth"] in CATEGORIES_4]
    total_4 = len(obs_4)
    
    top1_v3_5 = 0
    top2_v3_5 = 0
    top1_v3_4 = 0
    top2_v3_4 = 0
    abstention_v3 = 0
    
    cm_v3 = collections.defaultdict(lambda: collections.defaultdict(int))
    
    corrections_count = 0
    regressions_count = 0
    gt_in_secondary_count = 0
    gt_absent_count = 0
    
    case_diffs_v3 = []
    error_attribution_cases = []
    
    for p in payloads:
        cid = p["case_id"]
        gt = p["ground_truth"]
        v2_diff = p["v2_diff"]
        v2_pred = v2_diff.get("v2_primary")
        v2_sec = v2_diff.get("v2_secondary", [])
        is_v2_top1 = (v2_pred == gt)
        
        eval_output = engine.evaluate_case(cid, p)
        ev_results = eval_output["evidence_results"]
        
        decision_v3 = arbitrator_v3.arbitrate(cid, ev_results, p)
        pred_v3 = decision_v3.primary_category
        sec_v3 = [s["category"] for s in decision_v3.secondary_categories]
        
        is_top1_v3 = (pred_v3 == gt)
        is_top2_v3 = is_top1_v3 or (gt in sec_v3)
        
        if is_top1_v3:
            top1_v3_5 += 1
            if gt in CATEGORIES_4:
                top1_v3_4 += 1
        if is_top2_v3:
            top2_v3_5 += 1
            if gt in CATEGORIES_4:
                top2_v3_4 += 1
        if pred_v3 == "NO_STRONG_OBSERVABLE_DEFECT":
            abstention_v3 += 1
            
        cm_v3[gt][pred_v3] += 1
        
        # Diff tracking (v2 vs v3)
        corrected = (not is_v2_top1 and is_top1_v3)
        regression = (is_v2_top1 and not is_top1_v3)
        changed = (v2_pred != pred_v3)
        
        if corrected:
            corrections_count += 1
        if regression:
            regressions_count += 1
        if not is_top1_v3:
            if gt in sec_v3:
                gt_in_secondary_count += 1
            else:
                gt_absent_count += 1
                
        diff_entry = {
            "case_id": cid,
            "product": p["product"],
            "folder": p["folder"],
            "language": p["language"],
            "ground_truth": gt,
            "v2_primary": v2_pred,
            "v3_primary": pred_v3,
            "v2_secondary": v2_sec,
            "v3_secondary": sec_v3,
            "is_v2_top1": is_v2_top1,
            "is_v3_top1": is_top1_v3,
            "corrected": corrected,
            "regression": regression,
            "changed": changed,
            "explanation": decision_v3.explanation
        }
        case_diffs_v3.append(diff_entry)
        
        # Error attribution record
        strengths_v3 = {
            cname: cdata.get("evidence_strength", 0.0)
            for cname, cdata in ev_results.items()
        }
        gt_strength = strengths_v3.get(gt, 0.0) if gt != "Repeated hotkey" else -1.0
        win_strength = strengths_v3.get(pred_v3, 0.0) if pred_v3 != "NO_STRONG_OBSERVABLE_DEFECT" else 0.0
        
        if is_top1_v3:
            err_class = "CORRECT"
            res_bucket = "NONE"
        elif gt == "Repeated hotkey":
            err_class = "VISUALLY_UNSUPPORTED"
            res_bucket = "FUNDAMENTALLY_UNOBSERVABLE"
        elif pred_v3 == "NO_STRONG_OBSERVABLE_DEFECT":
            err_class = "AMBIGUOUS_INSUFFICIENT_EVIDENCE"
            res_bucket = "EVIDENCE_EXTRACTION_REQUIRED"
        elif gt in sec_v3:
            err_class = "ARBITRATION_RANKING_FAILURE"
            res_bucket = "ARBITRATION_FIXABLE"
        else:
            err_class = "EVIDENCE_COVERAGE_FAILURE"
            res_bucket = "EVIDENCE_EXTRACTION_REQUIRED"
            
        error_attribution_cases.append({
            "case_id": cid,
            "ground_truth": gt,
            "v3_primary": pred_v3,
            "v3_secondary": sec_v3,
            "gt_status": "PRIMARY" if is_top1_v3 else ("SECONDARY" if gt in sec_v3 else "ABSENT"),
            "gt_strength": gt_strength,
            "winner_strength": win_strength,
            "error_classification": err_class,
            "resolution_bucket": res_bucket,
            "explanation": decision_v3.explanation
        })

    # --------------------------------------------------------------------------
    # METRICS SUMMARY COMPARISON (Base vs v2 vs v3)
    # --------------------------------------------------------------------------
    
    per_cat_v3 = {}
    f1_list_v3 = []
    rec_list_v3 = []
    for cat in CATEGORIES_5:
        tp = cm_v3[cat][cat]
        fp = sum(cm_v3[other][cat] for other in CATEGORIES_5 if other != cat)
        fn = sum(cm_v3[cat][pred] for pred in list(cm_v3[cat].keys()) if pred != cat)
        
        prec = (tp / max(1, tp + fp)) * 100.0 if (tp + fp) > 0 else 0.0
        rec = (tp / max(1, tp + fn)) * 100.0 if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / max(1e-7, prec + rec)) if (prec + rec) > 0 else 0.0
        
        per_cat_v3[cat] = {
            "ground_truth_count": tp + fn,
            "predicted_count": tp + fp,
            "true_positives": tp,
            "precision_pct": round(prec, 2),
            "recall_pct": round(rec, 2),
            "f1_score": round(f1, 2)
        }
        f1_list_v3.append(f1)
        rec_list_v3.append(rec)
        
    macro_f1_5 = round(float(np.mean(f1_list_v3)), 2)
    bal_acc_5 = round(float(np.mean(rec_list_v3)), 2)
    
    macro_f1_4 = round(float(np.mean([per_cat_v3[c]["f1_score"] for c in CATEGORIES_4])), 2)
    bal_acc_4 = round(float(np.mean([per_cat_v3[c]["recall_pct"] for c in CATEGORIES_4])), 2)

    results_v3 = {
        "benchmark_comparison": {
            "full_5_category": {
                "baseline_top1_pct": 26.73,
                "v2_top1_pct": 29.70,
                "v3_top1_pct": round((top1_v3_5 / total_5) * 100.0, 2),
                "v3_vs_v2_top1_delta_pct": round((top1_v3_5 / total_5) * 100.0 - 29.70, 2),
                "baseline_top2_pct": 65.35,
                "v2_top2_pct": 66.34,
                "v3_top2_pct": round((top2_v3_5 / total_5) * 100.0, 2),
                "v3_vs_v2_top2_delta_pct": round((top2_v3_5 / total_5) * 100.0 - 66.34, 2),
                "v3_macro_f1": macro_f1_5,
                "v3_balanced_acc_pct": bal_acc_5
            },
            "observable_4_category": {
                "baseline_top1_pct": 28.72,
                "v2_top1_pct": 31.91,
                "v3_top1_pct": round((top1_v3_4 / total_4) * 100.0, 2),
                "v3_vs_v2_top1_delta_pct": round((top1_v3_4 / total_4) * 100.0 - 31.91, 2),
                "baseline_top2_pct": 70.21,
                "v2_top2_pct": 71.28,
                "v3_top2_pct": round((top2_v3_4 / total_4) * 100.0, 2),
                "v3_vs_v2_top2_delta_pct": round((top2_v3_4 / total_4) * 100.0 - 71.28, 2),
                "v3_macro_f1": macro_f1_4,
                "v3_balanced_acc_pct": bal_acc_4
            }
        },
        "v3_controlled_diff_summary": {
            "corrections_over_v2_count": corrections_count,
            "regressions_over_v2_count": regressions_count,
            "net_v3_gain_cases": corrections_count - regressions_count,
            "remaining_arbitration_errors_gt_in_secondary": gt_in_secondary_count,
            "remaining_coverage_errors_gt_absent": gt_absent_count,
            "total_remaining_errors": total_5 - top1_v3_5
        },
        "per_category_metrics_v3": per_cat_v3,
        "confusion_matrix_v3": {k: dict(v) for k, v in cm_v3.items()},
        "case_diffs": case_diffs_v3
    }
    
    attribution_doc = {
        "summary": results_v3["v3_controlled_diff_summary"],
        "cases": error_attribution_cases
    }
    
    return results_v3, attribution_doc

def generate_v3_html_report(results, output_path):
    cmp5 = results["benchmark_comparison"]["full_5_category"]
    cmp4 = results["benchmark_comparison"]["observable_4_category"]
    diff_sum = results["v3_controlled_diff_summary"]
    pc = results["per_category_metrics_v3"]
    cm = results["confusion_matrix_v3"]
    diffs = results["case_diffs"]
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Causal Precedence Arbitrator v3 Comparison Report</title>
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
<h1>Causal Precedence Arbitrator v3 Comparison Report</h1>
<div style="color: #94a3b8; font-size: 14px;">
  Evaluating generalized context-dependent physical precedence rules (v3) against baseline and v2 across all 101 benchmark cases.
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">4-Category Top-1 (v3 vs v2 vs Base)</div>
    <div class="card-val" style="color: #4ade80;">{cmp4['v3_top1_pct']}%</div>
    <div class="card-sub">{cmp4['v3_vs_v2_top1_delta_pct']:+0.2f}% vs v2 ({cmp4['v2_top1_pct']}%) / +{cmp4['v3_top1_pct']-cmp4['baseline_top1_pct']:.2f}% vs Base</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">4-Category Top-2 Accuracy</div>
    <div class="card-val" style="color: #38bdf8;">{cmp4['v3_top2_pct']}%</div>
    <div class="card-sub">{cmp4['v3_vs_v2_top2_delta_pct']:+0.2f}% vs v2 ({cmp4['v2_top2_pct']}%)</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">v3 Net Case Gain</div>
    <div class="card-val" style="color: #4ade80;">+{diff_sum['net_v3_gain_cases']} Cases</div>
    <div class="card-sub">{diff_sum['corrections_over_v2_count']} corrected / {diff_sum['regressions_over_v2_count']} regressions</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Full 5-Category Top-1</div>
    <div class="card-val" style="color: #f59e0b;">{cmp5['v3_top1_pct']}%</div>
    <div class="card-sub">{cmp5['v3_vs_v2_top1_delta_pct']:+0.2f}% vs v2 ({cmp5['v2_top1_pct']}%)</div>
  </div>
</div>

<h2>1. 3-Way Architecture Evolution (Baseline vs. v2 vs. v3)</h2>
<table>
  <thead>
    <tr>
      <th>Architecture Stage</th>
      <th>4-Category Observable Top-1</th>
      <th>4-Category Observable Top-2</th>
      <th>Full 5-Category Top-1</th>
      <th>Full 5-Category Top-2</th>
      <th>Macro F1 (4-Cat)</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Baseline Un-Tuned Arbitrator</strong></td>
      <td>28.72%</td>
      <td>70.21%</td>
      <td>26.73%</td>
      <td>65.35%</td>
      <td>28.54</td>
    </tr>
    <tr>
      <td><strong>Causal Precedence v2</strong></td>
      <td>31.91%</td>
      <td>71.28%</td>
      <td>29.70%</td>
      <td>66.34%</td>
      <td>31.01</td>
    </tr>
    <tr style="background: #182842;">
      <td style="color:#38bdf8; font-weight:bold;">Causal Precedence v3 (Context-Dependent)</td>
      <td style="color:#4ade80; font-weight:bold;">{cmp4['v3_top1_pct']}%</td>
      <td style="color:#38bdf8; font-weight:bold;">{cmp4['v3_top2_pct']}%</td>
      <td style="color:#4ade80; font-weight:bold;">{cmp5['v3_top1_pct']}%</td>
      <td style="color:#38bdf8; font-weight:bold;">{cmp5['v3_top2_pct']}%</td>
      <td style="color:#4ade80; font-weight:bold;">{cmp4['v3_macro_f1']}</td>
    </tr>
  </tbody>
</table>

<h2>2. Category-Level Performance (v3)</h2>
<table>
  <thead>
    <tr>
      <th>Ground Truth Category</th>
      <th>Benchmark N</th>
      <th>Predicted Count</th>
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
      <td>{p['predicted_count']}</td>
      <td style="font-weight:bold; color:#4ade80;">{p['true_positives']}</td>
      <td>{p['precision_pct']:.1f}%</td>
      <td>{p['recall_pct']:.1f}%</td>
      <td style="font-weight:bold; color:#38bdf8;">{p['f1_score']:.1f}</td>
    </tr>
"""
    html += """
  </tbody>
</table>

<h2>3. 5-Class Confusion Matrix (v3)</h2>
<table>
  <thead>
    <tr>
      <th>Ground Truth \\ Predicted</th>
      <th>Misalignment</th>
      <th>Overlapping</th>
      <th>Truncation</th>
      <th>Untranslation</th>
      <th>Repeated hotkey</th>
      <th>Abstained / Insufficient</th>
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

<h2>4. Case-by-Case Diff Sample (v2 vs. v3)</h2>
<table>
  <thead>
    <tr>
      <th>ID</th>
      <th>Product / Lang</th>
      <th>Ground Truth</th>
      <th>v2 Primary</th>
      <th>v3 Primary</th>
      <th>Status</th>
      <th>Causal Reasoning Trace</th>
    </tr>
  </thead>
  <tbody>
"""
    for d in diffs[:35]:
        if d["corrected"]:
            status_badge = "<span class='badge-gain'>CORRECTED (+1)</span>"
        elif d["regression"]:
            status_badge = "<span class='badge-reg'>REGRESSION (-1)</span>"
        elif d["changed"]:
            status_badge = "<span class='badge-same'>SHIFTED (INCORRECT)</span>"
        else:
            status_badge = "<span class='badge-same'>UNCHANGED</span>"
            
        html += f"""
    <tr>
      <td style="font-weight:bold;">#{d['case_id']}</td>
      <td>{d['product']} ({d['language']})</td>
      <td style="font-weight:bold; color:#38bdf8;">{d['ground_truth']}</td>
      <td>{d['v2_primary']}</td>
      <td style="font-weight:bold;">{d['v3_primary']}</td>
      <td>{status_badge}</td>
      <td style="font-size:11px; color:#cbd5e1;">{d['explanation']}</td>
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
    results_v3, attribution_doc = run_v3_evaluation()
    
    with open(OUTPUT_V3_RESULTS_JSON, 'w', encoding='utf-8') as f:
        json.dump(results_v3, f, indent=2)
    print(f"Saved causal v3 results JSON to {OUTPUT_V3_RESULTS_JSON.resolve()}")
    
    with open(OUTPUT_V3_ATTRIBUTION_JSON, 'w', encoding='utf-8') as f:
        json.dump(attribution_doc, f, indent=2)
    print(f"Saved causal v3 attribution JSON to {OUTPUT_V3_ATTRIBUTION_JSON.resolve()}")
    
    generate_v3_html_report(results_v3, OUTPUT_V3_REPORT_HTML)
    print(f"Saved visual HTML report to {OUTPUT_V3_REPORT_HTML.resolve()}")

    cmp5 = results_v3["benchmark_comparison"]["full_5_category"]
    cmp4 = results_v3["benchmark_comparison"]["observable_4_category"]
    diff_sum = results_v3["v3_controlled_diff_summary"]

    print("\n" + "="*75)
    print("CAUSAL PRECEDENCE ARBITRATION V3 EVALUATION SUMMARY")
    print("="*75)
    print(f"1. 4-Category Observable Top-1 : {cmp4['v3_top1_pct']}% (v2: {cmp4['v2_top1_pct']}%, Base: {cmp4['baseline_top1_pct']}%, Delta: {cmp4['v3_vs_v2_top1_delta_pct']:+0.2f}%)")
    print(f"2. 4-Category Observable Top-2 : {cmp4['v3_top2_pct']}% (v2: {cmp4['v2_top2_pct']}%, Base: {cmp4['baseline_top2_pct']}%, Delta: {cmp4['v3_vs_v2_top2_delta_pct']:+0.2f}%)")
    print(f"3. 4-Category Observable Macro F1: {cmp4['v3_macro_f1']} (v2: {results_v3['benchmark_comparison']['observable_4_category']['v3_macro_f1']})")
    print(f"4. Full 5-Category Top-1       : {cmp5['v3_top1_pct']}% (v2: {cmp5['v2_top1_pct']}%, Base: {cmp5['baseline_top1_pct']}%, Delta: {cmp5['v3_vs_v2_top1_delta_pct']:+0.2f}%)")
    print(f"5. Full 5-Category Top-2       : {cmp5['v3_top2_pct']}% (v2: {cmp5['v2_top2_pct']}%, Base: {cmp5['baseline_top2_pct']}%, Delta: {cmp5['v3_vs_v2_top2_delta_pct']:+0.2f}%)")
    print(f"6. v3 Corrections over v2      : {diff_sum['corrections_over_v2_count']} cases")
    print(f"7. v3 Regressions over v2      : {diff_sum['regressions_over_v2_count']} cases")
    print(f"8. Net v3 Case Gain            : +{diff_sum['net_v3_gain_cases']} cases")
    print("="*75 + "\n")

if __name__ == '__main__':
    main()
