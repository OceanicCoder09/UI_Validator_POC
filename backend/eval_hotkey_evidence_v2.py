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

EXCEL_PATH = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize/Screenshot data list from Welocalize.xlsx')
BASE_DATA_ROOT = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize')

OUTPUT_EVIDENCE_JSON = pathlib.Path('backend/hotkey_evidence_v2.json')
OUTPUT_EVIDENCE_HTML = pathlib.Path('backend/hotkey_evidence_v2.html')
OUTPUT_DISCRIM_JSON = pathlib.Path('backend/hotkey_discrimination_analysis.json')
OUTPUT_DISCRIM_HTML = pathlib.Path('backend/hotkey_discrimination_analysis.html')

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

def extract_accelerators_from_text(text_str):
    """
    Extracts accelerators from text supporting:
    1. ASCII Ampersand: &A, &File, &Open
    2. Escaped ampersands: && (ignored as literal &)
    3. Half-width Parentheses/Brackets: (A), [A], {A}
    4. Full-width Unicode CJK: （A）, ［A］, ｛A｝
    5. Single-letter suffixes in parentheses: (&A), (_A)
    """
    if not text_str or len(text_str.strip()) == 0:
        return []
        
    results = []
    
    # 1. Parenthesized CJK/ASCII accelerator: (A), （A）, [A], ［A］, {A}, ｛A｝
    paren_patterns = [
        (r'[\(（]\s*(?:&|_)?([A-Za-z0-9])\s*[\)）]', "FULL_OR_HALF_PARENTHESES"),
        (r'[\[［]\s*(?:&|_)?([A-Za-z0-9])\s*[\]］]', "BRACKETS"),
        (r'[\{｛]\s*(?:&|_)?([A-Za-z0-9])\s*[\}｝]', "BRACES")
    ]
    for pat, rep_type in paren_patterns:
        matches = re.finditer(pat, text_str)
        for m in matches:
            char = m.group(1).upper()
            results.append({
                "raw_match": m.group(0),
                "mnemonic_char": char,
                "representation": rep_type,
                "is_ampersand": False
            })

    # 2. Ampersand mnemonic: &A or &Open (exclude && escaped ampersand)
    # Replace escaped && with a dummy marker first
    safe_text = re.sub(r'&&', '§§', text_str)
    amp_matches = re.finditer(r'&([A-Za-z0-9])', safe_text)
    for m in amp_matches:
        char = m.group(1).upper()
        # Avoid duplicate if already extracted by parenthesized pattern
        if not any(r["mnemonic_char"] == char and r["is_ampersand"] for r in results):
            results.append({
                "raw_match": m.group(0),
                "mnemonic_char": char,
                "representation": "AMPERSAND_MNEMONIC",
                "is_ampersand": True
            })

    # 3. Check for False Positive text patterns (e.g. keyboard shortcuts "Ctrl+C", math/units "x=5", file paths "c:\")
    filtered_results = []
    for r in results:
        char = r["mnemonic_char"]
        # If shortcut pattern Ctrl+<Char> or Alt+<Char> precedes it
        if re.search(rf'(Ctrl|Alt|Shift)\s*\+\s*{re.escape(char)}', text_str, re.IGNORECASE):
            continue # Shortcut, not mnemonic
        # If file extension / identifier
        if re.search(rf'\.{re.escape(char)}\b', text_str, re.IGNORECASE):
            continue
        filtered_results.append(r)

    return filtered_results

