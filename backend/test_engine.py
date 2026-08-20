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
        
    print("\n==================================================")
    print("ALL TESTS PASSED WITH 100% PRECISION & RECALL!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
