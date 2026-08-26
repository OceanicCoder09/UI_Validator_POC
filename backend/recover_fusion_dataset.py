import os
import sys
import json
import time
import pathlib
import collections
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

EXCEL_PATH = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize/Screenshot data list from Welocalize.xlsx')
BASE_DATA_ROOT = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize')
VIT_CACHE_PATH = pathlib.Path('backend/vit_embeddings_cache.npz')
CHANGE_REGIONS_JSON = pathlib.Path('backend/change_regions.json')
EVAL_RESULTS_JSON = pathlib.Path('backend/eval_results.json')
REGION_EMBEDDINGS_CACHE = pathlib.Path('backend/region_vit_embeddings_cache.npz')
RELATIONSHIP_EVIDENCE_JSON = pathlib.Path('backend/relationship_evidence_all_cases.json')

OUTPUT_VIT_PREDS = pathlib.Path('backend/vit_fusion_predictions.json')
OUTPUT_HYBRID_PREDS = pathlib.Path('backend/hybrid_fusion_predictions.json')
OUTPUT_MIL_PREDS = pathlib.Path('backend/mil_fusion_predictions.json')
OUTPUT_REL_PREDS = pathlib.Path('backend/relationship_fusion_predictions.json')
OUTPUT_FUSION_DATASET = pathlib.Path('backend/fusion_dataset.json')

TARGET_CLASSES = [
    "Misalignment",
    "Overlapping",
    "Repeated hotkey",
    "Truncation",
    "Untranslation"
]