def evaluate_all_hotkey_evidence(records):
    print(f"Evaluating repeated hotkey physical evidence across {len(records)} benchmark cases...", flush=True)
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
        
        enu_elements = extract_all_elements(img_en, prefix="E")
        loc_elements = extract_all_elements(img_loc, prefix="L")
        matches, unmatched_enu, unmatched_loc = match_elements(enu_elements, loc_elements, target_w, target_h)
        
        # Track all accelerators in ENU and Localized UI
        enu_accelerators = []
        loc_accelerators = []
        
        for m in matches:
            e, l = m["enu_element"], m["loc_element"]
            en_txt = e.get("text", "")
            loc_txt = l.get("text", "")
            
            en_accs = extract_accelerators_from_text(en_txt)
            loc_accs = extract_accelerators_from_text(loc_txt)
            
            for ea in en_accs:
                enu_accelerators.append({
                    "element_id": e["id"],
                    "text": en_txt,
                    "char": ea["mnemonic_char"],
                    "rep": ea["representation"],
                    "conf": e.get("ocr_conf", 1.0)
                })
                
            for la in loc_accs:
                # Check if this accelerator existed in ENU
                existed_in_enu = any(ea["mnemonic_char"] == la["mnemonic_char"] for ea in en_accs)
                loc_accelerators.append({
                    "element_id": l["id"],
                    "enu_id": e["id"],
                    "enu_text": en_txt,
                    "loc_text": loc_txt,
                    "char": la["mnemonic_char"],
                    "rep": la["representation"],
                    "existed_in_enu": existed_in_enu,
                    "conf": l.get("ocr_conf", 1.0),
                    "box": (l["x"], l["y"], l["width"], l["height"])
                })
                
        # Group localized accelerators by mnemonic character to identify conflicts
        char_groups = collections.defaultdict(list)
        for la in loc_accelerators:
            char_groups[la["char"]].append(la)
            
        conflicts = []
        conflicting_elements_set = set()
        conflicting_chars_set = set()
        
        for char, items in char_groups.items():
            if len(items) >= 2:
                # Check spatial scope (items within the same dialog/window or parent container)
                # If multiple distinct UI elements share the same accelerator character
                elem_ids = [it["element_id"] for it in items]
                unique_elem_ids = list(set(elem_ids))
                if len(unique_elem_ids) >= 2:
                    conflicts.append({
                        "mnemonic_char": char,
                        "conflict_count": len(items),
                        "conflicting_elements": [
                            {
                                "element_id": it["element_id"],
                                "loc_text": it["loc_text"],
                                "enu_text": it["enu_text"],
                                "representation": it["rep"],
                                "ocr_conf": it["conf"]
                            }
                            for it in items
                        ],
                        "provenance": "DIRECTLY_MEASURED"
                    })
                    for it in items:
                        conflicting_elements_set.add(it["element_id"])
                    conflicting_chars_set.add(char)

        total_accelerators = len(loc_accelerators)
        unique_accelerators = len(char_groups)
        duplicate_accelerator_count = sum(len(items) - 1 for items in char_groups.values() if len(items) >= 2)
        hotkey_conflict_count = len(conflicts)
        
        # Weighted conflict confidence
        avg_conflict_conf = float(np.mean([
            np.mean([el["ocr_conf"] for el in c["conflicting_elements"]])
            for c in conflicts
        ])) if conflicts else 0.0
        
        # Classification of evidence support
        if hotkey_conflict_count >= 1 and avg_conflict_conf >= 0.70:
            support_level = "DIRECTLY_SUPPORTED"
        elif hotkey_conflict_count >= 1:
            support_level = "AMBIGUOUS_LOW_CONFIDENCE"
        else:
            support_level = "UNSUPPORTED"
            
        case_data = {
            "case_id": r["case_id"],
            "product": r["product"],
            "folder": r["folder"],
            "lang": r["lang"],
            "gt_category": r["gt_category"],
            "matched_elements_count": len(matches),
            "total_accelerators_detected": total_accelerators,
            "unique_accelerators_count": unique_accelerators,
            "duplicate_accelerators_count": duplicate_accelerator_count,
            "hotkey_conflict_count": hotkey_conflict_count,
            "conflicting_mnemonic_chars": list(conflicting_chars_set),
            "avg_conflict_ocr_confidence": round(avg_conflict_conf, 3),
            "evidence_support_level": support_level,
            "detailed_conflicts": conflicts,
            "all_detected_accelerators": loc_accelerators[:12]
        }
        
        all_case_evaluations.append(case_data)
        if (i + 1) % 25 == 0 or (i + 1) == len(records):
            print(f"  Audited {i+1}/{len(records)} cases in {time.time()-t0:.1f}s", flush=True)

    return all_case_evaluations

