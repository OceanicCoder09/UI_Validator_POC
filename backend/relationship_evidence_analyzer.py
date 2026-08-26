import os
import sys
import json
import pathlib
import numpy as np

POC_JSON_PATH = pathlib.Path('backend/ui_relationship_poc.json')
OUTPUT_REPORT_JSON = pathlib.Path('backend/relationship_evidence_summary.json')
OUTPUT_REPORT_MD = pathlib.Path('backend/relationship_evidence_report.md')

def calc_box_gap_and_alignment(box1, box2):
    """
    Computes horizontal gap, vertical gap, left alignment delta, and top alignment delta.
    box: (x, y, w, h)
    """
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    
    # Horizontal gap (positive = separated, negative = overlapping)
    if x1 + w1 <= x2:
        h_gap = x2 - (x1 + w1)
    elif x2 + w2 <= x1:
        h_gap = x1 - (x2 + w2)
    else:
        # Overlapping horizontally
        inter_x1 = max(x1, x2)
        inter_x2 = min(x1 + w1, x2 + w2)
        h_gap = -(inter_x2 - inter_x1)
        
    # Vertical gap
    if y1 + h1 <= y2:
        v_gap = y2 - (y1 + h1)
    elif y2 + h2 <= y1:
        v_gap = y1 - (y2 + h2)
    else:
        inter_y1 = max(y1, y2)
        inter_y2 = min(y1 + h1, y2 + h2)
        v_gap = -(inter_y2 - inter_y1)
        
    # Alignment deltas
    left_align_delta = abs(x1 - x2)
    top_align_delta = abs(y1 - y2)
    
    # Bounding-box intersection area
    inter_w = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
    inter_h = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
    intersection_area = inter_w * inter_h
    
    return {
        "h_gap": int(h_gap),
        "v_gap": int(v_gap),
        "left_align_delta": int(left_align_delta),
        "top_align_delta": int(top_align_delta),
        "intersection_area": int(intersection_area)
    }

