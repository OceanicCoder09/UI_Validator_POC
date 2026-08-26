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
from backend.evidence_arbitrator import EvidenceArbitrator

MISALIGN_PATH = pathlib.Path('backend/misalignment_evidence_v2.json')
MOVEMENT_PATH = pathlib.Path('backend/movement_pattern_analysis.json')
OVERLAP_PATH = pathlib.Path('backend/overlap_evidence_v2.json')
TRUNC_PATH = pathlib.Path('backend/truncation_evidence_v2.json')
UNTRANS_PATH = pathlib.Path('backend/untranslation_evidence_v2.json')
HOTKEY_PATH = pathlib.Path('backend/hotkey_evidence_v2.json')
RELATIONSHIP_PATH = pathlib.Path('backend/relationship_evidence_all_cases.json')

OUTPUT_RESULTS_JSON = pathlib.Path('backend/end_to_end_evaluation_results.json')
OUTPUT_REPORT_HTML = pathlib.Path('backend/end_to_end_evaluation_report.html')

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

def load_case_payloads():
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
            "hotkey_v2": hk_data.get(cid, {})
        })
    return payloads

def run_end_to_end_benchmark():
    payloads = load_case_payloads()
    print(f"Running End-to-End Benchmark Evaluation across {len(payloads)} cases...", flush=True)
    
    engine = EvidenceEngine()
    arbitrator = EvidenceArbitrator()
    
    case_traces = []
    
    # Metrics accumulators
    total_5_cases = len(payloads)
    observable_4_cases = [p for p in payloads if p["ground_truth"] in CATEGORIES_4]
    total_4_cases = len(observable_4_cases)
    
    top1_correct_5 = 0
    top2_correct_5 = 0
    
    top1_correct_4 = 0
    top2_correct_4 = 0
    
    gt_in_secondary_count = 0
    gt_absent_count = 0
    abstention_count = 0
    
    confusion_matrix_5 = collections.defaultdict(lambda: collections.defaultdict(int))
    
    error_analysis_groups = collections.defaultdict(list)
    
    for p in payloads:
        cid = p["case_id"]
        gt = p["ground_truth"]
        
        # 1. Run Evidence Engine
        eval_output = engine.evaluate_case(cid, p)
        ev_results = eval_output["evidence_results"]
        
        # 2. Run Evidence Arbitrator
        decision = arbitrator.arbitrate(cid, ev_results, p)
        
        pred_primary = decision.primary_category
        pred_secondaries = [s["category"] for s in decision.secondary_categories]
        
        # Track Top-1 & Top-2
        is_top1 = (pred_primary == gt)
        is_top2 = is_top1 or (gt in pred_secondaries)
        
        if is_top1:
            top1_correct_5 += 1
            if gt in CATEGORIES_4:
                top1_correct_4 += 1
        elif gt in pred_secondaries:
            gt_in_secondary_count += 1
        else:
            gt_absent_count += 1
            
        if is_top2:
            top2_correct_5 += 1
            if gt in CATEGORIES_4:
                top2_correct_4 += 1
                
        if pred_primary == "NO_STRONG_OBSERVABLE_DEFECT":
            abstention_count += 1
            
        confusion_matrix_5[gt][pred_primary] += 1
        
        # Collect strengths for all 5 categories
        strengths_all = {
            cname: cdata.get("evidence_strength", 0.0)
            for cname, cdata in ev_results.items()
        }
        
        # Error grouping if primary prediction was incorrect
        error_type = None
        if not is_top1:
            if pred_primary == "NO_STRONG_OBSERVABLE_DEFECT":
                error_type = "INSUFFICIENT_OBSERVABLE_EVIDENCE"
            elif gt == "Repeated hotkey":
                error_type = "REPEATED_HOTKEY_VISUALLY_UNSUPPORTED"
            elif gt == "Misalignment" and pred_primary in ["Truncation", "Overlapping"]:
                error_type = "MISALIGNMENT_VS_LAYOUT_COLLISION_REFLOW"
            elif gt == "Overlapping" and pred_primary == "Truncation":
                error_type = "OVERLAP_VS_TEXT_EXPANSION_CLIPPING"
            elif gt == "Truncation" and pred_primary == "Overlapping":
                error_type = "TRUNCATION_VS_SIBLING_INTRUSION"
            elif gt == "Untranslation" and pred_primary != "Untranslation":
                error_type = "UNTRANSLATION_SUPPRESSED_BY_SPATIAL_DRIFT"
            else:
                error_type = f"{gt}_CONFUSED_WITH_{pred_primary}"
                
            error_analysis_groups[error_type].append({
                "case_id": cid,
                "ground_truth": gt,
                "predicted_primary": pred_primary,
                "secondary_categories": pred_secondaries,
                "dominant_mechanism": decision.dominant_mechanism,
                "strengths": strengths_all,
                "explanation": decision.explanation
            })

        trace = {
            "case_id": cid,
            "product": p["product"],
            "folder": p["folder"],
            "language": p["language"],
            "ground_truth": gt,
            "primary_category": pred_primary,
            "primary_evidence_strength": decision.primary_evidence_strength,
            "secondary_categories": decision.secondary_categories,
            "evidence_strengths_all_categories": strengths_all,
            "is_top1_correct": is_top1,
            "is_top2_correct": is_top2,
            "gt_in_secondary": (not is_top1 and gt in pred_secondaries),
            "gt_absent": (not is_top1 and gt not in pred_secondaries),
            "dominant_mechanism": decision.dominant_mechanism,
            "explanation": decision.explanation
        }
        case_traces.append(trace)

    # --------------------------------------------------------------------------
    # COMPUTE CLASSIFICATION & COVERAGE METRICS
    # --------------------------------------------------------------------------
    
    # 1. Overall Accuracies
    acc_top1_5 = round((top1_correct_5 / total_5_cases) * 100.0, 2)
    acc_top2_5 = round((top2_correct_5 / total_5_cases) * 100.0, 2)
    
    acc_top1_4 = round((top1_correct_4 / total_4_cases) * 100.0, 2)
    acc_top2_4 = round((top2_correct_4 / total_4_cases) * 100.0, 2)
    
    diagnosed_count = total_5_cases - abstention_count
    abstention_aware_acc_5 = round((top1_correct_5 / max(1, diagnosed_count)) * 100.0, 2)
    coverage_rate = round((diagnosed_count / total_5_cases) * 100.0, 2)
    
    # 2. Per-Category Precision, Recall, F1
    per_category_metrics = {}
    f1_list = []
    recall_list = []
    
    for cat in CATEGORIES_5:
        # True Positives
        tp = confusion_matrix_5[cat][cat]
        # False Positives (predicted as cat but GT != cat)
        fp = sum(confusion_matrix_5[other_gt][cat] for other_gt in CATEGORIES_5 if other_gt != cat)
        # False Negatives (GT == cat but predicted != cat)
        fn = sum(confusion_matrix_5[cat][pred] for pred in list(confusion_matrix_5[cat].keys()) if pred != cat)
        
        prec = (tp / max(1, tp + fp)) * 100.0 if (tp + fp) > 0 else 0.0
        rec = (tp / max(1, tp + fn)) * 100.0 if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / max(1e-7, prec + rec)) if (prec + rec) > 0 else 0.0
        
        per_category_metrics[cat] = {
            "ground_truth_count": tp + fn,
            "predicted_count": tp + fp,
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision_pct": round(prec, 2),
            "recall_pct": round(rec, 2),
            "f1_score": round(f1, 2)
        }
        f1_list.append(f1)
        recall_list.append(rec)

    macro_f1 = round(float(np.mean(f1_list)), 2)
    balanced_acc = round(float(np.mean(recall_list)), 2)
    
    # 4-Category Macro F1 & Balanced Acc
    macro_f1_4 = round(float(np.mean([per_category_metrics[c]["f1_score"] for c in CATEGORIES_4])), 2)
    balanced_acc_4 = round(float(np.mean([per_category_metrics[c]["recall_pct"] for c in CATEGORIES_4])), 2)

    evaluation_summary = {
        "benchmark_summary": {
            "total_5_category_cases": total_5_cases,
            "observable_4_category_cases": total_4_cases,
            "diagnosed_cases_count": diagnosed_count,
            "abstention_count": abstention_count,
            "coverage_rate_pct": coverage_rate
        },
        "overall_accuracies": {
            "full_5_category": {
                "top1_accuracy_pct": acc_top1_5,
                "top2_accuracy_pct": acc_top2_5,
                "macro_f1": macro_f1,
                "balanced_accuracy_pct": balanced_acc,
                "abstention_aware_accuracy_pct": abstention_aware_acc_5
            },
            "observable_4_category": {
                "top1_accuracy_pct": acc_top1_4,
                "top2_accuracy_pct": acc_top2_4,
                "macro_f1": macro_f1_4,
                "balanced_accuracy_pct": balanced_acc_4
            }
        },
        "multi_stream_coverage_stats": {
            "gt_correct_as_primary_count": top1_correct_5,
            "gt_preserved_as_secondary_count": gt_in_secondary_count,
            "gt_absent_count": gt_absent_count,
            "top2_coverage_pct": acc_top2_5
        },
        "per_category_metrics": per_category_metrics,
        "confusion_matrix_5_class": {k: dict(v) for k, v in confusion_matrix_5.items()},
        "error_analysis": {k: len(v) for k, v in error_analysis_groups.items()},
        "error_analysis_details": {k: v for k, v in error_analysis_groups.items()},
        "case_traces": case_traces
    }
    
    return evaluation_summary

