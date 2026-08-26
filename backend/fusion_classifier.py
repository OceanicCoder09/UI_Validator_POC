import os
import sys
import json
import pathlib
import collections
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

FUSION_DATASET_PATH = pathlib.Path('backend/fusion_dataset.json')
OUTPUT_RESULTS_JSON = pathlib.Path('backend/fusion_classifier_results.json')
OUTPUT_REPORT_HTML = pathlib.Path('backend/fusion_classifier_report.html')

TARGET_CLASSES = [
    "Misalignment",
    "Overlapping",
    "Repeated hotkey",
    "Truncation",
    "Untranslation"
]

def load_fusion_data():
    with open(FUSION_DATASET_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    classes = sorted(TARGET_CLASSES)
    
    feature_names = []
    # 1. 5 ViT probabilities
    for c in classes: feature_names.append(f"vit_prob_{c}")
    # 2. 5 Hybrid probabilities
    for c in classes: feature_names.append(f"hybrid_prob_{c}")
    # 3. 5 MIL probabilities
    for c in classes: feature_names.append(f"mil_prob_{c}")
    # 4. 5 Relationship OOF probabilities
    for c in classes: feature_names.append(f"rel_oof_prob_{c}")
    
    # 5. 13 Relationship evidence features
    rel_feat_keys = [
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
    for k in rel_feat_keys: feature_names.append(f"ev_{k}")
    
    # 6. MIL attention weight & entropy
    feature_names.append("mil_max_attention_weight")
    feature_names.append("mil_attention_entropy")
    
    X_list = []
    y_list = []
    case_meta = []
    
    for row in data:
        mp = row["model_probabilities"]
        ref = row["relationship_evidence_features"]
        mil_m = row["mil_metadata"]
        
        vec = []
        # 1. ViT
        for c in classes: vec.append(float(mp["vit_classifier"].get(c, 0.0)))
        # 2. Hybrid
        for c in classes: vec.append(float(mp["hybrid_classifier"].get(c, 0.0)))
        # 3. MIL
        for c in classes: vec.append(float(mp["mil_classifier"].get(c, 0.0)))
        # 4. Relationship OOF
        for c in classes: vec.append(float(mp["relationship_classifier_oof"].get(c, 0.0)))
        
        # 5. Relationship Evidence (13 features)
        for k in rel_feat_keys:
            vec.append(float(ref.get(k, 0.0)))
            
        # 6. MIL metadata
        vec.append(float(mil_m.get("max_attention_weight", 0.0)))
        vec.append(float(mil_m.get("attention_entropy", 0.0)))
        
        X_list.append(vec)
        y_list.append(classes.index(row["gt_category"]))
        case_meta.append({
            "case_id": row["case_id"],
            "product": row["product"],
            "folder": row["folder"],
            "lang": row["lang"],
            "gt_category": row["gt_category"]
        })
        
    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.int64)
    return X, y, classes, feature_names, case_meta

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

def evaluate_fusion_classifier(X, y, classes, feature_names, n_splits=3, n_repeats=10):
    num_classes = len(classes)
    num_features = X.shape[1]
    
    top1_accuracies = []
    top2_accuracies = []
    agg_conf_matrix = np.zeros((num_classes, num_classes), dtype=int)
    all_coefficients = []
    
    for repeat in range(n_repeats):
        splits = get_stratified_folds(y, n_splits=n_splits, seed=42 + repeat * 17)
        for train_idx, test_idx in splits:
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]
            
            # Normalization fit strictly on training fold only
            mean = np.mean(X_train, axis=0, keepdims=True)
            std = np.std(X_train, axis=0, keepdims=True)
            std[std < 1e-7] = 1.0
            
            X_train_scaled = (X_train - mean) / std
            X_test_scaled = (X_test - mean) / std
            
            # Regularized Multinomial Logistic Regression in PyTorch
            torch.manual_seed(42 + repeat)
            model = nn.Linear(num_features, num_classes)
            optimizer = torch.optim.Adam(model.parameters(), lr=0.03, weight_decay=1e-3)
            criterion = nn.CrossEntropyLoss()
            
            Xt = torch.tensor(X_train_scaled, dtype=torch.float32)
            yt = torch.tensor(y_train, dtype=torch.long)
            
            model.train()
            for _ in range(120):
                optimizer.zero_grad()
                loss = criterion(model(Xt), yt)
                loss.backward()
                optimizer.step()
                
            all_coefficients.append(model.weight.detach().cpu().numpy())
            
            model.eval()
            with torch.no_grad():
                logits = model(torch.tensor(X_test_scaled, dtype=torch.float32))
                probs = torch.softmax(logits, dim=1).numpy()
                
            preds = np.argmax(probs, axis=1)
            top2_preds = np.argsort(probs, axis=1)[:, -2:]
            
            fold_top1 = np.mean(preds == y_test) * 100.0
            fold_top2 = np.mean([y_test[i] in top2_preds[i] for i in range(len(y_test))]) * 100.0
            
            top1_accuracies.append(fold_top1)
            top2_accuracies.append(fold_top2)
            
            for true_c, pred_c in zip(y_test, preds):
                agg_conf_matrix[true_c, pred_c] += 1

    mean_top1 = float(np.mean(top1_accuracies))
    std_top1 = float(np.std(top1_accuracies))
    mean_top2 = float(np.mean(top2_accuracies))
    std_top2 = float(np.std(top2_accuracies))
    
    total_evals = int(np.sum(agg_conf_matrix))
    total_correct = int(np.trace(agg_conf_matrix))
    
    per_class_metrics = []
    for c_idx, c_name in enumerate(classes):
        total_gt = int(np.sum(agg_conf_matrix[c_idx, :]))
        correct = int(agg_conf_matrix[c_idx, c_idx])
        total_pred = int(np.sum(agg_conf_matrix[:, c_idx]))
        recall = (correct / total_gt * 100.0) if total_gt > 0 else 0.0
        precision = (correct / total_pred * 100.0) if total_pred > 0 else 0.0
        per_class_metrics.append({
            "class_name": c_name,
            "total_gt_evaluations": total_gt,
            "correct_evaluations": correct,
            "recall": round(recall, 2),
            "precision": round(precision, 2)
        })
        
    # Learned feature coefficients averaged across all 30 folds
    mean_coef = np.mean(all_coefficients, axis=0) # (5, 35)
    feature_importance_by_class = {}
    for c_idx, c_name in enumerate(classes):
        coef_dict = {feature_names[f_idx]: round(float(mean_coef[c_idx, f_idx]), 4) for f_idx in range(num_features)}
        sorted_coef = sorted(coef_dict.items(), key=lambda x: abs(x[1]), reverse=True)
        feature_importance_by_class[c_name] = sorted_coef
        
    return {
        "mean_top1_accuracy": round(mean_top1, 2),
        "std_top1_accuracy": round(std_top1, 2),
        "mean_top2_accuracy": round(mean_top2, 2),
        "std_top2_accuracy": round(std_top2, 2),
        "total_evaluations": total_evals,
        "total_correct_predictions": total_correct,
        "per_class_metrics": per_class_metrics,
        "aggregated_confusion_matrix": agg_conf_matrix.tolist(),
        "feature_importance_by_class": feature_importance_by_class,
        "classes": classes,
        "feature_names": feature_names
    }

