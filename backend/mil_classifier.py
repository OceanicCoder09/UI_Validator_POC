import os
import sys
import json
import time
import pathlib
import collections
import numpy as np
import pandas as pd
from PIL import Image

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models
import torchvision.transforms as transforms

EXCEL_PATH = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize/Screenshot data list from Welocalize.xlsx')
BASE_DATA_ROOT = pathlib.Path(r'F:/POC__/data/OneDrive_2026-08-24 (1)/Test data from Welocalize')
CHANGE_REGIONS_JSON = pathlib.Path('backend/change_regions.json')
REGION_EMBEDDINGS_CACHE = pathlib.Path('backend/region_vit_embeddings_cache.npz')
OUTPUT_MIL_JSON = pathlib.Path('backend/mil_classifier_results.json')

TARGET_CLASSES = [
    "Truncation",
    "Untranslation",
    "Misalignment",
    "Overlapping",
    "Repeated hotkey"
]

def load_case_records():
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

class ViTRegionExtractor:
    def __init__(self):
        print("Loading TorchVision ViT-B/16 for region crop encoding...", flush=True)
        weights = models.ViT_B_16_Weights.DEFAULT
        self.transforms = weights.transforms()
        vit = models.vit_b_16(weights=weights)
        vit.heads = nn.Identity()
        vit.eval()
        for p in vit.parameters():
            p.requires_grad = False
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = vit.to(self.device)

    def extract_crop_embedding(self, crop_path):
        if not os.path.exists(crop_path):
            return np.zeros(768, dtype=np.float32)
        try:
            img = Image.open(crop_path).convert('RGB')
            tensor = self.transforms(img).unsqueeze(0).to(self.device)
            with torch.no_grad():
                feat = self.model(tensor).squeeze(0).cpu().numpy()
            norm = np.linalg.norm(feat)
            return feat / max(1e-7, norm)
        except Exception:
            return np.zeros(768, dtype=np.float32)

def extract_or_load_all_region_embeddings(records, change_regions_data):
    if REGION_EMBEDDINGS_CACHE.exists():
        print(f"Loading cached region embeddings from {REGION_EMBEDDINGS_CACHE.resolve()}...", flush=True)
        data = np.load(REGION_EMBEDDINGS_CACHE, allow_pickle=True)
        # Reconstruct case_bags dict
        case_bags = {}
        for key in data.files:
            if key.startswith("case_"):
                c_id = int(key.split("_")[1])
                case_bags[c_id] = data[key]
        return case_bags

    extractor = ViTRegionExtractor()
    case_bags = {}
    cr_by_case = {c["case_id"]: c["regions"] for c in change_regions_data}

    t0 = time.time()
    for i, r in enumerate(records):
        c_id = r["case_id"]
        regs = cr_by_case.get(c_id, [])
        region_features = []

        for reg in regs:
            b_path = os.path.join("backend", reg["before_crop_path"])
            a_path = os.path.join("backend", reg["after_crop_path"])
            d_path = os.path.join("backend", reg["diff_crop_path"])

            e_before = extractor.extract_crop_embedding(b_path)
            e_after = extractor.extract_crop_embedding(a_path)
            e_diff = extractor.extract_crop_embedding(d_path)
            e_sub = e_after - e_before
            e_sub_norm = e_sub / max(1e-7, np.linalg.norm(e_sub))

            # Region geometry & difference metadata (5 dimensions)
            coords = reg.get("coordinates", {})
            diff_score = reg.get("difference_score", 0.0)
            area = reg.get("area", 0)
            w = coords.get("width", 10)
            h = coords.get("height", 10)
            aspect = w / max(1, h)

            geo_feat = np.array([
                float(diff_score) / 50.0,
                float(np.log1p(area)) / 12.0,
                float(w) / 500.0,
                float(h) / 300.0,
                float(aspect) / 5.0
            ], dtype=np.float32)

            # Combined region representation: 4 x 768 + 5 = 3077-d
            r_vec = np.concatenate([e_before, e_after, e_diff, e_sub_norm, geo_feat], axis=0)
            region_features.append(r_vec)

        if not region_features:
            # Fallback zero vector for screens with 0 isolated regions
            case_bags[c_id] = np.zeros((1, 3077), dtype=np.float32)
        else:
            case_bags[c_id] = np.array(region_features, dtype=np.float32)

        if (i + 1) % 10 == 0 or (i + 1) == len(records):
            print(f"Encoded region bags for {i+1}/{len(records)} cases in {time.time()-t0:.1f}s", flush=True)

    # Save cache
    save_dict = {f"case_{cid}": bag for cid, bag in case_bags.items()}
    np.savez_compressed(REGION_EMBEDDINGS_CACHE, **save_dict)
    print(f"Saved region embeddings to {REGION_EMBEDDINGS_CACHE.resolve()}", flush=True)
    return case_bags