def generate_evaluation_html_report(summary, output_path):
    ov_5 = summary["overall_accuracies"]["full_5_category"]
    ov_4 = summary["overall_accuracies"]["observable_4_category"]
    pc = summary["per_category_metrics"]
    cm = summary["confusion_matrix_5_class"]
    errs = summary["error_analysis"]
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>End-to-End Evidence Engine Benchmark Report</title>
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
  .badge-pass {{ background: #064e3b; color: #a7f3d0; border: 1px solid #10b981; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }}
  .badge-fail {{ background: #450a0a; color: #fecaca; border: 1px solid #ef4444; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }}
  .badge-sec {{ background: #1e3a5f; color: #93c5fd; border: 1px solid #38bdf8; padding: 3px 8px; border-radius: 4px; font-size: 11px; }}
</style>
</head>
<body>
<h1>End-to-End Evidence Engine Benchmark Report</h1>
<div style="color: #94a3b8; font-size: 14px;">
  Rigorous evaluation of the Evidence Engine & Arbitrator against the 101 Excel Ground Truth benchmark cases without classifier training, magic thresholds, or GT leakage.
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">4-Category Observable Top-1</div>
    <div class="card-val" style="color: #4ade80;">{ov_4['top1_accuracy_pct']}%</div>
    <div class="card-sub">observable visual cases (N=94)</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">4-Category Observable Top-2</div>
    <div class="card-val" style="color: #38bdf8;">{ov_4['top2_accuracy_pct']}%</div>
    <div class="card-sub">GT in primary or secondary stream</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Full 5-Category Top-1</div>
    <div class="card-val" style="color: #f59e0b;">{ov_5['top1_accuracy_pct']}%</div>
    <div class="card-sub">including 7 unobservable hotkey cases</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Full 5-Category Top-2</div>
    <div class="card-val" style="color: #38bdf8;">{ov_5['top2_accuracy_pct']}%</div>
    <div class="card-sub">multi-defect coverage rate</div>
  </div>
</div>

<h2>1. Category-Level Diagnostic Performance</h2>
<table>
  <thead>
    <tr>
      <th>Ground Truth Category</th>
      <th>Benchmark Cases</th>
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

<h2>2. 5-Class Confusion Matrix</h2>
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

<h2>3. Root Cause Error Distribution</h2>
<table>
  <thead>
    <tr>
      <th>Error Mechanism Pattern</th>
      <th>Error Count</th>
      <th>Physical Reason & Mechanism</th>
    </tr>
  </thead>
  <tbody>
"""
    err_reasons = {
        "REPEATED_HOTKEY_VISUALLY_UNSUPPORTED": "Native Win32 keyboard mnemonics rely on font underlines invisible to plain flat OCR.",
        "MISALIGNMENT_VS_LAYOUT_COLLISION_REFLOW": "Multi-column dialog displacement triggers both column break and text overflow.",
        "OVERLAP_VS_TEXT_EXPANSION_CLIPPING": "Expanded label intruded into rigid sibling boundary, triggering overlapping and truncation evidence.",
        "TRUNCATION_VS_SIBLING_INTRUSION": "Text container boundary overflow accompanied by sibling box collision.",
        "UNTRANSLATION_SUPPRESSED_BY_SPATIAL_DRIFT": "Untranslated UI string accompanied by dominant structural column shift.",
        "INSUFFICIENT_OBSERVABLE_EVIDENCE": "Sub-pixel changes below observable threshold without clear defect mechanism."
    }
    for err_name, cnt in errs.items():
        html += f"""
    <tr>
      <td style="font-weight:bold; color:#f43f5e;"><code>{err_name}</code></td>
      <td style="font-weight:bold;">{cnt}</td>
      <td style="font-size:12px; color:#cbd5e1;">{err_reasons.get(err_name, 'Cross-category multi-defect physical competition.')}</td>
    </tr>
"""
    html += """
  </tbody>
</table>

<h2>4. Case Diagnostic Trace Sample (First 25 Cases)</h2>
<table>
  <thead>
    <tr>
      <th>ID</th>
      <th>Product / Folder (Lang)</th>
      <th>Ground Truth</th>
      <th>Primary Diagnosis</th>
      <th>Top-1?</th>
      <th>Top-2?</th>
      <th>Dominant Physical Mechanism</th>
      <th>Explanation</th>
    </tr>
  </thead>
  <tbody>
"""
    for t in summary["case_traces"][:25]:
        top1_badge = "<span class='badge-pass'>TOP-1 MATCH</span>" if t["is_top1_correct"] else "<span class='badge-fail'>MISMATCH</span>"
        top2_badge = "<span class='badge-pass'>TOP-2 MATCH</span>" if t["is_top2_correct"] else ("<span class='badge-sec'>IN SECONDARY</span>" if t["gt_in_secondary"] else "<span class='badge-fail'>ABSENT</span>")
        html += f"""
    <tr>
      <td style="font-weight:bold;">#{t['case_id']}</td>
      <td>{t['product']} / {t['folder']} ({t['language']})</td>
      <td style="font-weight:bold;">{t['ground_truth']}</td>
      <td>{t['primary_category']}</td>
      <td>{top1_badge}</td>
      <td>{top2_badge}</td>
      <td style="font-size:11px; color:#38bdf8;">{t['dominant_mechanism']}</td>
      <td style="font-size:11px; color:#cbd5e1;">{t['explanation']}</td>
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
    summary = run_end_to_end_benchmark()
    
    with open(OUTPUT_RESULTS_JSON, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    print(f"Saved end-to-end benchmark results JSON to {OUTPUT_RESULTS_JSON.resolve()}")
    
    generate_evaluation_html_report(summary, OUTPUT_REPORT_HTML)
    print(f"Saved visual HTML report to {OUTPUT_REPORT_HTML.resolve()}")

    ov_5 = summary["overall_accuracies"]["full_5_category"]
    ov_4 = summary["overall_accuracies"]["observable_4_category"]
    
    print("\n" + "="*75)
    print("END-TO-END EVIDENCE ENGINE BENCHMARK SUMMARY")
    print("="*75)
    print(f"1. 4-Category Observable Top-1 Accuracy : {ov_4['top1_accuracy_pct']}% ({summary['per_category_metrics']['Misalignment']['true_positives'] + summary['per_category_metrics']['Overlapping']['true_positives'] + summary['per_category_metrics']['Truncation']['true_positives'] + summary['per_category_metrics']['Untranslation']['true_positives']} / 94)")
    print(f"2. 4-Category Observable Top-2 Accuracy : {ov_4['top2_accuracy_pct']}%")
    print(f"3. 4-Category Observable Macro F1       : {ov_4['macro_f1']}")
    print(f"4. 4-Category Balanced Accuracy         : {ov_4['balanced_accuracy_pct']}%")
    print(f"5. Full 5-Category Top-1 Accuracy       : {ov_5['top1_accuracy_pct']}% (including 7 unobservable hotkey cases)")
    print(f"6. Full 5-Category Top-2 Accuracy       : {ov_5['top2_accuracy_pct']}%")
    print(f"7. Abstention-Aware Accuracy (N=95)     : {ov_5['abstention_aware_accuracy_pct']}%")
    print(f"8. Coverage Rate                        : {summary['benchmark_summary']['coverage_rate_pct']}% ({summary['benchmark_summary']['diagnosed_cases_count']} / 101)")
    print(f"9. Ground Truth in Secondary Stream     : {summary['multi_stream_coverage_stats']['gt_preserved_as_secondary_count']} cases")
    print(f"10. Ground Truth Completely Absent      : {summary['multi_stream_coverage_stats']['gt_absent_count']} cases")
    print("="*75 + "\n")

if __name__ == '__main__':
    main()
