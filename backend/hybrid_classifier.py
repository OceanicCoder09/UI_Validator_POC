import os
import sys
import json
import pathlib
import collections
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

EXCEL_PATH = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize/Screenshot data list from Welocalize.xlsx')
BASE_DATA_ROOT = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize')
EMBEDDINGS_CACHE = pathlib.Path('backend/vit_embeddings_cache.npz')
CHANGE_REGIONS_JSON = pathlib.Path('backend/change_regions.json')
EVAL_RESULTS_JSON = pathlib.Path('backend/eval_results.json')
OUTPUT_HYBRID_JSON = pathlib.Path('backend/hybrid_classifier_results.json')

TARGET_CLASSES = [
    "Truncation",
    "Untranslation",
    "Misalignment",
    "Overlapping",
    "Repeated hotkey"
]

def load_case_mappings():
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
        
        if not en_files or not loc_files:
            continue
            
        case_idx += 1
        records.append({
            "case_id": case_idx,
            "product": product,
            "folder": folder,
            "lang": lang,
            "gt_category": gt_cat
        })
    return records

def extract_structured_features(change_regions_data, eval_results_data, num_cases=114):
    """
    Extracts numerical structured evidence features for each case:
    1. position shift X / Y
    2. width / height changes & max dimensions
    3. overlap / intersection measurements
    4. text length / token count changes & word indicators
    5. overflow / ellipsis indicators
    6. changed-pixel ratio / area
    7. number of meaningful change regions
    8. spatial spread of changes (std dev of coordinates)
    """
    features = []
    
    # Index change_regions by case_id
    cr_by_case = {c["case_id"]: c["regions"] for c in change_regions_data}
    # Index eval_results by case index
    ev_by_case = {i+1: ev for i, ev in enumerate(eval_results_data)}
    
    for case_id in range(1, num_cases + 1):
        regs = cr_by_case.get(case_id, [])
        ev_item = ev_by_case.get(case_id, {})
        candidates = ev_item.get("candidates", [])
        
        # 1. Region Count & Area Stats
        num_regions = len(regs)
        areas = [r.get("area", 0) for r in regs]
        total_area = sum(areas)
        max_area = max(areas, default=0)
        mean_diff_score = np.mean([r.get("difference_score", 0) for r in regs]) if regs else 0.0
        max_diff_score = max([r.get("difference_score", 0) for r in regs], default=0.0)
        
        # 2. Spatial Spread (Std Dev of X and Y)
        xs = [r.get("coordinates", {}).get("x", 0) for r in regs]
        ys = [r.get("coordinates", {}).get("y", 0) for r in regs]
        widths = [r.get("coordinates", {}).get("width", 0) for r in regs]
        heights = [r.get("coordinates", {}).get("height", 0) for r in regs]
        
        x_spread = float(np.std(xs)) if len(xs) > 1 else 0.0
        y_spread = float(np.std(ys)) if len(ys) > 1 else 0.0
        max_width = max(widths, default=0)
        max_height = max(heights, default=0)
        aspect_ratio_mean = float(np.mean([w / max(1, h) for w, h in zip(widths, heights)])) if widths else 1.0
        
        # 3. Position Shift measurements from candidates
        shifts = []
        for cand in candidates:
            ev = cand.get("evidence", {})
            if "position_shift_x" in ev:
                shifts.append(ev["position_shift_x"])
        max_shift_x = max(shifts, default=0)
        mean_shift_x = float(np.mean(shifts)) if shifts else 0.0
        
        # 4. Overlap measurements from candidates
        overlaps = []
        for cand in candidates:
            ev = cand.get("evidence", {})
            if "overlap_pixels" in ev:
                overlaps.append(ev["overlap_pixels"])
        max_overlap = max(overlaps, default=0)
        num_overlapping_nodes = len(overlaps)
        
        # 5. Overflow / Ellipsis measurements from candidates
        overflows = []
        has_ellipsis_any = 0
        for cand in candidates:
            ev = cand.get("evidence", {})
            if "overflow_px" in ev:
                overflows.append(ev["overflow_px"])
            if ev.get("has_ellipsis", False):
                has_ellipsis_any = 1
        max_overflow = max(overflows, default=0)
        
        # 6. Text count & untranslation indicators from candidates
        untrans_words_count = 0
        hotkey_conflict_count = 0
        control_delta_count = 0
        
        for cand in candidates:
            cat = cand.get("category", "")
            ev = cand.get("evidence", {})
            if cat == "UNTRANSLATION":
                untrans_words_count += len(ev.get("untranslated_words", []))
            elif cat == "HOTKEY_DEFECT":
                hotkey_conflict_count += 1
            elif cat == "MISC":
                control_delta_count += ev.get("control_count_delta", 1)
                
        feat_vec = [
            float(num_regions),
            float(total_area),
            float(max_area),
            float(mean_diff_score),
            float(max_diff_score),
            float(x_spread),
            float(y_spread),
            float(max_width),
            float(max_height),
            float(aspect_ratio_mean),
            float(max_shift_x),
            float(mean_shift_x),
            float(max_overlap),
            float(num_overlapping_nodes),
            float(max_overflow),
            float(has_ellipsis_any),
            float(untrans_words_count),
            float(hotkey_conflict_count),
            float(control_delta_count)
        ]
        features.append(feat_vec)
        
    feats_arr = np.array(features, dtype=np.float32)
    # Standardize structured features (zero mean, unit variance)
    mean = np.mean(feats_arr, axis=0, keepdims=True)
    std = np.std(feats_arr, axis=0, keepdims=True)
    std[std == 0] = 1.0
    normalized_feats = (feats_arr - mean) / std
    return normalized_feats

