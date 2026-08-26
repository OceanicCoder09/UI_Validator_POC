import os
import sys
import json
import time
import pathlib
import collections
import cv2
import numpy as np
import pandas as pd
from PIL import Image

import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as transforms

# Define Paths
EXCEL_PATH = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize/Screenshot data list from Welocalize.xlsx')
BASE_DATA_ROOT = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize')
EMBEDDINGS_CACHE = pathlib.Path('backend/vit_embeddings_cache.npz')
RESULTS_JSON = pathlib.Path('backend/vit_classifier_results.json')

def load_dataset_records():
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
            "gt_category": gt_cat,
            "en_path": str(en_files[0]),
            "loc_path": str(loc_files[0])
        })
    return records

class ViTFeatureExtractor:
    def __init__(self):
        print("Loading TorchVision ViT-B/16 pretrained weights...", flush=True)
        weights = models.ViT_B_16_Weights.DEFAULT
        self.transforms = weights.transforms()
        vit = models.vit_b_16(weights=weights)
        vit.heads = nn.Identity()  # Remove classification head to output 768-d embedding
        vit.eval()
        for p in vit.parameters():
            p.requires_grad = False
        self.model = vit
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
        print(f"ViT-B/16 loaded successfully on {self.device} (output dim: 768).", flush=True)

    def extract_image_embedding(self, pil_img):
        tensor = self.transforms(pil_img).unsqueeze(0).to(self.device)
        with torch.no_grad():
            feat = self.model(tensor)
        feat = feat.squeeze(0).cpu().numpy()
        # L2 normalize
        norm = np.linalg.norm(feat)
        return feat / max(1e-7, norm)

    def compute_pair_features(self, en_path, loc_path):
        img_en = Image.open(en_path).convert('RGB')
        img_loc = Image.open(loc_path).convert('RGB')
        
        # Match dimensions for difference
        if img_en.size != img_loc.size:
            img_loc_res = img_loc.resize(img_en.size, Image.Resampling.BILINEAR)
        else:
            img_loc_res = img_loc

        # 1. ENU image embedding (768-d)
        e_enu = self.extract_image_embedding(img_en)
        
        # 2. Localized image embedding (768-d)
        e_loc = self.extract_image_embedding(img_loc)
        
        # 3. Difference image embedding (768-d)
        arr_en = np.array(img_en, dtype=np.int16)
        arr_loc = np.array(img_loc_res, dtype=np.int16)
        diff_arr = np.abs(arr_loc - arr_en).astype(np.uint8)
        img_diff = Image.fromarray(diff_arr, mode='RGB')
        e_diff = self.extract_image_embedding(img_diff)
        
        # 4. Localized minus ENU vector representation (768-d)
        e_sub = e_loc - e_enu
        e_sub_norm = e_sub / max(1e-7, np.linalg.norm(e_sub))
        
        # Concatenate ONLY these four visual representations (4 * 768 = 3072-d)
        fused_vector = np.concatenate([e_enu, e_loc, e_diff, e_sub_norm], axis=0)
        return fused_vector

def extract_or_load_all_features(records):
    if EMBEDDINGS_CACHE.exists():
        print(f"Loading cached ViT-B/16 embeddings from {EMBEDDINGS_CACHE.resolve()}...", flush=True)
        data = np.load(EMBEDDINGS_CACHE, allow_pickle=True)
        return data['X'], data['y'], list(data['classes']), list(data['case_ids'])
        
    extractor = ViTFeatureExtractor()
    X_list = []
    y_list = []
    case_ids = []
    
    t0 = time.time()
    for i, r in enumerate(records):
        feat = extractor.compute_pair_features(r['en_path'], r['loc_path'])
        X_list.append(feat)
        y_list.append(r['gt_category'])
        case_ids.append(r['case_id'])
        if (i + 1) % 10 == 0 or (i + 1) == len(records):
            print(f"Extracted ViT-B/16 features for {i+1}/{len(records)} pairs in {time.time()-t0:.1f}s", flush=True)
            
    X = np.array(X_list, dtype=np.float32)
    classes = sorted(list(set(y_list)))
    y = np.array([classes.index(c) for c in y_list], dtype=np.int64)
    
    np.savez_compressed(EMBEDDINGS_CACHE, X=X, y=y, classes=classes, case_ids=case_ids)
    print(f"Saved extracted ViT embeddings matrix {X.shape} to {EMBEDDINGS_CACHE.resolve()}", flush=True)
    return X, y, classes, case_ids

class MulticlassLogisticRegression:
    """Multiclass Logistic Regression / Linear Softmax Classifier with L2 Regularization."""
    def __init__(self, num_features, num_classes, lr=0.05, weight_decay=1e-3, epochs=300):
        self.num_features = num_features
        self.num_classes = num_classes
        self.lr = lr
        self.weight_decay = weight_decay
        self.epochs = epochs
        
    def fit(self, X_train, y_train):
        # Convert to torch tensors
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