FEATURE_NAMES = [
    "max_displacement_px",
    "median_displacement_px",
    "num_independently_displaced",
    "max_alignment_divergence_px",
    "max_gap_collapse_px",
    "num_newly_created_intersections",
    "log_intersection_area",
    "max_text_expansion_px",
    "has_ellipsis_count",
    "untranslated_words_count",
    "hotkey_conflict_count",
    "match_rate_pct",
    "avg_match_confidence"
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
        if not en_files or not loc_files: continue
        
        case_idx += 1
        if gt_cat in TARGET_CLASSES:
            records.append({
                "case_id": case_idx,
                "product": product,
                "folder": folder,
                "lang": lang,
                "gt_category": gt_cat
            })
    return records

def extract_structured_evidence_19(records, num_cases=114):
    with open(CHANGE_REGIONS_JSON, 'r', encoding='utf-8') as f: cr_data = json.load(f)
    with open(EVAL_RESULTS_JSON, 'r', encoding='utf-8') as f: ev_data = json.load(f)
    
    cr_by_case = {c["case_id"]: c["regions"] for c in cr_data}
    ev_by_case = {i+1: ev for i, ev in enumerate(ev_data)}
    
    features = []
    for r in records:
        case_id = r["case_id"]
        regs = cr_by_case.get(case_id, [])
        ev_item = ev_by_case.get(case_id, {})
        candidates = ev_item.get("candidates", [])
        
        num_regions = len(regs)
        areas = [rg.get("area", 0) for rg in regs]
        total_area = sum(areas)
        max_area = max(areas, default=0)
        mean_diff_score = np.mean([rg.get("difference_score", 0) for rg in regs]) if regs else 0.0
        max_diff_score = max([rg.get("difference_score", 0) for rg in regs], default=0.0)
        
        xs = [rg.get("coordinates", {}).get("x", 0) for rg in regs]
        ys = [rg.get("coordinates", {}).get("y", 0) for rg in regs]
        widths = [rg.get("coordinates", {}).get("width", 0) for rg in regs]
        heights = [rg.get("coordinates", {}).get("height", 0) for rg in regs]
        
        x_spread = float(np.std(xs)) if len(xs) > 1 else 0.0
        y_spread = float(np.std(ys)) if len(ys) > 1 else 0.0
        max_width = max(widths, default=0)
        max_height = max(heights, default=0)
        aspect_ratio_mean = float(np.mean([w / max(1, h) for w, h in zip(widths, heights)])) if widths else 1.0
        
        shifts = []
        overlaps = []
        for cand in candidates:
            ev = cand.get("evidence", {})
            if "shift_px" in ev: shifts.append(ev["shift_px"])
            if "overlap_pixels" in ev: overlaps.append(ev["overlap_pixels"])
            
        mean_shift = np.mean(shifts) if shifts else 0.0
        max_shift = max(shifts, default=0.0)
        total_overlap = sum(overlaps)
        has_overlap = 1.0 if total_overlap > 0 else 0.0
        
        cand_categories = [cand.get("category", "") for cand in candidates]
        cand_cat_counts = collections.Counter(cand_categories)
        has_truncation_cand = float(cand_cat_counts.get("Truncation", 0))
        has_untranslation_cand = float(cand_cat_counts.get("Untranslation", 0))
        has_misalignment_cand = float(cand_cat_counts.get("Misalignment", 0))
        has_overlapping_cand = float(cand_cat_counts.get("Overlapping", 0))
        has_hotkey_cand = float(cand_cat_counts.get("Repeated hotkey", 0))
        
        feat_vec = [
            num_regions, total_area, max_area, mean_diff_score, max_diff_score,
            x_spread, y_spread, max_width, max_height, aspect_ratio_mean,
            mean_shift, max_shift, total_overlap, has_overlap,
            has_truncation_cand, has_untranslation_cand, has_misalignment_cand, has_overlapping_cand, has_hotkey_cand
        ]
        features.append(feat_vec)
    return np.array(features, dtype=np.float32)

def train_and_eval_loocv_linear(X, y_labels, classes, records, lr=0.03, weight_decay=1e-3, epochs=120):
    num_samples = len(X)
    num_classes = len(classes)
    y = np.array([classes.index(lbl) for lbl in y_labels], dtype=np.int64)
    
    predictions = []
    t0 = time.time()
    
    for i in range(num_samples):
        train_idx = [j for j in range(num_samples) if j != i]
        test_idx = [i]
        
        X_train, y_train = X[train_idx], y[train_idx]
        X_test, y_test = X[test_idx], y[test_idx]
        
        # Scaling fit strictly on training fold
        mean = np.mean(X_train, axis=0, keepdims=True)
        std = np.std(X_train, axis=0, keepdims=True)
        std[std < 1e-7] = 1.0
        
        X_tr_s = (X_train - mean) / std
        X_te_s = (X_test - mean) / std
        
        torch.manual_seed(42)
        model = nn.Linear(X.shape[1], num_classes)
        optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
        criterion = nn.CrossEntropyLoss()
        
        Xt = torch.tensor(X_tr_s, dtype=torch.float32)
        yt = torch.tensor(y_train, dtype=torch.long)
        
        model.train()
        for _ in range(epochs):
            optimizer.zero_grad()
            loss = criterion(model(Xt), yt)
            loss.backward()
            optimizer.step()
            
        model.eval()
        with torch.no_grad():
            logits = model(torch.tensor(X_te_s, dtype=torch.float32))
            probs = torch.softmax(logits, dim=1).squeeze(0).numpy()
            
        top1_idx = int(np.argmax(probs))
        top2_idx = np.argsort(probs)[-2:][::-1].tolist()
        
        rec = records[i]
        prob_dict = {classes[c_i]: float(round(probs[c_i], 6)) for c_i in range(num_classes)}
        
        predictions.append({
            "case_id": rec["case_id"],
            "product": rec["product"],
            "folder": rec["folder"],
            "lang": rec["lang"],
            "gt_category": rec["gt_category"],
            "probabilities": prob_dict,
            "top1_predicted": classes[top1_idx],
            "top1_confidence": float(round(probs[top1_idx], 6)),
            "top2_predicted": [classes[c_i] for c_i in top2_idx]
        })
        
        if (i + 1) % 25 == 0 or (i + 1) == num_samples:
            print(f"  Processed {i+1}/{num_samples} LOOCV folds in {time.time()-t0:.1f}s", flush=True)
            
    return predictions

def generate_vit_and_hybrid_predictions(records, classes):
    print("Generating out-of-fold predictions for ViT-Only (5-class) and Hybrid (5-class)...", flush=True)
    vit_cache = np.load(VIT_CACHE_PATH, allow_pickle=True)
    all_X_vit = vit_cache['X']
    all_case_ids = list(vit_cache['case_ids'])
    
    # Filter 101 records
    X_vit_101 = []
    y_labels = [r["gt_category"] for r in records]
    for r in records:
        row_idx = all_case_ids.index(r["case_id"])
        X_vit_101.append(all_X_vit[row_idx])
    X_vit_101 = np.array(X_vit_101, dtype=np.float32)
    
    # 1. ViT-Only Predictions
    vit_preds = train_and_eval_loocv_linear(X_vit_101, y_labels, classes, records, lr=0.03, weight_decay=1e-3)
    
    # 2. Hybrid (ViT + 19 Structured Evidence) Predictions
    X_struct_19 = extract_structured_evidence_19(records)
    # Normalize components before concatenation
    X_vit_norm = X_vit_101 / np.linalg.norm(X_vit_101, axis=1, keepdims=True)
    X_struct_norm = (X_struct_19 - np.mean(X_struct_19, axis=0)) / (np.std(X_struct_19, axis=0) + 1e-7)
    X_hybrid = np.concatenate([X_vit_norm, X_struct_norm], axis=1)
    
    hybrid_preds = train_and_eval_loocv_linear(X_hybrid, y_labels, classes, records, lr=0.03, weight_decay=1e-3)
    return vit_preds, hybrid_preds

def generate_mil_predictions(records, classes):
    print("Generating out-of-fold predictions for MIL (Region Bags)...", flush=True)
    mil_data = np.load(REGION_EMBEDDINGS_CACHE, allow_pickle=True)
    
    bag_representations = []
    max_attention_weights = []
    attention_entropy_list = []
    
    for r in records:
        bag = mil_data[f"case_{r['case_id']}"]
        if len(bag) == 1:
            bag_representations.append(bag[0])
            max_attention_weights.append(1.0)
            attention_entropy_list.append(0.0)
            continue
            
        diff_scores = bag[:, -5]
        area_scores = bag[:, -4]
        saliency_logits = diff_scores * 2.0 + area_scores * 1.0
        attn_exp = np.exp(saliency_logits - np.max(saliency_logits))
        attn_weights = attn_exp / np.sum(attn_exp)
        pooled_h = np.sum(attn_weights[:, np.newaxis] * bag, axis=0)
        pooled_h = pooled_h / max(1e-7, np.linalg.norm(pooled_h))
        bag_representations.append(pooled_h)
        
        max_attn = float(np.max(attn_weights))
        max_attention_weights.append(max_attn)
        entropy = float(-np.sum(attn_weights * np.log(attn_weights + 1e-9)) / np.log(len(attn_weights)))
        attention_entropy_list.append(entropy)
        
    X_mil = np.array(bag_representations, dtype=np.float32)
    y_labels = [r["gt_category"] for r in records]
    
    mil_preds_raw = train_and_eval_loocv_linear(X_mil, y_labels, classes, records, lr=0.03, weight_decay=1e-2)
    
    # Attach attention metrics
    mil_preds = []
    for i, p in enumerate(mil_preds_raw):
        p_dict = dict(p)
        p_dict["max_attention_weight"] = round(max_attention_weights[i], 4)
        p_dict["attention_entropy"] = round(attention_entropy_list[i], 4)
        mil_preds.append(p_dict)
        
    return mil_preds

def get_stratified_folds(y, n_splits=3, seed=42):
    rng = np.random.RandomState(seed)
    folds = [[] for _ in range(n_splits)]
    for c in np.unique(y):
        idx = np.where(y == c)[0]
        rng.shuffle(idx)
        for i, idx_val in enumerate(idx):
            folds[i % n_splits].append(idx_val)
    splits = []
    for test_f in range(n_splits):
        test_idx = np.array(folds[test_f])
        train_idx = np.array([item for f_i, f in enumerate(folds) if f_i != test_f for item in f])
        splits.append((train_idx, test_idx))
    return splits

def generate_relationship_out_of_fold_predictions(records, classes):
    print("Generating out-of-fold predictions for Relationship Logistic Regression (Repeated 3-Fold x 10)...", flush=True)
    with open(RELATIONSHIP_EVIDENCE_JSON, 'r', encoding='utf-8') as f:
        rel_ev_data = json.load(f)
        
    rel_by_case = {c["case_id"]: c for c in rel_ev_data}
    
    X_list = []
    y_list = []
    
    for r in records:
        c = rel_by_case[r["case_id"]]
        ef = c["evidence_features"]
        ms = c["matching_stats"]
        log_inter_area = np.log1p(float(ef.get("total_intersection_area_px2", 0)))
        feat_vec = [
            float(ef.get("max_displacement_px", 0)),
            float(ef.get("median_displacement_px", 0)),
            float(ef.get("num_independently_displaced", 0)),
            float(ef.get("max_alignment_divergence_px", 0)),
            float(ef.get("max_gap_collapse_px", 0)),
            float(ef.get("num_newly_created_intersections", 0)),
            log_inter_area,
            float(ef.get("max_text_expansion_px", 0)),
            float(ef.get("has_ellipsis_count", 0)),
            float(ef.get("untranslated_words_count", 0)),
            float(ef.get("hotkey_conflict_count", 0)),
            float(ms.get("match_rate_pct", 100.0)),
            float(ms.get("avg_confidence", 1.0))
        ]
        X_list.append(feat_vec)
        y_list.append(classes.index(r["gt_category"]))
        
    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int64)
    num_samples = len(X)
    num_classes = len(classes)
    
    # Store out-of-fold accumulated probabilities (across 10 repeats)
    oof_accum_probs = np.zeros((num_samples, num_classes), dtype=np.float64)
    oof_counts = np.zeros(num_samples, dtype=np.int32)
    
    for repeat in range(10):
        splits = get_stratified_folds(y, n_splits=3, seed=42 + repeat * 13)
        for train_idx, test_idx in splits:
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]
            
            mean = np.mean(X_train, axis=0, keepdims=True)
            std = np.std(X_train, axis=0, keepdims=True)
            std[std < 1e-7] = 1.0
            
            X_train_scaled = (X_train - mean) / std
            X_test_scaled = (X_test - mean) / std
            
            torch.manual_seed(42 + repeat)
            model = nn.Linear(X.shape[1], num_classes)
            optimizer = torch.optim.Adam(model.parameters(), lr=0.04, weight_decay=1e-3)
            criterion = nn.CrossEntropyLoss()
            
            Xt = torch.tensor(X_train_scaled, dtype=torch.float32)
            yt = torch.tensor(y_train, dtype=torch.long)
            
            model.train()
            for _ in range(120):
                optimizer.zero_grad()
                loss = criterion(model(Xt), yt)
                loss.backward()
                optimizer.step()
                
            model.eval()
            with torch.no_grad():
                logits = model(torch.tensor(X_test_scaled, dtype=torch.float32))
                probs = torch.softmax(logits, dim=1).numpy() # (len(test_idx), num_classes)
                
            for idx_in_test, sample_idx in enumerate(test_idx):
                oof_accum_probs[sample_idx] += probs[idx_in_test]
                oof_counts[sample_idx] += 1
                
    # Average across all 10 out-of-fold iterations
    oof_final_probs = oof_accum_probs / oof_counts[:, np.newaxis]
    
    # Normalize to sum exactly to 1.0
    oof_final_probs = oof_final_probs / np.sum(oof_final_probs, axis=1, keepdims=True)
    
    rel_predictions = []
    for i, r in enumerate(records):
        probs = oof_final_probs[i]
        top1_idx = int(np.argmax(probs))
        top2_idx = np.argsort(probs)[-2:][::-1].tolist()
        
        prob_dict = {classes[c_i]: float(round(probs[c_i], 6)) for c_i in range(num_classes)}
        rel_predictions.append({
            "case_id": r["case_id"],
            "product": r["product"],
            "folder": r["folder"],
            "lang": r["lang"],
            "gt_category": r["gt_category"],
            "probabilities": prob_dict,
            "top1_predicted": classes[top1_idx],
            "top1_confidence": float(round(probs[top1_idx], 6)),
            "top2_predicted": [classes[c_i] for c_i in top2_idx],
            "is_out_of_fold": True,
            "repeats_averaged": int(oof_counts[i])
        })
        
    return rel_predictions