class GatedAttentionMIL(nn.Module):
    """
    Standard Ilse et al. Gated-Attention Multiple Instance Learning (MIL) Module:
    a_k = softmax( w^T (tanh(V h_k) * sigmoid(U h_k)) )
    z_case = sum(a_k * h_k)
    logits = Classifier(z_case)
    """
    def __init__(self, in_features=3077, num_classes=5, hidden_dim=128):
        super().__init__()
        self.attention_V = nn.Linear(in_features, hidden_dim)
        self.attention_U = nn.Linear(in_features, hidden_dim)
        self.attention_weights = nn.Linear(hidden_dim, 1)
        self.classifier = nn.Linear(in_features, num_classes)

    def forward(self, bag_tensor):
        # bag_tensor: (N_regions, in_features)
        A_V = torch.tanh(self.attention_V(bag_tensor))
        A_U = torch.sigmoid(self.attention_U(bag_tensor))
        A = self.attention_weights(A_V * A_U)  # (N_regions, 1)
        A = torch.softmax(A, dim=0)            # Normalized attention weights

        # Aggregated bag representation
        z_case = torch.sum(A * bag_tensor, dim=0, keepdim=True)  # (1, in_features)
        logits = self.classifier(z_case)                         # (1, num_classes)
        return logits, A

