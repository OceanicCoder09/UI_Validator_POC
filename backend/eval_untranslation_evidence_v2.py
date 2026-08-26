import os
import sys
import json
import time
import pathlib
import re
import string
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

OUTPUT_EVIDENCE_JSON = pathlib.Path('backend/untranslation_evidence_v2.json')
OUTPUT_EVIDENCE_HTML = pathlib.Path('backend/untranslation_evidence_v2.html')
OUTPUT_DISCRIM_JSON = pathlib.Path('backend/untranslation_discrimination_analysis.json')
OUTPUT_DISCRIM_HTML = pathlib.Path('backend/untranslation_discrimination_analysis.html')

TARGET_CLASSES = [
    "Misalignment",
    "Overlapping",
    "Repeated hotkey",
    "Truncation",
    "Untranslation"
]

# Known non-translatable terminology, brands, file extensions, units, and acronyms
BRAND_AND_TECHNICAL_LEXICON = {
    # Brands & Products
    "autodesk", "autocad", "civil 3d", "civil3d", "inventor", "vault", "revit", "navisworks", "dwg", "dxf", "dgn", "pdf", "xml", "json", "html", "http", "https", "url", "cad", "bim",
    # Common universal file/code extensions
    "exe", "dll", "zip", "txt", "csv", "xlsx", "docx", "ipt", "iam", "idw", "dwf", "nwd", "nwc", "sat", "step", "stp", "iges", "igs",
    # Universal keyboard shortcuts, units & technical terms
    "ok", "cancel", "id", "x", "y", "z", "rgb", "hsv", "cm", "mm", "m", "km", "in", "ft", "px", "deg", "rad", "sec", "min", "hr", "kb", "mb", "gb", "tb", "hz", "khz", "mhz", "ghz",
    "ctrl", "alt", "shift", "tab", "esc", "enter", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
    "sql", "api", "sdk", "gui", "ui", "os", "ip", "tcp", "udp", "cpu", "ram", "gpu", "utf-8", "ascii", "ansi"
}

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

def normalize_text_token(t):
    t_clean = re.sub(r'[\(\[\{（\)\}\]\.,;:!?"\'_&~#\-\/\\]+', '', t).strip().lower()
    return t_clean

def classify_text_category(text_str):
    """
    Classifies token semantics into UI wording vs technical/brand/unit/acronym.
    """
    cleaned = normalize_text_token(text_str)
    if not cleaned:
        return "PUNCTUATION_OR_EMPTY", False
        
    # Check if numeric or unit value
    if re.match(r'^\d+(\.\d+)?(\s*(mm|cm|m|in|ft|px|deg|rad|kb|mb|gb|%))?$', cleaned):
        return "NUMERIC_OR_UNIT", False
        
    # Check if brand/technical term
    if cleaned in BRAND_AND_TECHNICAL_LEXICON:
        return "BRAND_OR_TECHNICAL_TERM", False
        
    # Check if file extension / path / code identifier
    if re.match(r'^[a-z0-9_]+\.[a-z0-9]{2,4}$', cleaned) or re.match(r'^[A-Z0-9_]{2,8}$', text_str.strip()):
        if cleaned in BRAND_AND_TECHNICAL_LEXICON:
            return "BRAND_OR_TECHNICAL_TERM", False
        if len(cleaned) <= 3:
            return "ACRONYM_OR_SHORT_CODE", False
            
    # Check if single letter / mnemonic accelerator
    if len(cleaned) == 1:
        return "SINGLE_LETTER_OR_HOTKEY", False
        
    # Check if English dictionary/wording token (>= 3 chars)
    words = re.findall(r'[A-Za-z]{3,}', text_str)
    if words:
        # Check if words are user-facing English sentences/words
        non_brand_words = [w for w in words if normalize_text_token(w) not in BRAND_AND_TECHNICAL_LEXICON]
        if non_brand_words:
            return "ORDINARY_USER_FACING_UI_WORDING", True
            
    return "UNKNOWN_OR_OTHER", False

