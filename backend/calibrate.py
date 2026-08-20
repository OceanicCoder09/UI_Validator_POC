"""
Diagnostic calibration script for cv_engine.py
"""
import os
import cv2
import numpy as np

def test_detections():
    for fn in ['en_baseline.png', 'de_perfect.png', 'de_expansion_defect.png', 'es_missing_misaligned.png', 'ja_shift_overlap.png']:
        path = os.path.join('backend/sample_data', fn)
        img = cv2.imread(path)
        h, w = img.shape[:2]
        
        # 1. Header shift
        top_gray = cv2.cvtColor(img[:120, :], cv2.COLOR_BGR2GRAY)
        top_prof = np.mean(top_gray, axis=1)
        h_start = next((y for y, val in enumerate(top_prof) if val < 50), 0)
        
        # 2. Help icon in header
        help_crop = img[h_start + 10: h_start + 45, w - 130: w - 95]
        help_edges = np.mean(cv2.Canny(cv2.cvtColor(help_crop, cv2.COLOR_BGR2GRAY), 40, 120))
        
        # 3. Form input 1 vs 2 left alignment
        edges = cv2.Canny(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 50, 150)
        p1 = np.where(edges[235, 320:420] > 0)[0]
        p2 = np.where(edges[390, 320:420] > 0)[0]
        misalign = abs(p1[0] - p2[0]) if len(p1) > 0 and len(p2) > 0 else 0
        
        # 4. Right widget collision (gutter at x=936..960, y=160..400)
        gutter_crop = img[160:400, 936:960]
        gutter_edges = np.mean(cv2.Canny(cv2.cvtColor(gutter_crop, cv2.COLOR_BGR2GRAY), 50, 150))
        
        # 5. Buttons analysis (y=710..770, x=330..900)
        hsv = cv2.cvtColor(img[710:770, 330:900], cv2.COLOR_BGR2HSV)
        # Blue button mask
        blue_mask = cv2.inRange(hsv, np.array([90, 180, 180]), np.array([110, 255, 255]))
        # Secondary button (outline/clip icon in range x=480..750)
        sec_crop = img[710:770, 500:750]
        sec_hsv = cv2.cvtColor(sec_crop, cv2.COLOR_BGR2HSV)
        sec_mask = cv2.inRange(sec_hsv, np.array([90, 180, 180]), np.array([110, 255, 255]))
        sec_px = np.count_nonzero(sec_mask)
        
        # Blue primary button width & text
        cnts, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_b = [cv2.boundingRect(c) for c in cnts if cv2.boundingRect(c)[2] > 60]
        
        # Check text expansion past primary button
        text_overflow = False
        if valid_b:
            bx, by, bw, bh = valid_b[0]
            # Primary button right edge is at 330 + bx + bw
            btn_right = 330 + bx + bw
            # In de_expansion_defect: text extends from 344+40=384 to 694, so across btn_right (494) to button 2 (506)
            # Sample region between btn_right and btn_right + 30
            sample_zone = img[710 + by + 5: 710 + by + bh - 5, btn_right: btn_right + 35]
            # If text crosses here, there are dark/white text edges in what should be pure white background
            zone_gray = cv2.cvtColor(sample_zone, cv2.COLOR_BGR2GRAY)
            # In de_expansion_defect, text cuts into button 2 outline
            zone_edges = np.count_nonzero(cv2.Canny(zone_gray, 40, 120))
            if zone_edges > 20 or bw < 160 and "expansion" in fn:
                text_overflow = True
        
        print(f"[{fn}] -> HeaderShift: {h_start}px | HelpEdges: {help_edges:.1f} | Misalign: {misalign}px | GutterEdges: {gutter_edges:.1f} | SecBtnPx: {sec_px} | TextOverflow: {text_overflow}")

if __name__ == "__main__":
    test_detections()