def analyze_case_evidence(case_data):
    """
    Analyzes fine-grained relationship evidence for a single case:
    1. Independent movement vs global translation (residual dx/dy relative to median shift)
    2. Sibling gap expansion/collapse
    3. Left-column alignment divergence
    4. Newly created bounding-box intersections
    5. Text expansion relative to available sibling gap
    """
    case_id = case_data["case_id"]
    product = case_data["product"]
    folder = case_data["folder"]
    lang = case_data["lang"]
    gt_category = case_data["gt_category"]
    
    enu_elements = {e["id"]: e for e in case_data["enu_elements"]}
    loc_elements = {l["id"]: l for l in case_data["loc_elements"]}
    relationships = case_data["relationships"]
    
    # Calculate global median translation to separate whole-dialog shift from independent movement
    all_dx = [r["spatial_changes"]["dx"] for r in relationships]
    all_dy = [r["spatial_changes"]["dy"] for r in relationships]
    median_dx = float(np.median(all_dx)) if all_dx else 0.0
    median_dy = float(np.median(all_dy)) if all_dy else 0.0
    
    ranked_evidence_records = []
    
    # 1. Evaluate Sibling Pairs that existed in both ENU and Localized
    matched_pairs = [(r["enu_id"], r["loc_id"], r) for r in relationships]
    
    # Check pairwise relationship changes between matched siblings
    for i in range(len(matched_pairs)):
        enu_id1, loc_id1, r1 = matched_pairs[i]
        e1 = enu_elements.get(enu_id1)
        l1 = loc_elements.get(loc_id1)
        if not e1 or not l1: continue
        
        # Independent movement of Element 1 (residual displacement from median)
        indep_dx1 = r1["spatial_changes"]["dx"] - median_dx
        indep_dy1 = r1["spatial_changes"]["dy"] - median_dy
        indep_mag1 = float(np.hypot(indep_dx1, indep_dy1))
        
        # Self-expansion (width expansion relative to ENU width)
        w_expansion_ratio = l1["width"] / max(1.0, e1["width"])
        
        for j in range(i + 1, len(matched_pairs)):
            enu_id2, loc_id2, r2 = matched_pairs[j]
            e2 = enu_elements.get(enu_id2)
            l2 = loc_elements.get(loc_id2)
            if not e2 or not l2: continue
            
            box_e1 = (e1["x"], e1["y"], e1["width"], e1["height"])
            box_e2 = (e2["x"], e2["y"], e2["width"], e2["height"])
            box_l1 = (l1["x"], l1["y"], l1["width"], l1["height"])
            box_l2 = (l2["x"], l2["y"], l2["width"], l2["height"])
            
            # Sibling proximity filter: only inspect elements in nearby spatial proximity (within 150px)
            dist_e = np.hypot(e1["center"][0] - e2["center"][0], e1["center"][1] - e2["center"][1])
            if dist_e > 180:
                continue
                
            rel_before = calc_box_gap_and_alignment(box_e1, box_e2)
            rel_after = calc_box_gap_and_alignment(box_l1, box_l2)
            
            # Relative movement between the two siblings
            diff_dx = abs(r1["spatial_changes"]["dx"] - r2["spatial_changes"]["dx"])
            diff_dy = abs(r1["spatial_changes"]["dy"] - r2["spatial_changes"]["dy"])
            rel_displacement = float(np.hypot(diff_dx, diff_dy))
            
            # A. Check for Newly Created Bounding Box Overlap / Intersection
            inter_before = rel_before["intersection_area"]
            inter_after = rel_after["intersection_area"]
            if inter_before == 0 and inter_after > 0:
                strength = float(inter_after)
                ranked_evidence_records.append({
                    "element": f"{enu_id1} ({e1['text'][:20]})",
                    "neighbor": f"{enu_id2} ({e2['text'][:20]})",
                    "mechanism": "NEW_OVERLAP_COLLISION",
                    "relationship": "Bounding-Box Intersection Area",
                    "before": f"{inter_before}px² (Clean)",
                    "after": f"{inter_after}px² (Colliding)",
                    "delta": f"+{inter_after}px² intersection",
                    "evidence_strength": round(strength, 2),
                    "evidence_type": "OVERLAP_INTERSECTION"
                })
                
            # B. Check for Horizontal Sibling Gap Collapse / Expansion
            gap_delta = rel_after["h_gap"] - rel_before["h_gap"]
            if rel_before["h_gap"] > 0 and rel_after["h_gap"] <= 0 and abs(e1["y"] - e2["y"]) < 20:
                # Text expanded and consumed full gap into adjacent control
                strength = abs(gap_delta) * (w_expansion_ratio)
                ranked_evidence_records.append({
                    "element": f"{enu_id1} ({e1['text'][:20]})",
                    "neighbor": f"{enu_id2} ({e2['text'][:20]})",
                    "mechanism": "SIBLING_GAP_COLLAPSED",
                    "relationship": "Horizontal Sibling Gutter Gap",
                    "before": f"{rel_before['h_gap']}px gap",
                    "after": f"{rel_after['h_gap']}px gap (Collapsed)",
                    "delta": f"{gap_delta:+d}px gap change",
                    "evidence_strength": round(strength, 2),
                    "evidence_type": "GAP_COLLAPSE"
                })
                
            # C. Check for Independent Alignment Shift (Left Column Divergence)
            # If two elements were vertically aligned in ENU (left_align_delta <= 4px) but separated in Loc
            align_delta_diff = rel_after["left_align_delta"] - rel_before["left_align_delta"]
            if rel_before["left_align_delta"] <= 4 and rel_after["left_align_delta"] >= 10:
                strength = float(rel_after["left_align_delta"])
                ranked_evidence_records.append({
                    "element": f"{enu_id1} ({e1['text'][:20]})",
                    "neighbor": f"{enu_id2} ({e2['text'][:20]})",
                    "mechanism": "INDEPENDENT_COLUMN_DISPLACEMENT",
                    "relationship": "Left-Anchor Column Alignment",
                    "before": f"{rel_before['left_align_delta']}px aligned",
                    "after": f"{rel_after['left_align_delta']}px shifted",
                    "delta": f"{align_delta_diff:+d}px divergence",
                    "evidence_strength": round(strength, 2),
                    "evidence_type": "COLUMN_MISALIGNMENT"
                })
                
            # D. Independent Movement Magnitude between Sibling Elements
            if rel_displacement >= 12.0:
                strength = float(rel_displacement)
                ranked_evidence_records.append({
                    "element": f"{enu_id1} ({e1['text'][:20]})",
                    "neighbor": f"{enu_id2} ({e2['text'][:20]})",
                    "mechanism": "INDEPENDENT_RELATIVE_MOVEMENT",
                    "relationship": "Relative Movement (Δdx, Δdy)",
                    "before": "Synchronized (0px rel)",
                    "after": f"Displaced ({rel_displacement:.1f}px rel)",
                    "delta": f"{rel_displacement:.1f}px delta",
                    "evidence_strength": round(strength, 2),
                    "evidence_type": "INDEPENDENT_MOVEMENT"
                })
                
    # Sort evidence records by strength descending
    ranked_evidence_records.sort(key=lambda r: r["evidence_strength"], reverse=True)
    
    # Deduplicate redundant pairs
    seen = set()
    unique_ranked = []
    for r in ranked_evidence_records:
        pair_key = (r["mechanism"], r["element"], r["neighbor"])
        if pair_key not in seen:
            seen.add(pair_key)
            unique_ranked.append(r)
            
    # Diagnostic summary counts for this case
    has_clear_independent_displacement = any(r["evidence_type"] in ["COLUMN_MISALIGNMENT", "INDEPENDENT_MOVEMENT"] for r in unique_ranked)
    has_newly_created_intersection = any(r["evidence_type"] in ["OVERLAP_INTERSECTION", "GAP_COLLAPSE"] for r in unique_ranked)
    
    return {
        "case_id": case_id,
        "product": product,
        "folder": folder,
        "lang": lang,
        "gt_category": gt_category,
        "total_relationships_evaluated": len(matched_pairs),
        "median_global_shift": {"dx": median_dx, "dy": median_dy},
        "has_clear_independent_displacement": has_clear_independent_displacement,
        "has_newly_created_intersection": has_newly_created_intersection,
        "ranked_evidence": unique_ranked[:8] # Top 8 strongest physical signals
    }