def evaluate_all_untranslation_evidence(records):
    print(f"Evaluating untranslation text evidence across {len(records)} benchmark cases...", flush=True)
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
        
        matched_text_elements = []
        genuine_untranslated_elements = []
        technical_brand_fp_elements = []
        
        total_english_chars_preserved = 0
        total_latin_words_preserved = 0
        
        for m in matches:
            e, l = m["enu_element"], m["loc_element"]
            if e["type"] != "text" or l["type"] != "text":
                continue
                
            en_txt = e.get("text", "").strip()
            loc_txt = l.get("text", "").strip()
            
            norm_en = normalize_text_token(en_txt)
            norm_loc = normalize_text_token(loc_txt)
            
            if not norm_en or not norm_loc:
                continue
                
            # Check English-character ratio in localized string
            latin_chars = len(re.findall(r'[A-Za-z]', loc_txt))
            total_chars = max(1, len(re.sub(r'\s+', '', loc_txt)))
            latin_char_ratio = round(latin_chars / float(total_chars), 3)
            
            # Exact or near-identical text preservation check
            is_identical = (norm_en == norm_loc)
            
            # Identify preserved English words
            en_words_list = re.findall(r'[A-Za-z]{3,}', loc_txt)
            preserved_words = [w for w in en_words_list if normalize_text_token(w) in norm_en]
            
            text_category, is_user_facing = classify_text_category(loc_txt)
            
            # Evidence evaluation:
            # Genuine untranslated string: identical/preserved English text that represents ordinary user-facing UI wording
            is_genuine_untranslated = False
            is_potential_fp = False
            
            if is_identical or len(preserved_words) >= 2 or (len(preserved_words) == 1 and len(preserved_words[0]) >= 5):
                if is_user_facing:
                    is_genuine_untranslated = True
                    total_english_chars_preserved += latin_chars
                    total_latin_words_preserved += len(preserved_words)
                else:
                    is_potential_fp = True
                    
            elem_record = {
                "element_id": l["id"],
                "enu_text": en_txt,
                "loc_text": loc_txt,
                "is_identical_normalized": is_identical,
                "preserved_english_words": preserved_words,
                "latin_char_ratio": latin_char_ratio,
                "ocr_confidence": l.get("ocr_conf"),
                "text_semantic_category": text_category,
                "is_user_facing_ui_wording": is_user_facing,
                "is_genuine_untranslated_evidence": is_genuine_untranslated,
                "is_potential_false_positive": is_potential_fp,
                "provenance": {
                    "enu_text": "DIRECTLY_MEASURED",
                    "loc_text": "DIRECTLY_MEASURED",
                    "semantic_classification": "DERIVED_FROM_MEASUREMENT",
                    "ocr_confidence": "DIRECTLY_MEASURED"
                }
            }
            
            matched_text_elements.append(elem_record)
            if is_genuine_untranslated:
                genuine_untranslated_elements.append(elem_record)
            if is_potential_fp:
                technical_brand_fp_elements.append(elem_record)

        genuine_count = len(genuine_untranslated_elements)
        fp_count = len(technical_brand_fp_elements)
        
        # Evidence Support Level
        # Directly supported: >= 1 genuine user-facing untranslated UI element
        # Ambiguous: 0 genuine but >= 1 technical/brand preservation
        # Unsupported: 0 preserved English elements
        if genuine_count >= 1:
            evidence_support_level = "DIRECTLY_SUPPORTED"
        elif fp_count >= 1:
            evidence_support_level = "AMBIGUOUS"
        else:
            evidence_support_level = "UNSUPPORTED"
            
        case_data = {
            "case_id": r["case_id"],
            "product": r["product"],
            "folder": r["folder"],
            "lang": r["lang"],
            "gt_category": r["gt_category"],
            "matched_elements_count": len(matches),
            "matched_text_elements_count": len(matched_text_elements),
            "genuine_untranslated_strings_count": genuine_count,
            "potential_fp_technical_brand_count": fp_count,
            "total_english_chars_preserved": total_english_chars_preserved,
            "total_latin_words_preserved": total_latin_words_preserved,
            "evidence_support_level": evidence_support_level,
            "genuine_untranslated_elements": genuine_untranslated_elements[:10],
            "technical_brand_fp_elements": technical_brand_fp_elements[:10]
        }
        
        all_case_evaluations.append(case_data)
        if (i + 1) % 25 == 0 or (i + 1) == len(records):
            print(f"  Audited {i+1}/{len(records)} cases in {time.time()-t0:.1f}s", flush=True)

    return all_case_evaluations

