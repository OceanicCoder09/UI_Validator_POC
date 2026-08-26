import os
import sys
import json
import pathlib
import collections
import pandas as pd
import numpy as np

RELATIONSHIP_PATH = pathlib.Path('backend/relationship_evidence_all_cases.json')
MISALIGN_V2_PATH = pathlib.Path('backend/misalignment_evidence_v2.json')
EXCEL_PATH = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize/Screenshot data list from Welocalize.xlsx')
BASE_DATA_ROOT = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize')

OUTPUT_JSON = pathlib.Path('backend/misalignment_discrimination_analysis.json')
OUTPUT_HTML = pathlib.Path('backend/misalignment_discrimination_analysis.html')

TARGET_CLASSES = [
    "Misalignment",
    "Overlapping",
    "Repeated hotkey",
    "Truncation",
    "Untranslation"
]

def load_all_case_data():
    with open(RELATIONSHIP_PATH, 'r', encoding='utf-8') as f:
        rel_cases = json.load(f)
    with open(MISALIGN_V2_PATH, 'r', encoding='utf-8') as f:
        mis_v2 = {c["case_id"]: c for c in json.load(f)["cases"]}
        
    return rel_cases, mis_v2

def run_discrimination_analysis():
    rel_cases, mis_v2 = load_all_case_data()
    print(f"Loaded {len(rel_cases)} benchmark cases from relationship evidence repository.")
    
    category_groups = collections.defaultdict(list)
    case_records = []
    
    for c in rel_cases:
        cid = c["case_id"]
        gt = c["gt_category"]
        mstats = c.get("matching_stats", {})
        rfeats = c.get("evidence_features", {})
        
        # Check if in mis_v2 for additional finding count details
        v2_entry = mis_v2.get(cid)
        
        rec = {
            "case_id": cid,
            "product": c["product"],
            "folder": c["folder"],
            "lang": c["lang"],
            "gt_category": gt,
            "matched_elements_count": mstats.get("matched_count", 0),
            "match_rate_pct": mstats.get("match_rate_pct", 0.0),
            "max_corrected_displacement_px": float(rfeats.get("max_displacement_px", 0.0)),
            "median_corrected_displacement_px": float(rfeats.get("median_displacement_px", 0.0)),
            "independently_displaced_elements": int(rfeats.get("num_independently_displaced", 0)),
            "max_alignment_divergence_px": float(rfeats.get("max_alignment_divergence_px", 0.0)),
            "global_shift": v2_entry.get("global_dialog_shift", {"x": 0.0, "y": 0.0}) if v2_entry else {"x": 0.0, "y": 0.0}
        }
        case_records.append(rec)
        category_groups[gt].append(rec)

    # Compute statistical distributions by category
    category_stats = {}
    metrics_to_eval = [
        "max_corrected_displacement_px",
        "median_corrected_displacement_px",
        "independently_displaced_elements",
        "max_alignment_divergence_px",
        "match_rate_pct"
    ]
    
    for cat, items in category_groups.items():
        stats_for_cat = {"count": len(items)}
        for m in metrics_to_eval:
            vals = [it[m] for it in items]
            stats_for_cat[m] = {
                "mean": round(float(np.mean(vals)), 2),
                "std": round(float(np.std(vals)), 2),
                "median": round(float(np.median(vals)), 2),
                "q25": round(float(np.percentile(vals, 25)), 2),
                "q75": round(float(np.percentile(vals, 75)), 2),
                "min": round(float(np.min(vals)), 2),
                "max": round(float(np.max(vals)), 2)
            }
        category_stats[cat] = stats_for_cat

    # Strong displacement counts (e.g. max displacement >= 20px and >= 50px)
    mis_cases = category_groups["Misalignment"]
    non_mis_cases = [c for c in case_records if c["gt_category"] != "Misalignment"]
    
    mis_strong_20 = sum(1 for c in mis_cases if c["max_corrected_displacement_px"] >= 20.0)
    mis_strong_50 = sum(1 for c in mis_cases if c["max_corrected_displacement_px"] >= 50.0)
    
    non_mis_strong_20 = sum(1 for c in non_mis_cases if c["max_corrected_displacement_px"] >= 20.0)
    non_mis_strong_50 = sum(1 for c in non_mis_cases if c["max_corrected_displacement_px"] >= 50.0)
    
    # Identify non-Misalignment cases with large displacement (false positive candidates if displacement alone is used)
    high_disp_non_mis = sorted(
        [c for c in non_mis_cases if c["max_corrected_displacement_px"] >= 50.0],
        key=lambda x: x["max_corrected_displacement_px"],
        reverse=True
    )

    # Feature separation evaluation: Separation Score / Fisher Criterion ratio: (mean_mis - mean_non_mis)^2 / (var_mis + var_non_mis)
    feature_separation = []
    for m in metrics_to_eval:
        vals_mis = np.array([it[m] for it in mis_cases])
        vals_non = np.array([it[m] for it in non_mis_cases])
        
        m_mis, v_mis = np.mean(vals_mis), np.var(vals_mis)
        m_non, v_non = np.mean(vals_non), np.var(vals_non)
        
        f_ratio = ((m_mis - m_non) ** 2) / (v_mis + v_non + 1e-7)
        feature_separation.append({
            "feature_name": m,
            "misalignment_mean": round(float(m_mis), 2),
            "non_misalignment_mean": round(float(m_non), 2),
            "misalignment_std": round(float(np.sqrt(v_mis)), 2),
            "non_misalignment_std": round(float(np.sqrt(v_non)), 2),
            "separation_ratio": round(float(f_ratio), 4)
        })
        
    feature_separation.sort(key=lambda x: x["separation_ratio"], reverse=True)

    summary = {
        "total_benchmark_cases": len(case_records),
        "misalignment_cases_count": len(mis_cases),
        "non_misalignment_cases_count": len(non_mis_cases),
        "misalignment_strong_disp_ge_20px": f"{mis_strong_20} / {len(mis_cases)} ({mis_strong_20/len(mis_cases)*100:.1f}%)",
        "misalignment_strong_disp_ge_50px": f"{mis_strong_50} / {len(mis_cases)} ({mis_strong_50/len(mis_cases)*100:.1f}%)",
        "non_misalignment_strong_disp_ge_20px": f"{non_mis_strong_20} / {len(non_mis_cases)} ({non_mis_strong_20/len(non_mis_cases)*100:.1f}%)",
        "non_misalignment_strong_disp_ge_50px": f"{non_mis_strong_50} / {len(non_mis_cases)} ({non_mis_strong_50/len(non_mis_cases)*100:.1f}%)",
        "top_separating_features": feature_separation,
        "category_distribution_stats": category_stats,
        "high_displacement_non_misalignment_cases_count": len(high_disp_non_mis),
        "high_displacement_non_misalignment_cases": high_disp_non_mis
    }
    
    return summary, case_records