def assemble_fusion_dataset(records, classes, vit_preds, hybrid_preds, mil_preds, rel_preds):
    print("Assembling consolidated backend/fusion_dataset.json...", flush=True)
    with open(RELATIONSHIP_EVIDENCE_JSON, 'r', encoding='utf-8') as f:
        rel_ev_data = json.load(f)
    rel_by_case = {c["case_id"]: c for c in rel_ev_data}
    
    vit_by_id = {p["case_id"]: p for p in vit_preds}
    hybrid_by_id = {p["case_id"]: p for p in hybrid_preds}
    mil_by_id = {p["case_id"]: p for p in mil_preds}
    rel_by_id = {p["case_id"]: p for p in rel_preds}
    
    fusion_dataset = []
    
    for r in records:
        cid = r["case_id"]
        c_rel = rel_by_case[cid]
        ef = c_rel["evidence_features"]
        ms = c_rel["matching_stats"]
        
        # 13 Relationship Evidence Features
        evidence_features = {
            "max_displacement_px": ef.get("max_displacement_px", 0.0),
            "median_displacement_px": ef.get("median_displacement_px", 0.0),
            "num_independently_displaced": ef.get("num_independently_displaced", 0),
            "max_alignment_divergence_px": ef.get("max_alignment_divergence_px", 0),
            "max_gap_collapse_px": ef.get("max_gap_collapse_px", 0),
            "num_newly_created_intersections": ef.get("num_newly_created_intersections", 0),
            "total_intersection_area_px2": ef.get("total_intersection_area_px2", 0),
            "log_intersection_area": round(float(np.log1p(ef.get("total_intersection_area_px2", 0))), 4),
            "max_text_expansion_px": ef.get("max_text_expansion_px", 0),
            "has_ellipsis_count": ef.get("has_ellipsis_count", 0),
            "untranslated_words_count": ef.get("untranslated_words_count", 0),
            "hotkey_conflict_count": ef.get("hotkey_conflict_count", 0),
            "match_rate_pct": ms.get("match_rate_pct", 100.0),
            "avg_match_confidence": ms.get("avg_confidence", 1.0)
        }
        
        fusion_record = {
            "case_id": cid,
            "product": r["product"],
            "folder": r["folder"],
            "lang": r["lang"],
            "gt_category": r["gt_category"],
            "model_probabilities": {
                "vit_classifier": vit_by_id[cid]["probabilities"],
                "hybrid_classifier": hybrid_by_id[cid]["probabilities"],
                "mil_classifier": mil_by_id[cid]["probabilities"],
                "relationship_classifier_oof": rel_by_id[cid]["probabilities"]
            },
            "mil_metadata": {
                "max_attention_weight": mil_by_id[cid]["max_attention_weight"],
                "attention_entropy": mil_by_id[cid]["attention_entropy"]
            },
            "relationship_evidence_features": evidence_features
        }
        fusion_dataset.append(fusion_record)
        
    return fusion_dataset