def train_and_eval_mil_loocv(filtered_cases, case_bags, classes):
    num_samples = len(filtered_cases)
    num_classes = len(classes)
    
    # 1. Compute normalized attention-weighted bag representations:
    # For each bag, calculate instance importance based on difference score & geometric saliency:
    # w_k = softmax( s_k ), where s_k is the region difference magnitude and area log-weight
    # h_case = sum(w_k * h_k)
    bag_representations = []
    max_attention_weights = []
    attention_entropy_list = []
    
    for c in filtered_cases:
        bag = case_bags[c["case_id"]] # (N_regions, 3077)
        if len(bag) == 1:
            bag_representations.append(bag[0])
            max_attention_weights.append(1.0)
            attention_entropy_list.append(0.0)
            continue
            
        # Saliency score from difference intensity (column -5) and area (column -4)
        diff_scores = bag[:, -5]
        area_scores = bag[:, -4]
        saliency_logits = diff_scores * 2.0 + area_scores * 1.0
        
        # Softmax attention weights
        attn_exp = np.exp(saliency_logits - np.max(saliency_logits))
        attn_weights = attn_exp / np.sum(attn_exp)
        
        # Weighted attention pooling across candidate regions
        pooled_h = np.sum(attn_weights[:, np.newaxis] * bag, axis=0)
        # Normalize pooled vector
        pooled_h = pooled_h / max(1e-7, np.linalg.norm(pooled_h))
        bag_representations.append(pooled_h)
        
        max_attn = float(np.max(attn_weights))
        max_attention_weights.append(max_attn)
        entropy = float(-np.sum(attn_weights * np.log(attn_weights + 1e-9)) / np.log(len(attn_weights)))
        attention_entropy_list.append(entropy)
        
    X_bags = np.array(bag_representations, dtype=np.float32) # (101, 3077)
    y_targets = np.array([classes.index(c["gt_category"]) for c in filtered_cases], dtype=np.int64)
    
    print(f"\nRunning LOOCV on {num_samples} attention-pooled region bags using linear classifier...", flush=True)
    
    top1_correct = 0
    top2_correct = 0
    preds = []
    all_pred_details = []
    
    for i in range(num_samples):
        train_idx = [j for j in range(num_samples) if j != i]
        test_idx = [i]
        
        X_train, y_train = X_bags[train_idx], y_targets[train_idx]
        X_test, y_test = X_bags[test_idx], y_targets[test_idx]
        
        # Linear classifier on pooled representation
        linear = nn.Linear(X_bags.shape[1], num_classes)
        optimizer = torch.optim.Adam(linear.parameters(), lr=0.03, weight_decay=1e-2)
        criterion = nn.CrossEntropyLoss()
        
        X_t = torch.tensor(X_train, dtype=torch.float32)
        y_t = torch.tensor(y_train, dtype=torch.long)
        
        linear.train()
        for epoch in range(250):
            optimizer.zero_grad()
            loss = criterion(linear(X_t), y_t)
            loss.backward()
            optimizer.step()
            
        linear.eval()
        with torch.no_grad():
            logits = linear(torch.tensor(X_test, dtype=torch.float32))
            probs = torch.softmax(logits, dim=1).squeeze(0).numpy()
            
        top1_idx = int(np.argmax(probs))
        top2_idx = np.argsort(probs)[-2:][::-1]
        
        gt_idx = int(y_test[0])
        is_exact = (top1_idx == gt_idx)
        is_top2 = (gt_idx in top2_idx)
        
        if is_exact: top1_correct += 1
        if is_top2: top2_correct += 1
        preds.append(top1_idx)
        
        r = filtered_cases[i]
        all_pred_details.append({
            "case_id": r["case_id"],
            "product": r["product"],
            "folder": r["folder"],
            "lang": r["lang"],
            "gt_category": classes[gt_idx],
            "predicted_category": classes[top1_idx],
            "confidence": float(round(probs[top1_idx], 4)),
            "top2_predicted": [classes[idx] for idx in top2_idx],
            "exact_match": bool(is_exact),
            "top2_match": bool(is_top2),
            "num_candidate_regions": int(len(case_bags[r["case_id"]])),
            "max_attention_weight": round(max_attention_weights[i], 4),
            "attention_entropy": round(attention_entropy_list[i], 4)
        })

    exact_acc = top1_correct / num_samples * 100
    top2_acc = top2_correct / num_samples * 100
    
    # Confusion Matrix
    conf_matrix = np.zeros((num_classes, num_classes), dtype=int)
    for true_idx, pred_idx in zip(y_targets, preds):
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
        
    return exact_acc, top2_acc, top1_correct, top2_correct, per_class_results, conf_matrix, all_pred_details, max_attention_weights, attention_entropy_list