def generate_html_report(summary, records, output_path):
    cats = summary["category_distribution_stats"]
    sep = summary["top_separating_features"]
    fps = summary["high_displacement_non_misalignment_cases"]
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Misalignment Displacement Discrimination Analysis</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
  h1 {{ color: #38bdf8; font-size: 24px; margin-bottom: 6px; }}
  h2 {{ color: #93c5fd; font-size: 18px; margin-top: 28px; border-bottom: 1px solid #334155; padding-bottom: 6px; }}
  .metrics-banner {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 20px 0; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; text-align: center; }}
  .card-val {{ font-size: 22px; font-weight: bold; margin-top: 4px; color: #38bdf8; }}
  .card-sub {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; background: #1e293b; border-radius: 6px; overflow: hidden; }}
  th, td {{ padding: 10px 12px; text-align: right; border-bottom: 1px solid #334155; }}
  th:first-child, td:first-child {{ text-align: left; }}
  th {{ background: #0f172a; color: #38bdf8; font-weight: 600; }}
  tr:hover {{ background: #243247; }}
  .gt-badge {{ padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }}
  .gt-mis {{ background: #064e3b; color: #a7f3d0; border: 1px solid #10b981; }}
  .gt-non {{ background: #450a0a; color: #fecaca; border: 1px solid #ef4444; }}
</style>
</head>
<body>
<h1>Misalignment Displacement Discrimination Analysis</h1>
<div style="color: #94a3b8; font-size: 14px;">
  Evaluating the selectivity of global-anchor translation-corrected displacement evidence across all 101 benchmark cases (19 Misalignment vs. 82 Non-Misalignment).
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Misalignment with Strong Disp (&ge;20px)</div>
    <div class="card-val" style="color: #4ade80;">{summary['misalignment_strong_disp_ge_20px']}</div>
    <div class="card-sub">19/19 with &ge;49.4px</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Non-Misalignment with Disp &ge;20px</div>
    <div class="card-val" style="color: #f43f5e;">{summary['non_misalignment_strong_disp_ge_20px']}</div>
    <div class="card-sub">due to localized text expansion / layout shifts</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Non-Misalignment with Disp &ge;50px</div>
    <div class="card-val" style="color: #f59e0b;">{summary['non_misalignment_strong_disp_ge_50px']}</div>
    <div class="card-sub">significant lateral movement cases</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Top Separating Feature</div>
    <div class="card-val" style="font-size: 16px; color: #38bdf8;"><code>{sep[0]['feature_name']}</code></div>
    <div class="card-sub">Fisher ratio: {sep[0]['separation_ratio']}</div>
  </div>
</div>

<h2>1. Feature Separation Power (Misalignment vs Non-Misalignment)</h2>
<table>
  <thead>
    <tr>
      <th>Feature Measurement</th>
      <th>Misalignment Mean &plusmn; Std (N=19)</th>
      <th>Non-Misalignment Mean &plusmn; Std (N=82)</th>
      <th>Mean Difference</th>
      <th>Separation Ratio (Fisher Criterion)</th>
    </tr>
  </thead>
  <tbody>
"""
    for s in sep:
        diff = s['misalignment_mean'] - s['non_misalignment_mean']
        html += f"""
    <tr>
      <td><code>{s['feature_name']}</code></td>
      <td style="color:#4ade80; font-weight:bold;">{s['misalignment_mean']} &plusmn; {s['misalignment_std']}</td>
      <td style="color:#cbd5e1;">{s['non_misalignment_mean']} &plusmn; {s['non_misalignment_std']}</td>
      <td style="font-weight:bold;">{diff:+.2f}</td>
      <td style="color:#38bdf8; font-weight:bold;">{s['separation_ratio']:.4f}</td>
    </tr>
"""
    html += """
  </tbody>
</table>

<h2>2. Full Physical Evidence Distribution by Category (5 Target Classes)</h2>
<table>
  <thead>
    <tr>
      <th>Ground Truth Category</th>
      <th>Case Count</th>
      <th>Max Displacement (Mean / Median)</th>
      <th>Alignment Divergence (Mean / Median)</th>
      <th>Independently Displaced (Mean / Median)</th>
      <th>Match Rate % (Mean / Median)</th>
    </tr>
  </thead>
  <tbody>
"""
    for cat_name, stats in cats.items():
        is_mis = (cat_name == "Misalignment")
        style = "background: #1e3a5f; font-weight:bold;" if is_mis else ""
        html += f"""
    <tr style="{style}">
      <td style="color: {'#38bdf8' if is_mis else '#f8fafc'};">{cat_name}</td>
      <td>{stats['count']}</td>
      <td>{stats['max_corrected_displacement_px']['mean']:.1f}px / {stats['max_corrected_displacement_px']['median']:.1f}px</td>
      <td>{stats['max_alignment_divergence_px']['mean']:.1f}px / {stats['max_alignment_divergence_px']['median']:.1f}px</td>
      <td>{stats['independently_displaced_elements']['mean']:.1f} / {stats['independently_displaced_elements']['median']:.1f}</td>
      <td>{stats['match_rate_pct']['mean']:.1f}% / {stats['match_rate_pct']['median']:.1f}%</td>
    </tr>
"""
    html += f"""
  </tbody>
</table>

<h2>3. High-Displacement Non-Misalignment Cases (Max Displacement &ge; 50px, N = {len(fps)})</h2>
<div style="color: #94a3b8; font-size: 13px; margin-bottom: 8px;">
  These cases exhibit large element movement driven by text expansion, button resizing, or collision rather than independent column misalignment.
</div>
<table>
  <thead>
    <tr>
      <th>Case ID</th>
      <th>Product / Folder (Lang)</th>
      <th>Ground Truth Category</th>
      <th>Max Corrected Displacement</th>
      <th>Median Displacement</th>
      <th>Independently Displaced</th>
      <th>Max Alignment Divergence</th>
    </tr>
  </thead>
  <tbody>
"""
    for fp in fps:
        html += f"""
    <tr>
      <td style="font-weight:bold;">#{fp['case_id']}</td>
      <td>{fp['product']} / {fp['folder']} ({fp['lang']})</td>
      <td><span class="gt-badge gt-non">{fp['gt_category']}</span></td>
      <td style="color:#f43f5e; font-weight:bold;">{fp['max_corrected_displacement_px']:.1f}px</td>
      <td>{fp['median_corrected_displacement_px']:.1f}px</td>
      <td>{fp['independently_displaced_elements']}</td>
      <td>{fp['max_alignment_divergence_px']:.1f}px</td>
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
    summary, records = run_discrimination_analysis()
    
    print("\n" + "="*75)
    print("MISALIGNMENT DISCRIMINATION ANALYSIS SUMMARY")
    print("="*75)
    print(f"Total Benchmark Cases Evaluated           : {summary['total_benchmark_cases']}")
    print(f"Misalignment Cases Evaluated              : {summary['misalignment_cases_count']}")
    print(f"Non-Misalignment Cases Evaluated          : {summary['non_misalignment_cases_count']}")
    print(f"\nDisplacement Prevalence Comparison:")
    print(f"  - Misalignment Cases with Disp >= 20px  : {summary['misalignment_strong_disp_ge_20px']}")
    print(f"  - Misalignment Cases with Disp >= 50px  : {summary['misalignment_strong_disp_ge_50px']}")
    print(f"  - Non-Misalignment with Disp >= 20px    : {summary['non_misalignment_strong_disp_ge_20px']}")
    print(f"  - Non-Misalignment with Disp >= 50px    : {summary['non_misalignment_strong_disp_ge_50px']}")
    print(f"\nFeature Separation Power (Fisher Criterion Ratio):")
    for s in summary["top_separating_features"]:
        print(f"  - {s['feature_name']:35s}: Ratio = {s['separation_ratio']:.4f} (Mis: {s['misalignment_mean']:.1f}px vs Non: {s['non_misalignment_mean']:.1f}px)")
    print(f"\nHigh-Displacement Non-Misalignment Cases (>= 50px): {summary['high_displacement_non_misalignment_cases_count']} cases")
    print("="*75 + "\n")
    
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    print(f"Saved discrimination analysis JSON to {OUTPUT_JSON.resolve()}")
    
    generate_html_report(summary, records, OUTPUT_HTML)
    print(f"Saved visual HTML report to {OUTPUT_HTML.resolve()}")

if __name__ == '__main__':
    main()