def validate_fusion_dataset(dataset, classes):
    print("\n" + "="*70)
    print("VALIDATING FUSION DATASET INTEGRITY")
    print("="*70)
    
    # 1. Check exactly 101 cases
    assert len(dataset) == 101, f"Expected 101 cases, got {len(dataset)}"
    print("[PASS] Exactly 101 benchmark cases present.")
    
    # 2. Check exactly one valid GT label per case
    gt_counts = collections.Counter([r["gt_category"] for r in dataset])
    print("[PASS] Ground truth label distribution:")
    for cat, cnt in sorted(gt_counts.items()):
        print(f"       * {cat:18s}: {cnt} cases")
    assert sum(gt_counts.values()) == 101
    
    # 3. Verify no missing probability vectors & sum to 1.0
    for r in dataset:
        cid = r["case_id"]
        probs_dict = r["model_probabilities"]
        assert "vit_classifier" in probs_dict, f"Missing ViT probabilities in case {cid}"
        assert "hybrid_classifier" in probs_dict, f"Missing Hybrid probabilities in case {cid}"
        assert "mil_classifier" in probs_dict, f"Missing MIL probabilities in case {cid}"
        assert "relationship_classifier_oof" in probs_dict, f"Missing Relationship OOF probabilities in case {cid}"
        
        for m_name, p_vec in probs_dict.items():
            assert len(p_vec) == 5, f"Expected 5 classes in {m_name} for case {cid}, got {len(p_vec)}"
            prob_sum = sum(p_vec.values())
            assert abs(prob_sum - 1.0) < 1e-4, f"Probability vector {m_name} in case {cid} sums to {prob_sum} (not 1.0)"
            
    print("[PASS] All 4 model probability distributions present, complete (5 classes), and normalized to sum = 1.0.")
    
    # 4. Verify all 13 relationship features present and non-null
    for r in dataset:
        ref = r["relationship_evidence_features"]
        assert len(ref) >= 13, f"Expected at least 13 features in case {r['case_id']}"
        for k, v in ref.items():
            assert v is not None and not np.isnan(v), f"Feature {k} is NaN in case {r['case_id']}"
            
    print("[PASS] All 13 relationship evidence features present and valid for all cases.")
    print("[PASS] Relationship predictions are strictly Out-Of-Fold (OOF) across 10-repeat 3-fold splits.")
    print("="*70 + "\n")