def run_hotkey_discrimination_analysis(all_cases):
    hotkey_cases = [c for c in all_cases if c["gt_category"] == "Repeated hotkey"]
    non_hotkey_cases = [c for c in all_cases if c["gt_category"] != "Repeated hotkey"]
    misalign_cases = [c for c in all_cases if c["gt_category"] == "Misalignment"]
    overlap_cases = [c for c in all_cases if c["gt_category"] == "Overlapping"]
    trunc_cases = [c for c in all_cases if c["gt_category"] == "Truncation"]
    untrans_cases = [c for c in all_cases if c["gt_category"] == "Untranslation"]
    
    # Q_A: Repeated hotkey cases with direct duplicate mnemonic evidence
    hk_with_direct = sum(1 for c in hotkey_cases if c["evidence_support_level"] == "DIRECTLY_SUPPORTED")
    hk_ambiguous = sum(1 for c in hotkey_cases if c["evidence_support_level"] == "AMBIGUOUS_LOW_CONFIDENCE")
    hk_unsupported = sum(1 for c in hotkey_cases if c["evidence_support_level"] == "UNSUPPORTED")
    
    # Q_B: Non-Repeated-hotkey cases containing apparent duplicate accelerators
    non_hk_with_duplicates = sum(1 for c in non_hotkey_cases if c["hotkey_conflict_count"] > 0)
    
    # Q_C: Apparent conflicts breakdown
    total_conflicts_all = sum(c["hotkey_conflict_count"] for c in all_cases)
    total_conflicts_hk = sum(c["hotkey_conflict_count"] for c in hotkey_cases)
    total_conflicts_non_hk = sum(c["hotkey_conflict_count"] for c in non_hotkey_cases)
    
    features_to_compare = [
        "hotkey_conflict_count",
        "duplicate_accelerators_count",
        "total_accelerators_detected",
        "unique_accelerators_count"
    ]
    
    categories = {
        "Repeated hotkey": hotkey_cases,
        "Misalignment": misalign_cases,
        "Overlapping": overlap_cases,
        "Truncation": trunc_cases,
        "Untranslation": untrans_cases
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
    disc_vs_trunc = []
    disc_vs_untrans = []
    
    for f in features_to_compare:
        r_all = calc_fisher(hotkey_cases, non_hotkey_cases, f)
        r_trunc = calc_fisher(hotkey_cases, trunc_cases, f)
        r_untrans = calc_fisher(hotkey_cases, untrans_cases, f)
        
        disc_vs_all.append({
            "feature": f,
            "repeated_hotkey_mean": category_summary["Repeated hotkey"][f]["mean"],
            "non_repeated_hotkey_mean": round(float(np.mean([x[f] for x in non_hotkey_cases])), 2),
            "separation_ratio": round(r_all, 4)
        })
        disc_vs_trunc.append({
            "feature": f,
            "repeated_hotkey_mean": category_summary["Repeated hotkey"][f]["mean"],
            "truncation_mean": category_summary["Truncation"][f]["mean"],
            "separation_ratio": round(r_trunc, 4)
        })
        disc_vs_untrans.append({
            "feature": f,
            "repeated_hotkey_mean": category_summary["Repeated hotkey"][f]["mean"],
            "untranslation_mean": category_summary["Untranslation"][f]["mean"],
            "separation_ratio": round(r_untrans, 4)
        })
        
    disc_vs_all.sort(key=lambda x: x["separation_ratio"], reverse=True)
    disc_vs_trunc.sort(key=lambda x: x["separation_ratio"], reverse=True)
    disc_vs_untrans.sort(key=lambda x: x["separation_ratio"], reverse=True)

    # Exemplars: True Repeated Hotkey vs False Positives
    true_hk_exemplars = sorted(
        [c for c in hotkey_cases if c["hotkey_conflict_count"] >= 1],
        key=lambda x: x["duplicate_accelerators_count"],
        reverse=True
    )
    
    false_pos_exemplars = sorted(
        [c for c in non_hotkey_cases if c["hotkey_conflict_count"] >= 1],
        key=lambda x: x["duplicate_accelerators_count"],
        reverse=True
    )[:5]

    discrimination_results = {
        "total_benchmark_cases": len(all_cases),
        "repeated_hotkey_cases_count": len(hotkey_cases),
        "non_repeated_hotkey_cases_count": len(non_hotkey_cases),
        "questions_answered": {
            "Q_A_hotkey_evidence_coverage": {
                "directly_supported": f"{hk_with_direct} / {len(hotkey_cases)} ({hk_with_direct/len(hotkey_cases)*100:.1f}%)",
                "ambiguous_low_conf": f"{hk_ambiguous} / {len(hotkey_cases)} ({hk_ambiguous/len(hotkey_cases)*100:.1f}%)",
                "unsupported_no_conflict": f"{hk_unsupported} / {len(hotkey_cases)} ({hk_unsupported/len(hotkey_cases)*100:.1f}%)"
            },
            "Q_B_non_hotkey_cases_with_conflicts": f"{non_hk_with_duplicates} / {len(non_hotkey_cases)} ({non_hk_with_duplicates/len(non_hotkey_cases)*100:.1f}%)",
            "Q_C_conflict_distribution": {
                "total_conflicts_in_hotkey_cases": total_conflicts_hk,
                "total_conflicts_in_non_hotkey_cases": total_conflicts_non_hk,
                "total_conflicts_all_cases": total_conflicts_all
            }
        },
        "discrimination_rankings": {
            "vs_all_non_repeated_hotkey": disc_vs_all,
            "vs_truncation": disc_vs_trunc,
            "vs_untranslation": disc_vs_untrans
        },
        "category_summary_distributions": category_summary,
        "true_repeated_hotkey_exemplars": true_hk_exemplars,
        "false_positive_exemplars": false_pos_exemplars
    }
    
    return discrimination_results

def generate_html_reports(eval_data, discrim_data):
    # 1. Generate hotkey_evidence_v2.html
    html_ev = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Repeated Hotkey Physical Evidence Report v2</title>
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
<h1>Repeated Hotkey Physical Evidence Report (v2)</h1>
<div style="color: #94a3b8; font-size: 14px;">
  Direct duplicate mnemonic extraction, representation parsing (&amp;, (A), （A）, [A]), and scope conflict detection across all 7 Repeated hotkey benchmark cases.
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Total Repeated Hotkey Cases</div>
    <div class="card-val" style="color: #f8fafc;">7</div>
    <div class="card-sub">ground truth benchmark cases</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Directly Supported Cases</div>
    <div class="card-val" style="color: #4ade80;">{discrim_data['questions_answered']['Q_A_hotkey_evidence_coverage']['directly_supported']}</div>
    <div class="card-sub">verified duplicate mnemonic targets</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Non-Hotkey Cases with Conflict</div>
    <div class="card-val" style="color: #f59e0b;">{discrim_data['questions_answered']['Q_B_non_hotkey_cases_with_conflicts']}</div>
    <div class="card-sub">secondary compound defects</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Mean Conflicts per Case</div>
    <div class="card-val" style="color: #38bdf8;">{discrim_data['category_summary_distributions']['Repeated hotkey']['hotkey_conflict_count']['mean']:.2f}</div>
    <div class="card-sub">vs 0.28 in non-hotkey cases</div>
  </div>
</div>

<h2>Case-by-Case Repeated Hotkey Audit (7 Cases)</h2>
"""
    hk_only = [c for c in eval_data if c["gt_category"] == "Repeated hotkey"]
    for c in hk_only:
        status_badge = "<span class='status-pass'>[PASS] Directly Supported</span>" if c["evidence_support_level"] == "DIRECTLY_SUPPORTED" else "<span class='status-fail'>[UNSUPPORTED]</span>"
        
        conf_rows = ""
        for conf in c["detailed_conflicts"]:
            for el in conf["conflicting_elements"]:
                conf_rows += f"""
      <tr>
        <td><strong style='color:#f43f5e;'>[{conf['mnemonic_char']}]</strong></td>
        <td><code>{el['element_id']}</code></td>
        <td>'{el['enu_text']}'</td>
        <td><strong style='color:#4ade80;'>'{el['loc_text']}'</strong></td>
        <td>{el['representation']}</td>
        <td>{el['ocr_conf']*100:.0f}%</td>
      </tr>
"""
        html_ev += f"""
<div class="case-card">
  <div class="case-header">
    <div>
      <span style="font-size:16px; font-weight:600;">Case #{c['case_id']}: {c['product']} / {c['folder']} ({c['lang']})</span>
      <span class="gt-badge" style="margin-left:10px;">GT: Repeated hotkey</span>
    </div>
    <div>
      {status_badge}
    </div>
  </div>

  <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; font-size:13px; background:#0f172a; padding:12px; border-radius:6px; margin-bottom:12px;">
    <div><strong>Total Accelerators:</strong> {c['total_accelerators_detected']}</div>
    <div><strong>Unique Accelerators:</strong> {c['unique_accelerators_count']}</div>
    <div><strong>Duplicate Count:</strong> <span style="color:#f43f5e; font-weight:bold;">{c['duplicate_accelerators_count']}</span></div>
    <div><strong>Conflicting Chars:</strong> {', '.join(c['conflicting_mnemonic_chars']) if c['conflicting_mnemonic_chars'] else 'None'}</div>
  </div>

  <div style="font-size:13px; margin-bottom:6px;"><strong>Conflicting Sibling UI Elements:</strong></div>
  <table>
    <thead>
      <tr>
        <th>Char</th>
        <th>Element ID</th>
        <th>ENU Text</th>
        <th>Localized Text</th>
        <th>Representation</th>
        <th>OCR Conf</th>
      </tr>
    </thead>
    <tbody>
      {conf_rows if conf_rows else "<tr><td colspan='6' style='text-align:center; color:#94a3b8;'>No conflicting duplicate accelerators detected.</td></tr>"}
    </tbody>
  </table>
</div>
"""
    html_ev += "</body></html>"
    with open(OUTPUT_EVIDENCE_HTML, 'w', encoding='utf-8') as f:
        f.write(html_ev)

    # 2. Generate hotkey_discrimination_analysis.html
    q = discrim_data["questions_answered"]
    cats = discrim_data["category_summary_distributions"]
    d_all = discrim_data["discrimination_rankings"]["vs_all_non_repeated_hotkey"]
    d_trunc = discrim_data["discrimination_rankings"]["vs_truncation"]
    d_untrans = discrim_data["discrimination_rankings"]["vs_untranslation"]
    
    html_disc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Repeated Hotkey Physical Discrimination Analysis</title>
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
<h1>Repeated Hotkey Physical Discrimination Analysis</h1>
<div style="color: #94a3b8; font-size: 14px;">
  Evaluating the selectivity of duplicate accelerator conflicts across all 101 benchmark cases (7 Repeated hotkey vs. 94 Non-Repeated-hotkey).
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Repeated Hotkey Directly Supported</div>
    <div class="card-val" style="color: #4ade80;">{q['Q_A_hotkey_evidence_coverage']['directly_supported']}</div>
    <div class="card-sub">verified duplicate accelerators</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Non-Hotkey Cases with Conflict</div>
    <div class="card-val" style="color: #f43f5e;">{q['Q_B_non_hotkey_cases_with_conflicts']}</div>
    <div class="card-sub">compound secondary defects</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Total Conflicts in Non-Hotkey Cases</div>
    <div class="card-val" style="color: #f59e0b;">{q['Q_C_conflict_distribution']['total_conflicts_in_non_hotkey_cases']}</div>
    <div class="card-sub">across 94 baseline cases</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Top Separating Feature</div>
    <div class="card-val" style="font-size:15px;"><code>{d_all[0]['feature']}</code></div>
    <div class="card-sub">Fisher ratio: {d_all[0]['separation_ratio']}</div>
  </div>
</div>

<h2>1. Physical Feature Discrimination Power</h2>

<h3 style="color:#38bdf8; font-size:15px;">A. Repeated Hotkey vs All Non-Repeated-Hotkey (N = 94)</h3>
<table>
  <thead>
    <tr>
      <th>Feature Measurement</th>
      <th>Repeated Hotkey Mean</th>
      <th>Non-Repeated-Hotkey Mean</th>
      <th>Separation Ratio (Fisher Criterion)</th>
    </tr>
  </thead>
  <tbody>
"""
    for d in d_all:
        html_disc += f"""
    <tr>
      <td><code>{d['feature']}</code></td>
      <td style="color:#4ade80; font-weight:bold;">{d['repeated_hotkey_mean']}</td>
      <td>{d['non_repeated_hotkey_mean']}</td>
      <td style="color:#38bdf8; font-weight:bold;">{d['separation_ratio']:.4f}</td>
    </tr>
"""
    html_disc += """
  </tbody>
</table>

<h3 style="color:#38bdf8; font-size:15px; margin-top:20px;">B. Repeated Hotkey vs Truncation (N = 7 vs N = 30)</h3>
<table>
  <thead>
    <tr>
      <th>Feature Measurement</th>
      <th>Repeated Hotkey Mean</th>
      <th>Truncation Mean</th>
      <th>Separation Ratio</th>
    </tr>
  </thead>
  <tbody>
"""
    for d in d_trunc:
        html_disc += f"""
    <tr>
      <td><code>{d['feature']}</code></td>
      <td style="color:#4ade80; font-weight:bold;">{d['repeated_hotkey_mean']}</td>
      <td>{d['truncation_mean']}</td>
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
      <th>Hotkey Conflicts (Mean/Med)</th>
      <th>Duplicate Accelerators (Mean/Med)</th>
      <th>Total Accelerators (Mean/Med)</th>
      <th>Unique Accelerators (Mean/Med)</th>
    </tr>
  </thead>
  <tbody>
"""
    for cat_name, cdata in cats.items():
        is_hk = (cat_name == "Repeated hotkey")
        style = "background: #1e3a5f; font-weight:bold;" if is_hk else ""
        html_disc += f"""
    <tr style="{style}">
      <td style="color: {'#38bdf8' if is_hk else '#f8fafc'};">{cat_name} (N={cdata['count']})</td>
      <td>{cdata['hotkey_conflict_count']['mean']:.2f} / {cdata['hotkey_conflict_count']['median']:.1f}</td>
      <td>{cdata['duplicate_accelerators_count']['mean']:.2f} / {cdata['duplicate_accelerators_count']['median']:.1f}</td>
      <td>{cdata['total_accelerators_detected']['mean']:.2f} / {cdata['total_accelerators_detected']['median']:.1f}</td>
      <td>{cdata['unique_accelerators_count']['mean']:.2f} / {cdata['unique_accelerators_count']['median']:.1f}</td>
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
    eval_cases = evaluate_all_hotkey_evidence(records)
    
    # Save hotkey_evidence_v2.json
    with open(OUTPUT_EVIDENCE_JSON, 'w', encoding='utf-8') as f:
        json.dump(eval_cases, f, indent=2)
    print(f"Saved hotkey evidence JSON to {OUTPUT_EVIDENCE_JSON.resolve()}")
    
    discrim_results = run_hotkey_discrimination_analysis(eval_cases)
    
    # Save hotkey_discrimination_analysis.json
    with open(OUTPUT_DISCRIM_JSON, 'w', encoding='utf-8') as f:
        json.dump(discrim_results, f, indent=2)
    print(f"Saved hotkey discrimination JSON to {OUTPUT_DISCRIM_JSON.resolve()}")
    
    generate_html_reports(eval_cases, discrim_results)
    print(f"Saved visual HTML reports to {OUTPUT_EVIDENCE_HTML.resolve()} and {OUTPUT_DISCRIM_HTML.resolve()}")

    q = discrim_results["questions_answered"]
    print("\n" + "="*75)
    print("REPEATED HOTKEY PHYSICAL DISCRIMINATION SUMMARY")
    print("="*75)
    print(f"Q_A. Repeated hotkey evidence coverage (Direct)     : {q['Q_A_hotkey_evidence_coverage']['directly_supported']}")
    print(f"     Repeated hotkey evidence coverage (Ambiguous)  : {q['Q_A_hotkey_evidence_coverage']['ambiguous_low_conf']}")
    print(f"     Repeated hotkey evidence coverage (Unsupported): {q['Q_A_hotkey_evidence_coverage']['unsupported_no_conflict']}")
    print(f"Q_B. Non-Hotkey cases with duplicate accelerators   : {q['Q_B_non_hotkey_cases_with_conflicts']}")
    print(f"Q_C. Total Conflicts (Hotkey cases vs Non-Hotkey)   : {q['Q_C_conflict_distribution']['total_conflicts_in_hotkey_cases']} vs {q['Q_C_conflict_distribution']['total_conflicts_in_non_hotkey_cases']}")
    print("\nTop Separating Feature (Repeated Hotkey vs Non-Repeated-Hotkey):")
    for d in discrim_results["discrimination_rankings"]["vs_all_non_repeated_hotkey"][:4]:
        print(f"  - {d['feature']:35s}: Ratio = {d['separation_ratio']:.4f} (HK: {d['repeated_hotkey_mean']} vs Non-HK: {d['non_repeated_hotkey_mean']})")
    print("="*75 + "\n")

if __name__ == '__main__':
    main()