def run_untranslation_discrimination_analysis(all_cases):
    untrans_cases = [c for c in all_cases if c["gt_category"] == "Untranslation"]
    non_untrans_cases = [c for c in all_cases if c["gt_category"] != "Untranslation"]
    misalign_cases = [c for c in all_cases if c["gt_category"] == "Misalignment"]
    overlap_cases = [c for c in all_cases if c["gt_category"] == "Overlapping"]
    trunc_cases = [c for c in all_cases if c["gt_category"] == "Truncation"]
    hotkey_cases = [c for c in all_cases if c["gt_category"] == "Repeated hotkey"]
    
    # Q_A: Untranslation cases with direct user-facing English evidence
    untrans_with_direct_evidence = sum(1 for c in untrans_cases if c["evidence_support_level"] == "DIRECTLY_SUPPORTED")
    untrans_ambiguous = sum(1 for c in untrans_cases if c["evidence_support_level"] == "AMBIGUOUS")
    untrans_unsupported = sum(1 for c in untrans_cases if c["evidence_support_level"] == "UNSUPPORTED")
    
    # Q_B: Non-Untranslation cases containing preserved English text
    non_untrans_with_genuine = sum(1 for c in non_untrans_cases if c["genuine_untranslated_strings_count"] > 0)
    non_untrans_with_fp_only = sum(1 for c in non_untrans_cases if c["genuine_untranslated_strings_count"] == 0 and c["potential_fp_technical_brand_count"] > 0)
    
    # Q_C: Apparent matches that are technical terms/brands across all cases
    total_genuine_strings_all = sum(c["genuine_untranslated_strings_count"] for c in all_cases)
    total_tech_brand_strings_all = sum(c["potential_fp_technical_brand_count"] for c in all_cases)
    
    features_to_compare = [
        "genuine_untranslated_strings_count",
        "potential_fp_technical_brand_count",
        "total_english_chars_preserved",
        "total_latin_words_preserved"
    ]
    
    categories = {
        "Untranslation": untrans_cases,
        "Misalignment": misalign_cases,
        "Overlapping": overlap_cases,
        "Truncation": trunc_cases,
        "Repeated hotkey": hotkey_cases
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
    disc_vs_mis = []
    
    for f in features_to_compare:
        r_all = calc_fisher(untrans_cases, non_untrans_cases, f)
        r_trunc = calc_fisher(untrans_cases, trunc_cases, f)
        r_mis = calc_fisher(untrans_cases, misalign_cases, f)
        
        disc_vs_all.append({
            "feature": f,
            "untranslation_mean": category_summary["Untranslation"][f]["mean"],
            "non_untranslation_mean": round(float(np.mean([x[f] for x in non_untrans_cases])), 2),
            "separation_ratio": round(r_all, 4)
        })
        disc_vs_trunc.append({
            "feature": f,
            "untranslation_mean": category_summary["Untranslation"][f]["mean"],
            "truncation_mean": category_summary["Truncation"][f]["mean"],
            "separation_ratio": round(r_trunc, 4)
        })
        disc_vs_mis.append({
            "feature": f,
            "untranslation_mean": category_summary["Untranslation"][f]["mean"],
            "misalignment_mean": category_summary["Misalignment"][f]["mean"],
            "separation_ratio": round(r_mis, 4)
        })
        
    disc_vs_all.sort(key=lambda x: x["separation_ratio"], reverse=True)
    disc_vs_trunc.sort(key=lambda x: x["separation_ratio"], reverse=True)
    disc_vs_mis.sort(key=lambda x: x["separation_ratio"], reverse=True)

    # Exemplars: True Untranslation vs False Positives (Technical strings)
    true_untrans_exemplars = sorted(
        [c for c in untrans_cases if c["genuine_untranslated_strings_count"] >= 2],
        key=lambda x: x["total_english_chars_preserved"],
        reverse=True
    )[:5]
    
    false_pos_exemplars = sorted(
        [c for c in non_untrans_cases if c["potential_fp_technical_brand_count"] >= 2],
        key=lambda x: x["potential_fp_technical_brand_count"],
        reverse=True
    )[:5]

    discrimination_results = {
        "total_benchmark_cases": len(all_cases),
        "untranslation_cases_count": len(untrans_cases),
        "non_untranslation_cases_count": len(non_untrans_cases),
        "questions_answered": {
            "Q_A_untranslation_evidence_coverage": {
                "directly_supported": f"{untrans_with_direct_evidence} / {len(untrans_cases)} ({untrans_with_direct_evidence/len(untrans_cases)*100:.1f}%)",
                "ambiguous_technical_only": f"{untrans_ambiguous} / {len(untrans_cases)} ({untrans_ambiguous/len(untrans_cases)*100:.1f}%)",
                "unsupported_no_english": f"{untrans_unsupported} / {len(untrans_cases)} ({untrans_unsupported/len(untrans_cases)*100:.1f}%)"
            },
            "Q_B_non_untranslation_cases_with_preserved_english": {
                "with_genuine_user_facing_english": f"{non_untrans_with_genuine} / {len(non_untrans_cases)} ({non_untrans_with_genuine/len(non_untrans_cases)*100:.1f}%)",
                "with_technical_brand_only": f"{non_untrans_with_fp_only} / {len(non_untrans_cases)} ({non_untrans_with_fp_only/len(non_untrans_cases)*100:.1f}%)"
            },
            "Q_C_technical_brand_tokens_vs_genuine_ui_strings": {
                "total_genuine_untranslated_strings": total_genuine_strings_all,
                "total_technical_brand_tokens": total_tech_brand_strings_all,
                "technical_token_ratio_pct": f"{total_tech_brand_strings_all / max(1, total_genuine_strings_all + total_tech_brand_strings_all)*100:.1f}%"
            }
        },
        "discrimination_rankings": {
            "vs_all_non_untranslation": disc_vs_all,
            "vs_truncation": disc_vs_trunc,
            "vs_misalignment": disc_vs_mis
        },
        "category_summary_distributions": category_summary,
        "true_untranslation_exemplars": true_untrans_exemplars,
        "false_positive_exemplars": false_pos_exemplars
    }
    
    return discrimination_results

def generate_html_reports(eval_data, discrim_data):
    # 1. Generate untranslation_evidence_v2.html
    html_ev = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Untranslation Physical Evidence Report v2</title>
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
  .status-ambig {{ background: #78350f; border: 1px solid #f59e0b; color: #fef3c7; font-weight: 600; padding: 4px 10px; border-radius: 6px; font-size: 13px; }}
  .status-fail {{ background: #334155; color: #94a3b8; font-weight: 600; padding: 4px 10px; border-radius: 6px; font-size: 13px; }}
</style>
</head>
<body>
<h1>Untranslation Physical Evidence Report (v2)</h1>
<div style="color: #94a3b8; font-size: 14px;">
  Direct lexical preservation audit across all 26 Untranslation benchmark cases, differentiating user-facing UI text from universal technical terms.
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Total Untranslation Cases</div>
    <div class="card-val" style="color: #f8fafc;">26</div>
    <div class="card-sub">ground truth benchmark cases</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Directly Supported Cases</div>
    <div class="card-val" style="color: #4ade80;">{discrim_data['questions_answered']['Q_A_untranslation_evidence_coverage']['directly_supported']}</div>
    <div class="card-sub">user-facing English words retained</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Ambiguous (Tech/Brand Only)</div>
    <div class="card-val" style="color: #f59e0b;">{discrim_data['questions_answered']['Q_A_untranslation_evidence_coverage']['ambiguous_technical_only']}</div>
    <div class="card-sub">acronyms, OK/Cancel, DWG, etc.</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Unsupported (No English)</div>
    <div class="card-val" style="color: #94a3b8;">{discrim_data['questions_answered']['Q_A_untranslation_evidence_coverage']['unsupported_no_english']}</div>
    <div class="card-sub">OCR missed or subtle punctuation</div>
  </div>
</div>

<h2>Case-by-Case Untranslation Evidence Audit (26 Cases)</h2>
"""
    untrans_only = [c for c in eval_data if c["gt_category"] == "Untranslation"]
    for c in untrans_only:
        if c["evidence_support_level"] == "DIRECTLY_SUPPORTED":
            status_badge = "<span class='status-pass'>[PASS] Directly Supported</span>"
        elif c["evidence_support_level"] == "AMBIGUOUS":
            status_badge = "<span class='status-ambig'>[AMBIGUOUS] Technical/Brand Only</span>"
        else:
            status_badge = "<span class='status-fail'>[UNSUPPORTED]</span>"
            
        elem_rows = ""
        for el in c["genuine_untranslated_elements"]:
            elem_rows += f"""
      <tr>
        <td><code>{el['element_id']}</code></td>
        <td>'{el['enu_text']}'</td>
        <td><strong style='color:#4ade80;'>'{el['loc_text']}'</strong></td>
        <td>{', '.join(el['preserved_english_words'])}</td>
        <td>{el['latin_char_ratio']*100:.0f}%</td>
        <td><span style='color:#4ade80; font-weight:bold;'>USER_FACING_UI_WORDING</span></td>
      </tr>
"""
        for el in c["technical_brand_fp_elements"]:
            elem_rows += f"""
      <tr>
        <td><code>{el['element_id']}</code></td>
        <td>'{el['enu_text']}'</td>
        <td><span style='color:#f59e0b;'>'{el['loc_text']}'</span></td>
        <td>{', '.join(el['preserved_english_words']) if el['preserved_english_words'] else el['loc_text']}</td>
        <td>{el['latin_char_ratio']*100:.0f}%</td>
        <td><span style='color:#94a3b8;'>{el['text_semantic_category']}</span></td>
      </tr>
"""
        html_ev += f"""
<div class="case-card">
  <div class="case-header">
    <div>
      <span style="font-size:16px; font-weight:600;">Case #{c['case_id']}: {c['product']} / {c['folder']} ({c['lang']})</span>
      <span class="gt-badge" style="margin-left:10px;">GT: Untranslation</span>
    </div>
    <div>
      {status_badge}
    </div>
  </div>

  <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; font-size:13px; background:#0f172a; padding:12px; border-radius:6px; margin-bottom:12px;">
    <div><strong>Genuine Untranslated Strings:</strong> <span style="color:#4ade80; font-weight:bold;">{c['genuine_untranslated_strings_count']}</span></div>
    <div><strong>Technical/Brand Tokens:</strong> {c['potential_fp_technical_brand_count']}</div>
    <div><strong>Total English Chars Preserved:</strong> {c['total_english_chars_preserved']}</div>
    <div><strong>Support Level:</strong> {c['evidence_support_level']}</div>
  </div>

  <div style="font-size:13px; margin-bottom:6px;"><strong>Preserved English Text Elements:</strong></div>
  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>ENU Text</th>
        <th>Localized Text</th>
        <th>Preserved Words</th>
        <th>Latin Char %</th>
        <th>Semantic Category</th>
      </tr>
    </thead>
    <tbody>
      {elem_rows if elem_rows else "<tr><td colspan='6' style='text-align:center; color:#94a3b8;'>No preserved English text elements found by OCR.</td></tr>"}
    </tbody>
  </table>
</div>
"""
    html_ev += "</body></html>"
    with open(OUTPUT_EVIDENCE_HTML, 'w', encoding='utf-8') as f:
        f.write(html_ev)

    # 2. Generate untranslation_discrimination_analysis.html
    q = discrim_data["questions_answered"]
    cats = discrim_data["category_summary_distributions"]
    d_all = discrim_data["discrimination_rankings"]["vs_all_non_untranslation"]
    d_trunc = discrim_data["discrimination_rankings"]["vs_truncation"]
    d_mis = discrim_data["discrimination_rankings"]["vs_misalignment"]
    
    html_disc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Untranslation Physical Discrimination Analysis</title>
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
<h1>Untranslation Physical Discrimination Analysis</h1>
<div style="color: #94a3b8; font-size: 14px;">
  Evaluating the selectivity of user-facing English lexical preservation across all 101 benchmark cases (26 Untranslation vs. 75 Non-Untranslation).
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Untranslation Directly Supported</div>
    <div class="card-val" style="color: #4ade80;">{q['Q_A_untranslation_evidence_coverage']['directly_supported']}</div>
    <div class="card-sub">user-facing English words</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Non-Untranslation with Genuine English</div>
    <div class="card-val" style="color: #f43f5e;">{q['Q_B_non_untranslation_cases_with_preserved_english']['with_genuine_user_facing_english']}</div>
    <div class="card-sub">compound defect cases in baseline</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Technical/Brand Token Prevalence</div>
    <div class="card-val" style="color: #f59e0b;">{q['Q_C_technical_brand_tokens_vs_genuine_ui_strings']['technical_token_ratio_pct']}</div>
    <div class="card-sub">universal non-translatable tokens</div>
  </div>
  <div class="card">
    <div style="font-size: 13px; color: #94a3b8;">Top Separating Feature</div>
    <div class="card-val" style="font-size:15px;"><code>{d_all[0]['feature']}</code></div>
    <div class="card-sub">Fisher ratio: {d_all[0]['separation_ratio']}</div>
  </div>
</div>

<h2>1. Physical Feature Discrimination Power</h2>

<h3 style="color:#38bdf8; font-size:15px;">A. Untranslation vs All Non-Untranslation (N = 75)</h3>
<table>
  <thead>
    <tr>
      <th>Feature Measurement</th>
      <th>Untranslation Mean</th>
      <th>Non-Untranslation Mean</th>
      <th>Separation Ratio (Fisher Criterion)</th>
    </tr>
  </thead>
  <tbody>
"""
    for d in d_all:
        html_disc += f"""
    <tr>
      <td><code>{d['feature']}</code></td>
      <td style="color:#4ade80; font-weight:bold;">{d['untranslation_mean']}</td>
      <td>{d['non_untranslation_mean']}</td>
      <td style="color:#38bdf8; font-weight:bold;">{d['separation_ratio']:.4f}</td>
    </tr>
"""
    html_disc += """
  </tbody>
</table>

<h3 style="color:#38bdf8; font-size:15px; margin-top:20px;">B. Untranslation vs Truncation (N = 26 vs N = 30)</h3>
<table>
  <thead>
    <tr>
      <th>Feature Measurement</th>
      <th>Untranslation Mean</th>
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
      <td style="color:#4ade80; font-weight:bold;">{d['untranslation_mean']}</td>
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
      <th>Genuine Untranslated Strings (Mean/Med)</th>
      <th>Technical/Brand Tokens (Mean/Med)</th>
      <th>Preserved English Chars (Mean/Med)</th>
      <th>Preserved Latin Words (Mean/Med)</th>
    </tr>
  </thead>
  <tbody>
"""
    for cat_name, cdata in cats.items():
        is_un = (cat_name == "Untranslation")
        style = "background: #1e3a5f; font-weight:bold;" if is_un else ""
        html_disc += f"""
    <tr style="{style}">
      <td style="color: {'#38bdf8' if is_un else '#f8fafc'};">{cat_name} (N={cdata['count']})</td>
      <td>{cdata['genuine_untranslated_strings_count']['mean']:.2f} / {cdata['genuine_untranslated_strings_count']['median']:.1f}</td>
      <td>{cdata['potential_fp_technical_brand_count']['mean']:.2f} / {cdata['potential_fp_technical_brand_count']['median']:.1f}</td>
      <td>{cdata['total_english_chars_preserved']['mean']:.1f} / {cdata['total_english_chars_preserved']['median']:.1f}</td>
      <td>{cdata['total_latin_words_preserved']['mean']:.2f} / {cdata['total_latin_words_preserved']['median']:.1f}</td>
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
    eval_cases = evaluate_all_untranslation_evidence(records)
    
    # Save untranslation_evidence_v2.json
    with open(OUTPUT_EVIDENCE_JSON, 'w', encoding='utf-8') as f:
        json.dump(eval_cases, f, indent=2)
    print(f"Saved untranslation evidence JSON to {OUTPUT_EVIDENCE_JSON.resolve()}")
    
    discrim_results = run_untranslation_discrimination_analysis(eval_cases)
    
    # Save untranslation_discrimination_analysis.json
    with open(OUTPUT_DISCRIM_JSON, 'w', encoding='utf-8') as f:
        json.dump(discrim_results, f, indent=2)
    print(f"Saved untranslation discrimination JSON to {OUTPUT_DISCRIM_JSON.resolve()}")
    
    generate_html_reports(eval_cases, discrim_results)
    print(f"Saved visual HTML reports to {OUTPUT_EVIDENCE_HTML.resolve()} and {OUTPUT_DISCRIM_HTML.resolve()}")

    q = discrim_results["questions_answered"]
    print("\n" + "="*75)
    print("UNTRANSLATION PHYSICAL DISCRIMINATION SUMMARY")
    print("="*75)
    print(f"Q_A. Untranslation evidence coverage (Direct)     : {q['Q_A_untranslation_evidence_coverage']['directly_supported']}")
    print(f"     Untranslation evidence coverage (Ambiguous)  : {q['Q_A_untranslation_evidence_coverage']['ambiguous_technical_only']}")
    print(f"     Untranslation evidence coverage (Unsupported): {q['Q_A_untranslation_evidence_coverage']['unsupported_no_english']}")
    print(f"Q_B. Non-Untranslation with genuine English       : {q['Q_B_non_untranslation_cases_with_preserved_english']['with_genuine_user_facing_english']}")
    print(f"     Non-Untranslation with technical/brand only  : {q['Q_B_non_untranslation_cases_with_preserved_english']['with_technical_brand_only']}")
    print(f"Q_C. Technical/Brand Token Prevalence             : {q['Q_C_technical_brand_tokens_vs_genuine_ui_strings']['technical_token_ratio_pct']}")
    print("\nTop Separating Feature (Untranslation vs Non-Untranslation):")
    for d in discrim_results["discrimination_rankings"]["vs_all_non_untranslation"]:
        print(f"  - {d['feature']:35s}: Ratio = {d['separation_ratio']:.4f} (Untrans: {d['untranslation_mean']} vs Non-Untrans: {d['non_untranslation_mean']})")
    print("="*75 + "\n")

if __name__ == '__main__':
    main()