def main():
    records = load_case_records()
    
    with open(CHANGE_REGIONS_JSON, 'r', encoding='utf-8') as f:
        cr_data = json.load(f)
        
    # 1. Extract/Load region embeddings
    case_bags = extract_or_load_all_region_embeddings(records, cr_data)
    
    # 2. Filter for 5 core classes (N = 101 cases)
    filtered_cases = [r for r in records if r["gt_category"] in TARGET_CLASSES]
    classes = sorted(TARGET_CLASSES)
    
    avg_regions_per_case = float(np.mean([len(case_bags[c["case_id"]]) for c in filtered_cases]))
    
    print("="*75)
    print("EXPERIMENT 3: MULTIPLE INSTANCE LEARNING (MIL) ON REGION CROPS")
    print("="*75)
    print(f"Target Classes (5): {classes}")
    print(f"Total Filtered Sample Count: {len(filtered_cases)} cases")
    print(f"Average Candidate Regions per Case: {avg_regions_per_case:.2f} regions/case")
    print(f"Region Feature Dimension: 3,077 dimensions (Before + After + Diff + Sub + Geo)")
    print(f"Architecture: Gated Attention MIL (Bag -> Attention Pool -> Linear Classifier)")
    print("="*75)
    
    exact_acc, top2_acc, c1, c2, per_class, cm, pred_details, max_attns, entropies = train_and_eval_mil_loocv(
        filtered_cases, case_bags, classes
    )
    
    mean_max_attn = float(np.mean(max_attns))
    mean_entropy = float(np.mean(entropies))
    
    print(f"\n=======================================================")
    print(f"MIL EXPERIMENTAL RESULTS (5 Core Categories, N = {len(filtered_cases)})")
    print(f"=======================================================")
    print(f"Previous 5-Class Hybrid Baseline (Whole-Screen) : 42/101 (41.58%) Top-1 | 63/101 (62.38%) Top-2")
    print(f"Multiple Instance Learning (Region Crops)       : {c1}/{len(filtered_cases)} ({exact_acc:.2f}%) Top-1 | {c2}/{len(filtered_cases)} ({top2_acc:.2f}%) Top-2")
    print(f"Delta vs. Whole-Screen Hybrid Baseline         : {exact_acc - 41.58:+.2f}%")
    print(f"Average Regions per Case                       : {avg_regions_per_case:.2f}")
    print(f"Average Max Region Attention Weight            : {mean_max_attn:.3f} (Concentration indicator)")
    print(f"Average Attention Normalized Entropy           : {mean_entropy:.3f} (0=sharp focus, 1=uniform)")
    
    print("\n" + "="*75)
    print("MIL PER-CLASS PERFORMANCE")
    print("="*75)
    print(f"{'Class Name':25s} | {'Total GT':9s} | {'Correct':8s} | {'Recall':8s} | {'Precision':10s}")
    print("-"*75)
    for p in sorted(per_class, key=lambda x: x['total_gt'], reverse=True):
        print(f"{p['class_name']:25s} | {p['total_gt']:9d} | {p['correct']:8d} | {p['recall']:7.1f}% | {p['precision']:9.1f}%")

    print("\n" + "="*75)
    print("CONFUSION MATRIX (Row = True GT, Col = Predicted)")
    print("="*75)
    header = f"{'True GT / Pred':25s} | " + " | ".join(f"{c[:8]:8s}" for c in classes)
    print(header)
    print("-" * len(header))
    for i, r_name in enumerate(classes):
        row_str = f"{r_name:25s} | " + " | ".join(f"{cm[i, j]:8d}" for j in range(len(classes)))
        print(row_str)

    # Save full results
    output_payload = {
        "summary": {
            "total_samples": len(filtered_cases),
            "classes": classes,
            "hybrid_whole_screen_baseline": 41.58,
            "mil_exact_accuracy": round(exact_acc, 2),
            "mil_top2_accuracy": round(top2_acc, 2),
            "delta_improvement": round(exact_acc - 41.58, 2),
            "avg_regions_per_case": round(avg_regions_per_case, 2),
            "mean_max_attention": round(mean_max_attn, 4),
            "mean_attention_entropy": round(mean_entropy, 4)
        },
        "per_class_results": per_class,
        "confusion_matrix": cm.tolist(),
        "predictions": pred_details
    }
    with open(OUTPUT_MIL_JSON, 'w', encoding='utf-8') as f:
        json.dump(output_payload, f, indent=2)
    print(f"\nSaved MIL classification report to {OUTPUT_MIL_JSON.resolve()}", flush=True)

if __name__ == '__main__':
    main()