class MulticlassLogisticRegression:
    def __init__(self, num_features, num_classes, lr=0.03, weight_decay=1e-2, epochs=250):
        self.num_features = num_features
        self.num_classes = num_classes
        self.lr = lr
        self.weight_decay = weight_decay
        self.epochs = epochs
        
    def fit(self, X_train, y_train):
        X_t = torch.tensor(X_train, dtype=torch.float32)
        y_t = torch.tensor(y_train, dtype=torch.long)
        
        linear = nn.Linear(self.num_features, self.num_classes)
        optimizer = torch.optim.Adam(linear.parameters(), lr=self.lr, weight_decay=self.weight_decay)
        criterion = nn.CrossEntropyLoss()
        
        linear.train()
        for epoch in range(self.epochs):
            optimizer.zero_grad()
            logits = linear(X_t)
            loss = criterion(logits, y_t)
            loss.backward()
            optimizer.step()
            
        self.model = linear
        self.model.eval()

    def predict_proba(self, X_val):
        X_t = torch.tensor(X_val, dtype=torch.float32)
        with torch.no_grad():
            logits = self.model(X_t)
            probs = torch.softmax(logits, dim=1).numpy()
        return probs

def main():
    records = load_case_mappings()
    
    # 1. Load cached ViT embeddings
    vit_data = np.load(EMBEDDINGS_CACHE, allow_pickle=True)
    X_vit = vit_data['X']  # (114, 3072)
    
    # 2. Load Change Regions & Eval results
    with open(CHANGE_REGIONS_JSON, 'r', encoding='utf-8') as f:
        cr_data = json.load(f)
    with open(EVAL_RESULTS_JSON, 'r', encoding='utf-8') as f:
        ev_data = json.load(f)
        
    # 3. Extract and normalize structured features
    X_struct = extract_structured_features(cr_data, ev_data, num_cases=len(records))  # (114, 19)
    
    # 4. Fuse ViT embeddings + structured features
    X_fused = np.concatenate([X_vit, X_struct], axis=1)  # (114, 3091)
    
    # 5. Filter for the 5 sufficiently represented categories
    filtered_indices = []
    filtered_records = []
    y_filtered_labels = []
    
    for i, r in enumerate(records):
        gt = r['gt_category']
        if gt in TARGET_CLASSES:
            filtered_indices.append(i)
            filtered_records.append(r)
            y_filtered_labels.append(gt)
            
    classes = sorted(TARGET_CLASSES)
    y_filtered = np.array([classes.index(lbl) for lbl in y_filtered_labels], dtype=np.int64)
    
    X_vit_subset = X_vit[filtered_indices]
    X_hybrid_subset = X_fused[filtered_indices]
    num_samples = len(filtered_indices)
    num_classes = len(classes)
    
    print("="*75)
    print("EXPERIMENT 2: HYBRID (ViT + STRUCTURED EVIDENCE) CLASSIFIER")
    print("="*75)
    print(f"Target Classes (5): {classes}")
    print(f"Total Filtered Sample Count: {num_samples} (from 114 total benchmark cases)")
    print(f"Features: ViT (3,072) + Structured Evidence (19) = {X_hybrid_subset.shape[1]} dimensions")
    print(f"Evaluation: Leave-One-Out Cross-Validation (LOOCV)")
    print("="*75)

    # -------------------------------------------------------------
    # 1. RUN SUBSET ViT-ONLY BASELINE (for direct fair comparison)
    # -------------------------------------------------------------
    vit_top1_correct = 0
    vit_top2_correct = 0
    vit_preds = []
    
    for i in range(num_samples):
        train_idx = [j for j in range(num_samples) if j != i]
        test_idx = [i]
        
        clf = MulticlassLogisticRegression(num_features=X_vit_subset.shape[1], num_classes=num_classes)
        clf.fit(X_vit_subset[train_idx], y_filtered[train_idx])
        
        probs = clf.predict_proba(X_vit_subset[test_idx])[0]
        top1_idx = int(np.argmax(probs))
        top2_idx = np.argsort(probs)[-2:][::-1]
        
        gt_idx = int(y_filtered[i])
        if top1_idx == gt_idx: vit_top1_correct += 1
        if gt_idx in top2_idx: vit_top2_correct += 1
        vit_preds.append(top1_idx)

    # -------------------------------------------------------------
    # 2. RUN HYBRID (ViT + Structured Features) CLASSIFIER
    # -------------------------------------------------------------
    hybrid_top1_correct = 0
    hybrid_top2_correct = 0
    hybrid_preds = []
    pred_details = []
    
    for i in range(num_samples):
        train_idx = [j for j in range(num_samples) if j != i]
        test_idx = [i]
        
        clf = MulticlassLogisticRegression(num_features=X_hybrid_subset.shape[1], num_classes=num_classes)
        clf.fit(X_hybrid_subset[train_idx], y_filtered[train_idx])
        
        probs = clf.predict_proba(X_hybrid_subset[test_idx])[0]
        top1_idx = int(np.argmax(probs))
        top2_idx = np.argsort(probs)[-2:][::-1]
        
        gt_idx = int(y_filtered[i])
        is_exact = (top1_idx == gt_idx)
        is_top2 = (gt_idx in top2_idx)
        
        if is_exact: hybrid_top1_correct += 1
        if is_top2: hybrid_top2_correct += 1
        hybrid_preds.append(top1_idx)
        
        r = filtered_records[i]
        pred_details.append({
            "case_id": r["case_id"],
            "product": r["product"],
            "folder": r["folder"],
            "lang": r["lang"],
            "gt_category": classes[gt_idx],
            "predicted_category": classes[top1_idx],
            "confidence": float(round(probs[top1_idx], 4)),
            "top2_predicted": [classes[idx] for idx in top2_idx],
            "exact_match": bool(is_exact),
            "top2_match": bool(is_top2)
        })

    # Metrics
    vit_exact_acc = vit_top1_correct / num_samples * 100
    vit_top2_acc = vit_top2_correct / num_samples * 100
    
    hybrid_exact_acc = hybrid_top1_correct / num_samples * 100
    hybrid_top2_acc = hybrid_top2_correct / num_samples * 100

    # Confusion Matrix for Hybrid
    conf_matrix = np.zeros((num_classes, num_classes), dtype=int)
    for true_idx, pred_idx in zip(y_filtered, hybrid_preds):
        conf_matrix[true_idx, pred_idx] += 1
        
    per_class_results = []
    for c_idx, c_name in enumerate(classes):
        total_gt = np.sum(conf_matrix[c_idx, :])
        correct = conf_matrix[c_idx, c_idx]
        total_pred = np.sum(conf_matrix[:, c_idx])
        recall = (correct / total_gt * 100) if total_gt > 0 else 0.0
        precision = (correct / total_pred * 100) if total_pred > 0 else 0.0
        per_class_results.append({
            "class_name": c_name,
            "total_gt": int(total_gt),
            "correct": int(correct),
            "recall": float(round(recall, 2)),
            "precision": float(round(precision, 2))
        })

    print(f"\n=======================================================")
    print(f"COMPARISON SUMMARY (5 Core Categories, N = {num_samples})")
    print(f"=======================================================")
    print(f"ViT-Only (16-class Global Baseline) : 43/114 (37.72%) Top-1 | 64/114 (56.14%) Top-2")
    print(f"ViT-Only (5-class Subset)          : {vit_top1_correct}/{num_samples} ({vit_exact_acc:.2f}%) Top-1 | {vit_top2_correct}/{num_samples} ({vit_top2_acc:.2f}%) Top-2")
    print(f"Hybrid (ViT + Structured Evidence) : {hybrid_top1_correct}/{num_samples} ({hybrid_exact_acc:.2f}%) Top-1 | {hybrid_top2_correct}/{num_samples} ({hybrid_top2_acc:.2f}%) Top-2")
    print(f"Delta Improvement (Exact Accuracy) : +{hybrid_exact_acc - vit_exact_acc:.2f}% (from {vit_exact_acc:.2f}% to {hybrid_exact_acc:.2f}%)")

    print("\n" + "="*75)
    print("HYBRID PER-CLASS PERFORMANCE")
    print("="*75)
    print(f"{'Class Name':25s} | {'Total GT':9s} | {'Correct':8s} | {'Recall':8s} | {'Precision':10s}")
    print("-"*75)
    for p in sorted(per_class_results, key=lambda x: x['total_gt'], reverse=True):
        print(f"{p['class_name']:25s} | {p['total_gt']:9d} | {p['correct']:8d} | {p['recall']:7.1f}% | {p['precision']:9.1f}%")

    print("\n" + "="*75)
    print("CONFUSION MATRIX (Row = True GT, Col = Predicted)")
    print("="*75)
    header = f"{'True GT / Pred':25s} | " + " | ".join(f"{c[:8]:8s}" for c in classes)
    print(header)
    print("-" * len(header))
    for i, r_name in enumerate(classes):
        row_str = f"{r_name:25s} | " + " | ".join(f"{conf_matrix[i, j]:8d}" for j in range(num_classes))
        print(row_str)

    # Save to JSON
    output_payload = {
        "summary": {
            "total_samples": num_samples,
            "classes": classes,
            "vit_only_5class_accuracy": round(vit_exact_acc, 2),
            "vit_only_5class_top2": round(vit_top2_acc, 2),
            "hybrid_accuracy": round(hybrid_exact_acc, 2),
            "hybrid_top2": round(hybrid_top2_acc, 2),
            "improvement_pct": round(hybrid_exact_acc - vit_exact_acc, 2)
        },
        "per_class_results": per_class_results,
        "confusion_matrix": conf_matrix.tolist(),
        "predictions": pred_details
    }
    with open(OUTPUT_HYBRID_JSON, 'w', encoding='utf-8') as f:
        json.dump(output_payload, f, indent=2)
    print(f"\nSaved hybrid classification report to {OUTPUT_HYBRID_JSON.resolve()}", flush=True)

if __name__ == '__main__':
    main()