def main():
    with open(POC_JSON_PATH, 'r', encoding='utf-8') as f:
        poc_data = json.load(f)
        
    print(f"Loaded {len(poc_data)} POC benchmark cases from {POC_JSON_PATH.resolve()}.", flush=True)
    
    all_case_summaries = []
    
    misalign_cases_evaluated = 0
    misalign_with_displacement = 0
    
    overlap_cases_evaluated = 0
    overlap_with_intersections = 0
    
    for case in poc_data:
        res = analyze_case_evidence(case)
        all_case_summaries.append(res)
        
        gt = res["gt_category"]
        if gt == "Misalignment":
            misalign_cases_evaluated += 1
            if res["has_clear_independent_displacement"]:
                misalign_with_displacement += 1
        elif gt == "Overlapping":
            overlap_cases_evaluated += 1
            if res["has_newly_created_intersection"]:
                overlap_with_intersections += 1
                
    # Generate Markdown and JSON output
    with open(OUTPUT_REPORT_JSON, 'w', encoding='utf-8') as f:
        json.dump(all_case_summaries, f, indent=2)
    print(f"Saved evidence analysis data to {OUTPUT_REPORT_JSON.resolve()}", flush=True)
    
    print("\n" + "="*80)
    print("STRUCTURED RELATIONSHIP EVIDENCE ANALYSIS (10 CASES)")
    print("="*80)
    
    for cs in all_case_summaries:
        print(f"\nCase #{cs['case_id']}: {cs['product']}/{cs['folder']} ({cs['lang']}) | GT: {cs['gt_category']}")
        print(f"  * Median Screen Shift: dx={cs['median_global_shift']['dx']:+.1f}px, dy={cs['median_global_shift']['dy']:+.1f}px")
        print(f"  * Top Ranked Evidence Changes ({len(cs['ranked_evidence'])} found):")
        if not cs['ranked_evidence']:
            print("    (No significant physical relationship delta detected)")
        else:
            print(f"    {'Element':25s} | {'Neighbor':25s} | {'Mechanism':28s} | {'Before':15s} | {'After':18s} | {'Delta':18s} | {'Strength'}")
            print("    " + "-"*130)
            for re in cs['ranked_evidence'][:5]:
                print(f"    {re['element'][:25]:25s} | {re['neighbor'][:25]:25s} | {re['mechanism'][:28]:28s} | {re['before'][:15]:15s} | {re['after'][:18]:18s} | {re['delta'][:18]:18s} | {re['evidence_strength']:>8.1f}")
                
    print("\n" + "="*80)
    print("SUMMARY ASSESSMENT")
    print("="*80)
    print(f"Misalignment Cases (N={misalign_cases_evaluated}): {misalign_with_displacement}/{misalign_cases_evaluated} show clear independent positional displacement ({misalign_with_displacement/max(1,misalign_cases_evaluated)*100:.1f}%)")
    print(f"Overlapping Cases (N={overlap_cases_evaluated}):  {overlap_with_intersections}/{overlap_cases_evaluated} show newly created bounding-box intersections / collapsed gaps ({overlap_with_intersections/max(1,overlap_cases_evaluated)*100:.1f}%)")

if __name__ == '__main__':
    main()
