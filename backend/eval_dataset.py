import pandas as pd
import pathlib
import os
import cv2
import numpy as np
from PIL import Image
import sys
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from cv_engine import analyze_localization_quality

excel_path = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize/Screenshot data list from Welocalize.xlsx')
base_data_root = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize')

df = pd.read_excel(excel_path, engine='openpyxl')
print(f"Total rows in Excel: {len(df)}", flush=True)

results = []
evaluated_count = 0

start_t = time.time()

for idx, row in df.iterrows():
    product = str(row['Product']).strip()
    folder = str(row['Screenshot Folder Name']).strip()
    lang = str(row['Language']).strip()
    
    target_dir = base_data_root / product / folder
    en_files = list(target_dir.glob('(ENU)*.*'))
    loc_files = list(target_dir.glob(f'({lang})*.*'))
    
    if not en_files or not loc_files:
        continue
        
    try:
        en_img = cv2.cvtColor(np.array(Image.open(en_files[0]).convert('RGB')), cv2.COLOR_RGB2BGR)
        loc_img = cv2.cvtColor(np.array(Image.open(loc_files[0]).convert('RGB')), cv2.COLOR_RGB2BGR)
    except Exception as e:
        continue
        
    t0 = time.time()
    res = analyze_localization_quality(en_img, loc_img)
    dt = time.time() - t0
    
    findings = res.get('findings', [])
    candidates = []
    for f in findings:
        candidates.append({
            'category': f.get('category'),
            'code': f.get('code'),
            'confidence': f.get('confidence', 0.8),
            'evidence': f.get('evidence', {}),
            'location': f.get('location', {})
        })
        
    categories_found = [c['category'] for c in candidates]
    
    evaluated_count += 1
    gt_cat = str(row.get('Defect Catogery', row.get('Defect Category', 'Unknown'))).strip()
    
    # Map GT category to expected engine codes
    gt_upper = gt_cat.upper()
    expected_categories = set()
    if 'TRUNCATION' in gt_upper: expected_categories.add('TRUNCATION')
    elif 'OVERLAPPING' in gt_upper and 'MISALIGNMENT' in gt_upper: expected_categories.update(['OVERLAPPING', 'MISSALIGNMENT'])
    elif 'OVERLAPPING' in gt_upper: expected_categories.add('OVERLAPPING')
    elif 'MISALIGNMENT' in gt_upper: expected_categories.add('MISSALIGNMENT')
    elif 'UNTRANSLATION' in gt_upper: expected_categories.add('UNTRANSLATION')
    elif 'HOTKEY' in gt_upper: expected_categories.add('HOTKEY_DEFECT')
    elif 'DIFFERENT' in gt_upper or 'CONTROL' in gt_upper: expected_categories.update(['MISC', 'SPEC_CHARACTERS'])
    elif 'LAYOUT' in gt_upper: expected_categories.update(['MISC', 'MISSALIGNMENT', 'OVERLAPPING', 'TRUNCATION'])
    elif 'PUNCTUATION' in gt_upper or 'SPACE' in gt_upper: expected_categories.update(['LEAD_TRAIL', 'MISSALIGNMENT'])
    elif 'SYMBOL' in gt_upper: expected_categories.add('SPEC_CHARACTERS')
    else: expected_categories.add(gt_upper)
    
    is_gt_present = bool(set(categories_found).intersection(expected_categories))
    
    print(f"[{evaluated_count}] {product}/{folder} ({lang}) in {dt:.2f}s | GT: {gt_cat} | Candidates: {categories_found} | GT Present: {is_gt_present}", flush=True)
    
    results.append({
        'product': product,
        'folder': folder,
        'lang': lang,
        'detected_count': len(findings),
        'detected_categories': categories_found,
        'candidates': candidates,
        'score': res['score'],
        'gt_category': gt_cat,
        'gt_description': str(row.get('Defect Description', '')),
        'is_gt_present_in_candidates': is_gt_present
    })

print(f"\n=======================================================", flush=True)
print(f"EVALUATION COMPLETE IN {time.time()-start_t:.1f}s", flush=True)
print(f"Total Evaluated Pairs: {len(results)}", flush=True)

# Category stats
category_breakdown = {}
for r in results:
    cat = r['gt_category']
    if not cat or cat == 'nan':
        cat = 'Uncategorized'
    if cat not in category_breakdown:
        category_breakdown[cat] = {'total': 0, 'detected': 0, 'categories_matched': 0}
    category_breakdown[cat]['total'] += 1
    if r['detected_count'] > 0:
        category_breakdown[cat]['detected'] += 1

print("\n=== BREAKDOWN BY GROUND TRUTH CATEGORY ===", flush=True)
for cat, stats in sorted(category_breakdown.items(), key=lambda x: x[1]['total'], reverse=True):
    det = stats['detected']
    tot = stats['total']
    pct = (det / tot * 100) if tot > 0 else 0
    print(f"  • {cat:25s}: {det}/{tot} caught ({pct:5.1f}%)", flush=True)

detected = [r for r in results if r['detected_count'] > 0]
not_detected = [r for r in results if r['detected_count'] == 0]

print(f"\n=== OVERALL SUMMARY ===", flush=True)
print(f"Total evaluated pairs: {len(results)}", flush=True)
print(f"Overall Defect Recall (Caught): {len(detected)}/{len(results)} ({len(detected)/len(results)*100:.2f}%)", flush=True)
print(f"Not Detected / Marked Clean: {len(not_detected)}/{len(results)} ({len(not_detected)/len(results)*100:.2f}%)", flush=True)

# Save JSON result
out_json = pathlib.Path('backend/eval_results.json')
with open(out_json, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2)
print(f"\nSaved detailed results to {out_json.resolve()}", flush=True)