def generate_html_report(results, output_path):
    classes = results["classes"]
    cm = np.array(results["aggregated_confusion_matrix"])
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Fusion Classifier Benchmark Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
  h1 {{ color: #38bdf8; font-size: 24px; margin-bottom: 6px; }}
  h2 {{ color: #93c5fd; font-size: 18px; margin-top: 28px; border-bottom: 1px solid #334155; padding-bottom: 6px; }}
  .metrics-banner {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 20px 0; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 18px; text-align: center; }}
  .card-val {{ font-size: 26px; font-weight: bold; color: #38bdf8; margin-top: 4px; }}
  .card-sub {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 13px; background: #1e293b; border-radius: 6px; overflow: hidden; }}
  th, td {{ padding: 10px 14px; text-align: right; border-bottom: 1px solid #334155; }}
  th:first-child, td:first-child {{ text-align: left; }}
  th {{ background: #0f172a; color: #38bdf8; font-weight: 600; }}
  tr:hover {{ background: #243247; }}
  .coef-pos {{ color: #4ade80; font-family: monospace; font-weight: bold; }}
  .coef-neg {{ color: #f43f5e; font-family: monospace; }}
</style>
</head>
<body>
<h1>Multimodal Fusion Classifier — Repeated Stratified 3-Fold Cross-Validation</h1>
<div style="color: #94a3b8; font-size: 14px;">
  Fusing 35 multimodal signals (ViT + Hybrid + MIL + Relationship OOF probabilities + 13 physical relationship metrics + MIL attention metadata).
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 14px; color: #94a3b8;">Fusion Mean Top-1 Accuracy</div>
    <div class="card-val">{results['mean_top1_accuracy']}%</div>
    <div class="card-sub">&plusmn; {results['std_top1_accuracy']}%</div>
  </div>
  <div class="card">
    <div style="font-size: 14px; color: #94a3b8;">Fusion Mean Top-2 Accuracy</div>
    <div class="card-val">{results['mean_top2_accuracy']}%</div>
    <div class="card-sub">&plusmn; {results['std_top2_accuracy']}%</div>
  </div>
  <div class="card">
    <div style="font-size: 14px; color: #94a3b8;">Best Previous Single Baseline</div>
    <div class="card-val" style="color: #cbd5e1;">41.58%</div>
    <div class="card-sub">Hybrid ViT+Evidence</div>
  </div>
  <div class="card">
    <div style="font-size: 14px; color: #94a3b8;">Total Test Evaluations</div>
    <div class="card-val" style="color: #4ade80;">{results['total_correct_predictions']} / {results['total_evaluations']}</div>
    <div class="card-sub">across 30 independent folds</div>
  </div>
</div>

<h2>1. Baseline Comparison (5 Core Categories, N = 101)</h2>
<table>
  <thead>
    <tr>
      <th>Model Architecture</th>
      <th>Top-1 Accuracy</th>
      <th>Top-2 Accuracy</th>
      <th>Delta vs Hybrid Baseline (41.58%)</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Relationship-Only Classifier</td>
      <td>33.59% &plusmn; 6.11%</td>
      <td>55.23%</td>
      <td style="color: #f43f5e;">-7.99%</td>
    </tr>
    <tr>
      <td>Multiple Instance Learning (MIL)</td>
      <td>38.61%</td>
      <td>51.49%</td>
      <td style="color: #f43f5e;">-2.97%</td>
    </tr>
    <tr>
      <td>Whole-Screen ViT-B/16 Only</td>
      <td>40.59%</td>
      <td>62.38%</td>
      <td style="color: #f43f5e;">-0.99%</td>
    </tr>
    <tr>
      <td>Whole-Screen Hybrid (ViT + Evidence)</td>
      <td>41.58%</td>
      <td>62.38%</td>
      <td>0.00% (Baseline)</td>
    </tr>
    <tr style="background: #1e3a5f; font-weight: bold;">
      <td style="color: #38bdf8;">Multimodal Fusion Classifier (35 Features)</td>
      <td style="color: #38bdf8;">{results['mean_top1_accuracy']}% &plusmn; {results['std_top1_accuracy']}%</td>
      <td style="color: #38bdf8;">{results['mean_top2_accuracy']}%</td>
      <td style="color: {'#4ade80' if results['mean_top1_accuracy'] >= 41.58 else '#f43f5e'}; font-weight:bold;">
        {results['mean_top1_accuracy'] - 41.58:+.2f}%
      </td>
    </tr>
  </tbody>
</table>

<h2>2. Per-Class Recall & Precision Breakdown</h2>
<table>
  <thead>
    <tr>
      <th>Class Name</th>
      <th>Total GT Samples</th>
      <th>Correct Predictions</th>
      <th>Recall</th>
      <th>Precision</th>
    </tr>
  </thead>
  <tbody>
"""
    for p in results["per_class_metrics"]:
        html += f"""
    <tr>
      <td style="font-weight: 600;">{p['class_name']}</td>
      <td>{p['total_gt_evaluations']}</td>
      <td>{p['correct_evaluations']}</td>
      <td style="font-weight: bold; color: #38bdf8;">{p['recall']}%</td>
      <td>{p['precision']}%</td>
    </tr>
"""
    html += """
  </tbody>
</table>

<h2>3. Aggregated Confusion Matrix (Row = True GT, Col = Predicted)</h2>
<table>
  <thead>
    <tr>
      <th>True GT / Predicted</th>
"""
    for c in classes:
        html += f"<th>{c[:8]}</th>"
    html += "<th>Total GT</th></tr></thead><tbody>"
    
    for r_idx, c_name in enumerate(classes):
        html += f"<tr><td style='font-weight:600;'>{c_name}</td>"
        row_sum = np.sum(cm[r_idx, :])
        for c_idx in range(len(classes)):
            val = cm[r_idx, c_idx]
            is_diag = (r_idx == c_idx)
            style = "font-weight: bold; color: #4ade80;" if is_diag else "color: #94a3b8;"
            html += f"<td style='{style}'>{val}</td>"
        html += f"<td style='font-weight:bold;'>{row_sum}</td></tr>"
        
    html += """
  </tbody>
</table>

<h2>4. Top Learned Feature Weights (Positive Decision Drivers by Class)</h2>
"""
    for c_name, top_coefs in results["feature_importance_by_class"].items():
        html += f"""
<h3 style="font-size:15px; color:#38bdf8; margin-top:18px;">Target Class: <code>{c_name}</code></h3>
<table>
  <thead>
    <tr>
      <th>Feature Name</th>
      <th>Mean Weight (Coefficient)</th>
      <th>Impact Direction</th>
    </tr>
  </thead>
  <tbody>
"""
        for feat_name, weight in top_coefs[:6]:
            cls_style = "coef-pos" if weight > 0 else "coef-neg"
            direction = "Positive Driver (+)" if weight > 0 else "Negative Suppressor (-)"
            html += f"""
    <tr>
      <td><code>{feat_name}</code></td>
      <td class="{cls_style}">{weight:+.4f}</td>
      <td>{direction}</td>
    </tr>
"""
        html += """
  </tbody>
</table>
"""

    html += """
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

def main():
    print("Loading 35 multimodal features from backend/fusion_dataset.json...", flush=True)
    X, y, classes, feature_names, case_meta = load_fusion_data()
    print(f"Loaded {len(X)} cases across {len(classes)} classes with {X.shape[1]} multimodal features.")
    
    print("\nRunning Repeated Stratified 3-Fold Cross-Validation (10 Repeats = 30 total folds)...", flush=True)
    results = evaluate_fusion_classifier(X, y, classes, feature_names, n_splits=3, n_repeats=10)
    
    print("\n" + "="*70)
    print("MULTIMODAL FUSION CLASSIFIER RESULTS (N = 101)")
    print("="*70)
    print(f"Mean Top-1 Accuracy : {results['mean_top1_accuracy']}%  (+/- {results['std_top1_accuracy']}%)")
    print(f"Mean Top-2 Accuracy : {results['mean_top2_accuracy']}%  (+/- {results['std_top2_accuracy']}%)")
    print(f"Total Correct Preds : {results['total_correct_predictions']} / {results['total_evaluations']}")
    print(f"ViT-Only Baseline   : 40.59%")
    print(f"Hybrid Baseline     : 41.58%")
    print(f"MIL Baseline        : 38.61%")
    print(f"Rel-Only Baseline   : 33.59%")
    print(f"Delta vs Hybrid     : {results['mean_top1_accuracy'] - 41.58:+.2f}%")
    
    print("\nPer-Class Breakdown:")
    for p in results["per_class_metrics"]:
        print(f"  {p['class_name']:18s}: Recall = {p['recall']:5.1f}% | Precision = {p['precision']:5.1f}%")
        
    print("\nAggregated Confusion Matrix (Row=True, Col=Pred):")
    cm = np.array(results["aggregated_confusion_matrix"])
    header = "  " + f"{'':18s}" + "".join([f"{c[:8]:>10s}" for c in classes])
    print(header)
    for r_idx, c_name in enumerate(classes):
        row_str = f"  {c_name:18s}" + "".join([f"{cm[r_idx, c_idx]:10d}" for c_idx in range(len(classes))])
        print(row_str)
        
    print("\nTop Learned Positive Feature Weights by Class:")
    for c_name, top_coefs in results["feature_importance_by_class"].items():
        pos_drivers = [f"{f} ({w:+.2f})" for f, w in top_coefs if w > 0][:3]
        print(f"  {c_name:18s}: {', '.join(pos_drivers)}")
        
    # Save outputs
    with open(OUTPUT_RESULTS_JSON, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved results to {OUTPUT_RESULTS_JSON.resolve()}")
    
    generate_html_report(results, OUTPUT_REPORT_HTML)
    print(f"Saved visual HTML report to {OUTPUT_REPORT_HTML.resolve()}")

if __name__ == '__main__':
    main()