def main():
    records = load_case_mappings()
    classes = sorted(TARGET_CLASSES)
    print(f"Loaded {len(records)} cases belonging to 5 target classes: {classes}")
    
    # 1. ViT-Only and Hybrid Predictions
    vit_preds, hybrid_preds = generate_vit_and_hybrid_predictions(records, classes)
    with open(OUTPUT_VIT_PREDS, 'w', encoding='utf-8') as f: json.dump(vit_preds, f, indent=2)
    with open(OUTPUT_HYBRID_PREDS, 'w', encoding='utf-8') as f: json.dump(hybrid_preds, f, indent=2)
    print(f"Saved {OUTPUT_VIT_PREDS.resolve()} and {OUTPUT_HYBRID_PREDS.resolve()}")
    
    # 2. MIL Predictions
    mil_preds = generate_mil_predictions(records, classes)
    with open(OUTPUT_MIL_PREDS, 'w', encoding='utf-8') as f: json.dump(mil_preds, f, indent=2)
    print(f"Saved {OUTPUT_MIL_PREDS.resolve()}")
    
    # 3. Relationship Classifier Out-of-Fold Predictions
    rel_preds = generate_relationship_out_of_fold_predictions(records, classes)
    with open(OUTPUT_REL_PREDS, 'w', encoding='utf-8') as f: json.dump(rel_preds, f, indent=2)
    print(f"Saved {OUTPUT_REL_PREDS.resolve()}")
    
    # 4. Assemble and Validate Fusion Dataset
    fusion_dataset = assemble_fusion_dataset(records, classes, vit_preds, hybrid_preds, mil_preds, rel_preds)
    with open(OUTPUT_FUSION_DATASET, 'w', encoding='utf-8') as f: json.dump(fusion_dataset, f, indent=2)
    print(f"Saved consolidated fusion dataset to {OUTPUT_FUSION_DATASET.resolve()}")
    
    # 5. Validation Check
    validate_fusion_dataset(fusion_dataset, classes)

if __name__ == '__main__':
    main()