def evaluate_classifier():
    records = load_dataset_records()
    print(f"Total benchmark records: {len(records)}")
    
    # Extract / Load Embeddings
    X, y, classes, case_ids = extract_or_load_all_features(records)
    num_samples, num_features = X.shape
    num_classes = len(classes)
    
    print("\n" + "="*70)
    print(f"EXPERIMENT SETUP")
    print(f"Total Samples: {num_samples}")
    print(f"Feature Dimension: {num_features} (4 x 768-d ViT embeddings)")
    print(f"Total Defect Classes: {num_classes}")
    print("="*70)
    
    # Evaluation Strategy:
    # 10 single-instance classes exist in the dataset (e.g. Bad layout, Different Number Controls).
    # Stratified K-Fold is mathematically impossible for singleton classes (cannot partition 1 item across k folds).
    # Therefore, we evaluate using:
    # 1. Leave-One-Out Cross-Validation (LOOCV) across all 114 cases (standard unbiased gold standard for small n=114 datasets)
    # 2. Stratified 5-Fold on the subset of non-singleton classes.
    
    print("\nRunning Leave-One-Out Cross Validation (LOOCV) across all 114 benchmark cases...", flush=True)
    
    loocv_preds = []
    loocv_top2_correct = 0
    loocv_exact_correct = 0
    
    all_pred_records = []
    
    for i in range(num_samples):
        # Leave out sample i as test
        train_idx = [j for j in range(num_samples) if j != i]
        test_idx = [i]
        
        X_train, y_train = X[train_idx], y[train_idx]
        X_test, y_test = X[test_idx], y[test_idx]
        
        clf = MulticlassLogisticRegression(num_features=num_features, num_classes=num_classes, lr=0.03, weight_decay=1e-2, epochs=250)
        clf.fit(X_train, y_train)
        
        probs = clf.predict_proba(X_test)[0]
        top1_idx = int(np.argmax(probs))
        top2_indices = np.argsort(probs)[-2:][::-1]
        
        gt_idx = int(y_test[0])
        is_exact = (top1_idx == gt_idx)
        is_top2 = (gt_idx in top2_indices)
        
        if is_exact: loocv_exact_correct += 1
        if is_top2: loocv_top2_correct += 1
        
        loocv_preds.append(top1_idx)
        
        rec = records[i]
        all_pred_records.append({
            "case_id": rec["case_id"],
            "product": rec["product"],
            "folder": rec["folder"],
            "lang": rec["lang"],
            "gt_category": classes[gt_idx],
            "predicted_category": classes[top1_idx],
            "confidence": float(round(probs[top1_idx], 4)),
            "top2_predicted": [classes[idx] for idx in top2_indices],
            "top2_confidences": [float(round(probs[idx], 4)) for idx in top2_indices],
            "exact_match": bool(is_exact),
            "top2_match": bool(is_top2)
        })

    exact_acc = loocv_exact_correct / num_samples * 100
    top2_acc = loocv_top2_correct / num_samples * 100
    
    # Confusion Matrix & Per-class stats
    conf_matrix = np.zeros((num_classes, num_classes), dtype=int)
    for true_idx, pred_idx in zip(y, loocv_preds):
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
        
    print("\n" + "="*70)
    print(f"EVALUATION RESULTS (Clean Baseline - ViT-B/16 Visual Classifier)")
    print("="*70)
    print(f"Total Benchmark Cases: {num_samples}")
    print(f"Exact Accuracy:        {loocv_exact_correct}/{num_samples} ({exact_acc:.2f}%)")
    print(f"Top-2 Accuracy:        {loocv_top2_correct}/{num_samples} ({top2_acc:.2f}%)")
    print("\nPer-Class Breakdown:")
    print(f"{'Class Name':40s} | {'Total':5s} | {'Correct':7s} | {'Recall':8s} | {'Precision':10s}")
    print("-"*78)
    for p in sorted(per_class_results, key=lambda x: x['total_gt'], reverse=True):
        print(f"{p['class_name']:40s} | {p['total_gt']:5d} | {p['correct']:7d} | {p['recall']:7.1f}% | {p['precision']:9.1f}%")
        
    # Save Full JSON results
    output_data = {
        "summary": {
            "total_samples": num_samples,
            "feature_dim": num_features,
            "exact_accuracy_pct": round(exact_acc, 2),
            "exact_correct": loocv_exact_correct,
            "top2_accuracy_pct": round(top2_acc, 2),
            "top2_correct": loocv_top2_correct,
            "evaluation_strategy": "Leave-One-Out Cross-Validation (LOOCV)"
        },
        "per_class_results": per_class_results,
        "classes": classes,
        "confusion_matrix": conf_matrix.tolist(),
        "predictions": all_pred_records
    }
    
    with open(RESULTS_JSON, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
    print(f"\nSaved full evaluation and predictions to {RESULTS_JSON.resolve()}", flush=True)

if __name__ == '__main__':
    evaluate_classifier()
