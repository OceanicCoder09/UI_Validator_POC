import os
import sys
import json
import time
import pathlib
import cv2
import numpy as np
from PIL import Image
import pandas as pd

def align_and_resize(img_en, img_loc):
    """Aligns dimensions between baseline and localized screenshots."""
    h_en, w_en = img_en.shape[:2]
    h_loc, w_loc = img_loc.shape[:2]
    
    if (h_en, w_en) == (h_loc, w_loc):
        return img_en, img_loc
        
    # Resize localized image to match baseline if dimensions differ slightly
    img_loc_aligned = cv2.resize(img_loc, (w_en, h_en), interpolation=cv2.INTER_LINEAR)
    return img_en, img_loc_aligned

def compute_difference_map(img_en, img_loc):
    """Computes a multi-scale structural and pixel difference map."""
    gray_en = cv2.cvtColor(img_en, cv2.COLOR_BGR2GRAY)
    gray_loc = cv2.cvtColor(img_loc, cv2.COLOR_BGR2GRAY)
    
    # 1. Absolute pixel difference
    diff_pixel = cv2.absdiff(gray_en, gray_loc)
    
    # 2. Gradient magnitude difference
    grad_en = cv2.morphologyEx(gray_en, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    grad_loc = cv2.morphologyEx(gray_loc, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    diff_grad = cv2.absdiff(grad_en, grad_loc)
    
    # 3. Edge difference
    canny_en = cv2.Canny(gray_en, 50, 150)
    canny_loc = cv2.Canny(gray_loc, 50, 150)
    diff_edge = cv2.absdiff(canny_en, canny_loc)
    
    # Combined composite diff
    combined = cv2.addWeighted(diff_pixel, 0.45, diff_grad, 0.35, 0)
    combined = cv2.addWeighted(combined, 0.80, diff_edge, 0.20, 0)
    
    return combined, diff_pixel

def merge_close_boxes(boxes, max_x_dist=24, max_y_dist=14):
    """Merges adjacent and closely aligned changed boxes into unified UI component regions."""
    if not boxes:
        return []
        
    # Initial sort top-to-bottom, left-to-right
    sorted_boxes = sorted(boxes, key=lambda b: (b[1] // 16, b[0]))
    merged = []
    
    for b in sorted_boxes:
        bx, by, bw, bh = b
        merged_with_existing = False
        
        for i, mb in enumerate(merged):
            mx, my, mw, mh = mb
            # Check horizontal proximity on the same horizontal baseline
            same_row = abs((by + bh / 2) - (my + mh / 2)) <= max(14, min(bh, mh) * 0.8)
            close_x = (bx <= mx + mw + max_x_dist) and (mx <= bx + bw + max_x_dist)
            
            # Check vertical proximity in same column
            same_col = abs((bx + bw / 2) - (mx + mw / 2)) <= max(20, min(bw, mw) * 0.8)
            close_y = (by <= my + mh + max_y_dist) and (my <= by + bh + max_y_dist)
            
            # Check overlap or container inclusion
            overlap_x = max(0, min(bx + bw, mx + mw) - max(bx, mx))
            overlap_y = max(0, min(by + bh, my + mh) - max(by, my))
            is_intersecting = (overlap_x > 0 and overlap_y > 0)
            
            if (same_row and close_x) or (same_col and close_y) or is_intersecting:
                new_x = min(bx, mx)
                new_y = min(by, my)
                new_w = max(bx + bw, mx + mw) - new_x
                new_h = max(by + bh, my + mh) - new_y
                merged[i] = (new_x, new_y, new_w, new_h)
                merged_with_existing = True
                break
                
        if not merged_with_existing:
            merged.append((bx, by, bw, bh))
            
    # Second-pass consolidation
    final_merged = []
    for mb in merged:
        bx, by, bw, bh = mb
        merged_again = False
        for i, fb in enumerate(final_merged):
            fx, fy, fw, fh = fb
            overlap_x = max(0, min(bx + bw, fx + fw) - max(bx, fx))
            overlap_y = max(0, min(by + bh, fy + fh) - max(by, fy))
            if (overlap_x > 0 and overlap_y > 0) or (abs((by + bh/2) - (fy + fh/2)) <= 12 and bx <= fx + fw + 16 and fx <= bx + bw + 16):
                new_x = min(bx, fx)
                new_y = min(by, fy)
                new_w = max(bx + bw, fx + fw) - new_x
                new_h = max(by + bh, fy + fh) - new_y
                final_merged[i] = (new_x, new_y, new_w, new_h)
                merged_again = True
                break
        if not merged_again:
            final_merged.append(mb)
            
    return final_merged

def extract_change_regions(img_en, img_loc, min_w=14, min_h=8, min_area=140):
    """Extracts meaningful UI change regions without any categorization."""
    h_img, w_img = img_en.shape[:2]
    combined_diff, diff_pixel = compute_difference_map(img_en, img_loc)
    
    # Threshold diff map to find active change pixels
    _, thresh = cv2.threshold(combined_diff, 18, 255, cv2.THRESH_BINARY)
    
    # Morphological grouping to connect letters into word blocks and UI controls
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 4))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel_h)
    
    cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    raw_boxes = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        # Filter out negligible noise speckles
        if w >= min_w and h >= min_h and area >= min_area and w <= w_img * 0.98 and h <= h_img * 0.98:
            raw_boxes.append((x, y, w, h))
            
    # Merge proximate boxes into complete changed component regions
    merged_boxes = merge_close_boxes(raw_boxes)
    
    # Calculate difference intensity for each region
    regions = []
    for b in merged_boxes:
        x, y, w, h = b
        roi_diff = diff_pixel[y:y+h, x:x+w]
        if roi_diff.size == 0:
            continue
        diff_score = float(np.mean(roi_diff))
        # Filter out regions with near-zero difference (e.g. compression noise)
        if diff_score >= 2.5:
            regions.append({
                "box": (int(x), int(y), int(w), int(h)),
                "difference_score": round(diff_score, 2),
                "area": int(w * h)
            })
            
    # Sort regions by difference intensity descending
    regions.sort(key=lambda r: (r["difference_score"] * np.log1p(r["area"])), reverse=True)
    return regions, diff_pixel

def save_region_crops(img_en, img_loc, diff_pixel, regions, case_dir, padding=12):
    """Saves Before, After, and Difference heatmap crops for each isolated region."""
    os.makedirs(case_dir, exist_ok=True)
    h_img, w_img = img_en.shape[:2]
    
    # Create difference heatmap
    diff_norm = cv2.normalize(diff_pixel, None, 0, 255, cv2.NORM_MINMAX)
    heatmap_colored = cv2.applyColorMap(diff_norm, cv2.COLORMAP_JET)
    diff_composite = cv2.addWeighted(img_loc, 0.45, heatmap_colored, 0.55, 0)
    
    saved_crops = []
    
    for idx, reg in enumerate(regions):
        x, y, w, h = reg["box"]
        # Apply contextual padding
        px1 = max(0, x - padding)
        py1 = max(0, y - padding)
        px2 = min(w_img, x + w + padding)
        py2 = min(h_img, y + h + padding)
        
        crop_en = img_en[py1:py2, px1:px2]
        crop_loc = img_loc[py1:py2, px1:px2]
        crop_diff = diff_composite[py1:py2, px1:px2]
        
        p_en = os.path.join(case_dir, f"region_{idx+1}_before.png")
        p_loc = os.path.join(case_dir, f"region_{idx+1}_after.png")
        p_diff = os.path.join(case_dir, f"region_{idx+1}_diff.png")
        
        cv2.imwrite(p_en, crop_en)
        cv2.imwrite(p_loc, crop_loc)
        cv2.imwrite(p_diff, crop_diff)
        
        saved_crops.append({
            "region_id": idx + 1,
            "coordinates": {"x": x, "y": y, "width": w, "height": h},
            "padded_coordinates": {"x": px1, "y": py1, "width": px2 - px1, "height": py2 - py1},
            "difference_score": reg["difference_score"],
            "area": reg["area"],
            "before_crop_path": os.path.relpath(p_en, start="backend").replace("\\", "/"),
            "after_crop_path": os.path.relpath(p_loc, start="backend").replace("\\", "/"),
            "diff_crop_path": os.path.relpath(p_diff, start="backend").replace("\\", "/"),
        })
        
    return saved_crops

def generate_html_report(all_cases_data, output_html_path):
    """Generates an HTML contact-sheet report for visual manual inspection of isolated regions."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Visual Change Regions — 114 Benchmark Cases</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }
  h1 { color: #38bdf8; font-size: 24px; margin-bottom: 8px; }
  .summary-bar { background: #1e293b; padding: 16px 20px; border-radius: 8px; margin-bottom: 24px; border: 1px solid #334155; display: flex; gap: 32px; font-size: 15px; }
  .case-card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; margin-bottom: 28px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); }
  .case-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 12px; margin-bottom: 16px; }
  .case-title { font-size: 18px; font-weight: 600; color: #f1f5f9; }
  .case-meta { font-size: 13px; color: #94a3b8; }
  .regions-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 16px; }
  .region-box { background: #0f172a; border: 1px solid #475569; border-radius: 6px; padding: 12px; }
  .region-header { display: flex; justify-content: space-between; font-size: 12px; color: #38bdf8; margin-bottom: 8px; font-weight: 600; }
  .crop-trio { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
  .crop-col { text-align: center; }
  .crop-col span { display: block; font-size: 11px; color: #94a3b8; margin-bottom: 4px; }
  .crop-col img { max-width: 100%; max-height: 160px; object-fit: contain; border: 1px solid #334155; border-radius: 4px; background: #020617; }
  .no-regions { color: #f43f5e; font-style: italic; font-size: 14px; padding: 8px 0; }
</style>
</head>
<body>
<h1>Visual Change Detector — Isolated Region Contact Sheet</h1>
<div class="summary-bar">
  <div>Total Cases Evaluated: <strong>""" + str(len(all_cases_data)) + """</strong></div>
  <div>Total Change Regions Isolated: <strong>""" + str(sum(len(c["regions"]) for c in all_cases_data)) + """</strong></div>
  <div>Avg Regions / Screen: <strong>""" + f"{sum(len(c['regions']) for c in all_cases_data) / max(1, len(all_cases_data)):.2f}" + """</strong></div>
</div>
"""

    for c in all_cases_data:
        case_id = c["case_id"]
        product = c["product"]
        folder = c["folder"]
        lang = c["lang"]
        regions = c["regions"]
        
        html_content += f"""
<div class="case-card">
  <div class="case-header">
    <div>
      <span class="case-title">#{case_id}: {product} / {folder} ({lang})</span>
    </div>
    <div class="case-meta">
      Change Regions: <strong>{len(regions)}</strong>
    </div>
  </div>
"""
        if not regions:
            html_content += """<div class="no-regions">No meaningful visual change regions isolated (Canvas clean or sub-threshold diff).</div>"""
        else:
            html_content += """<div class="regions-grid">"""
            for reg in regions:
                r_id = reg["region_id"]
                coords = reg["coordinates"]
                score = reg["difference_score"]
                b_path = reg["before_crop_path"]
                a_path = reg["after_crop_path"]
                d_path = reg["diff_crop_path"]
                
                html_content += f"""
  <div class="region-box">
    <div class="region-header">
      <span>Region #{r_id} (x={coords['x']}, y={coords['y']}, {coords['width']}x{coords['height']}px)</span>
      <span>Diff Score: {score}</span>
    </div>
    <div class="crop-trio">
      <div class="crop-col">
        <span>Baseline (Before)</span>
        <img src="{b_path}" alt="Before" loading="lazy" />
      </div>
      <div class="crop-col">
        <span>Localized (After)</span>
        <img src="{a_path}" alt="After" loading="lazy" />
      </div>
      <div class="crop-col">
        <span>Diff Heatmap</span>
        <img src="{d_path}" alt="Diff" loading="lazy" />
      </div>
    </div>
  </div>
"""
            html_content += """</div>"""
            
        html_content += """</div>"""

    html_content += """
</body>
</html>
"""
    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

def main():
    excel_path = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize/Screenshot data list from Welocalize.xlsx')
    base_data_root = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize')
    
    crops_base_dir = pathlib.Path('backend/crops')
    output_json_path = pathlib.Path('backend/change_regions.json')
    output_html_path = pathlib.Path('backend/change_regions_report.html')
    
    df = pd.read_excel(excel_path, engine='openpyxl')
    print(f"Loaded {len(df)} rows from Excel dataset.", flush=True)
    
    all_cases_data = []
    case_idx = 0
    t_start = time.time()
    
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
            img_en = cv2.cvtColor(np.array(Image.open(en_files[0]).convert('RGB')), cv2.COLOR_RGB2BGR)
            img_loc = cv2.cvtColor(np.array(Image.open(loc_files[0]).convert('RGB')), cv2.COLOR_RGB2BGR)
        except Exception as e:
            print(f"Error loading images for {product}/{folder}: {e}", flush=True)
            continue
            
        case_idx += 1
        case_id_str = f"case_{case_idx:03d}_{product}_{folder}_{lang}"
        case_crop_dir = crops_base_dir / case_id_str
        
        # 1. Align dimensions
        img_en_aligned, img_loc_aligned = align_and_resize(img_en, img_loc)
        
        # 2. Extract meaningful changed regions
        regions, diff_pixel = extract_change_regions(img_en_aligned, img_loc_aligned)
        
        # 3. Save Before/After/Diff crops for each region
        saved_crops = save_region_crops(img_en_aligned, img_loc_aligned, diff_pixel, regions, str(case_crop_dir))
        
        print(f"[{case_idx}/114] {product}/{folder} ({lang}) -> {len(saved_crops)} visual change regions isolated", flush=True)
        
        all_cases_data.append({
            "case_id": case_idx,
            "case_key": case_id_str,
            "product": product,
            "folder": folder,
            "lang": lang,
            "regions_count": len(saved_crops),
            "regions": saved_crops
        })
        
    print(f"\n=======================================================", flush=True)
    print(f"REGION EXTRACTION COMPLETE IN {time.time() - t_start:.2f}s", flush=True)
    print(f"Total Cases Processed: {len(all_cases_data)}", flush=True)
    print(f"Total Change Regions: {sum(c['regions_count'] for c in all_cases_data)}", flush=True)
    
    # Save change_regions.json
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(all_cases_data, f, indent=2)
    print(f"Saved region data to {output_json_path.resolve()}", flush=True)
    
    # Generate HTML contact-sheet
    generate_html_report(all_cases_data, output_html_path)
    print(f"Saved visual HTML report to {output_html_path.resolve()}", flush=True)

if __name__ == '__main__':
    main()
