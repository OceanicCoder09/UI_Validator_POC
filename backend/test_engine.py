"""
Test suite for cv_engine.py across all Autodesk Helpdesk presets.
"""
import os
import cv2
from cv_engine import analyze_localization_quality

def run_tests():
    sample_dir = os.path.join(os.path.dirname(__file__), "sample_data")
    en_path = os.path.join(sample_dir, "en_baseline.png")
    
    presets = [
        ("de_perfect.png", "German Perfect", 95, 100),
        ("de_expansion_defect.png", "German Expansion Defect", 70, 80),
        ("es_missing_misaligned.png", "Spanish Missing Component & Misaligned", 65, 75),
        ("ja_shift_overlap.png", "Japanese Shift & Overlap", 30, 45),
    ]
    
    en_img = cv2.imread(en_path)
    assert en_img is not None, f"Failed to load {en_path}"
    
    print("==================================================")
    print("RUNNING LOCALIZATION UI QUALITY CHECKER ENGINE TESTS")
    print("==================================================")
    
    for filename, label, min_score, max_score in presets:
        path = os.path.join(sample_dir, filename)
        loc_img = cv2.imread(path)
        assert loc_img is not None, f"Failed to load {path}"
        
        result = analyze_localization_quality(en_img, loc_img)
        score = result["score"]
        grade = result["grade"]
        defects = result["summary"]["total_defects"]
        
        print(f"\n[SCENARIO] {label} ({filename})")
        print(f"  Quality Score: {score}/100 (Grade: {grade})")
        print(f"  Total Defects Detected: {defects}")
        for f in result["findings"]:
            print(f"    - [{f['severity'].upper()}] {f['category']}: {f['title']}")
            
        assert min_score <= score <= max_score, f"Score {score} out of expected range [{min_score}, {max_score}] for {filename}"
        
    # Verify Autodesk Live Documentation screenshot pair
    doc_en_path = os.path.join(os.path.dirname(__file__), "..", "extracted_pdf_images", "new_report", "img_0_2_I1.png")
    doc_loc_path = os.path.join(os.path.dirname(__file__), "..", "extracted_pdf_images", "new_report", "img_0_3_I2.png")
    if os.path.exists(doc_en_path) and os.path.exists(doc_loc_path):
        doc_en = cv2.imread(doc_en_path)
        doc_loc = cv2.imread(doc_loc_path)
        doc_res = analyze_localization_quality(doc_en, doc_loc)
        print(f"\n[SCENARIO] Autodesk Live Documentation (Clean Web UI)")
        print(f"  Quality Score: {doc_res['score']}/100 (Grade: {doc_res['grade']})")
        print(f"  Total Defects Detected: {doc_res['summary']['total_defects']}")
        assert doc_res['score'] >= 95, f"Expected clean live UI to score >= 95, got {doc_res['score']}"
        
def run_dataset_benchmark():
    import pandas as pd
    from PIL import Image
    import pathlib
    
    excel_path = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize/Screenshot data list from Welocalize.xlsx')
    base_data_root = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize')
    
    if not excel_path.exists():
        print(f"Skipping dataset benchmark: {excel_path} not found.")
        return
        
    df = pd.read_excel(excel_path, engine='openpyxl')
    print("\n==================================================")
    print(f"RUNNING WELOCALIZE DATASET BENCHMARK ({len(df)} cases)")
    print("==================================================")
    
    total_evaluated = 0
    flagged_defective = 0
    
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
        except Exception:
            continue
            
        total_evaluated += 1
        res = analyze_localization_quality(en_img, loc_img)
        if len(res.get('findings', [])) > 0:
            flagged_defective += 1
            
    print(f"Successfully evaluated: {total_evaluated} pairs")
    print(f"Flagged as defective: {flagged_defective}/{total_evaluated} ({flagged_defective/total_evaluated*100:.1f}%)")
    print("==================================================")

if __name__ == "__main__":
    import numpy as np
    run_tests()
    run_dataset_benchmark()
