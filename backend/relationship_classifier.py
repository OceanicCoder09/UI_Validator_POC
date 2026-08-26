import os
import sys
import json
import pathlib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

EVIDENCE_JSON_PATH = pathlib.Path('backend/relationship_evidence_all_cases.json')
OUTPUT_RESULTS_JSON = pathlib.Path('backend/relationship_classifier_results.json')
OUTPUT_REPORT_HTML = pathlib.Path('backend/relationship_classifier_report.html')

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

def load_data():
    with open(EVIDENCE_JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    filtered = [c for c in data if c['gt_category'] in TARGET_CLASSES]
    classes = sorted(TARGET_CLASSES)
    
    X_list = []
    y_list = []
    case_meta = []
    
    for c in filtered:
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
        y_list.append(classes.index(c["gt_category"]))
        case_meta.append({
            "case_id": c["case_id"],
            "product": c["product"],
            "folder": c["folder"],
            "lang": c["lang"],
            "gt_category": c["gt_category"]
        })
        
    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int64), classes, case_meta

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

def evaluate_repeated_stratified_cv(X, y, classes, n_splits=3, n_repeats=10):
    num_classes = len(classes)
    top1_accuracies = []
    top2_accuracies = []
    agg_conf_matrix = np.zeros((num_classes, num_classes), dtype=int)
    all_coefficients = []
    
    for repeat in range(n_repeats):
        splits = get_stratified_folds(y, n_splits=n_splits, seed=42 + repeat * 13)
        for train_idx, test_idx in splits:
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]
            
            # Standardization computed ONLY on training split
            mean = np.mean(X_train, axis=0, keepdims=True)
            std = np.std(X_train, axis=0, keepdims=True)
            std[std < 1e-7] = 1.0
            
            X_train_scaled = (X_train - mean) / std
            X_test_scaled = (X_test - mean) / std
            
            # Multinomial Logistic Regression in PyTorch
            torch.manual_seed(42)
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
        
    mean_coef = np.mean(all_coefficients, axis=0) # (num_classes, num_features)
    
    feature_importance_by_class = {}
    for c_idx, c_name in enumerate(classes):
        coef_dict = {FEATURE_NAMES[f_idx]: round(float(mean_coef[c_idx, f_idx]), 4) for f_idx in range(len(FEATURE_NAMES))}
        sorted_coef = sorted(coef_dict.items(), key=lambda x: abs(x[1]), reverse=True)
        feature_importance_by_class[c_name] = sorted_coef
        
    return {
        "mean_top1_accuracy": round(mean_top1, 2),
        "std_top1_accuracy": round(std_top1, 2),
        "mean_top2_accuracy": round(mean_top2, 2),
        "std_top2_accuracy": round(std_top2, 2),
        "per_class_metrics": per_class_metrics,
        "aggregated_confusion_matrix": agg_conf_matrix.tolist(),
        "feature_importance_by_class": feature_importance_by_class,
        "n_evaluations_total": int(np.sum(agg_conf_matrix))
    }

    mean_top1 = float(np.mean(top1_accuracies))
    std_top1 = float(np.std(top1_accuracies))
    mean_top2 = float(np.mean(top2_accuracies))
    std_top2 = float(np.std(top2_accuracies))
    
    # Compute per-class recall and precision from aggregated confusion matrix
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
        
    # Average model coefficients across folds
    mean_coef = np.mean(all_coefficients, axis=0) # (num_classes, num_features)
    
    feature_importance_by_class = {}
    for c_idx, c_name in enumerate(classes):
        coef_dict = {FEATURE_NAMES[f_idx]: round(float(mean_coef[c_idx, f_idx]), 4) for f_idx in range(len(FEATURE_NAMES))}
        # Sort by absolute weight
        sorted_coef = sorted(coef_dict.items(), key=lambda x: abs(x[1]), reverse=True)
        feature_importance_by_class[c_name] = sorted_coef
        
    return {
        "mean_top1_accuracy": round(mean_top1, 2),
        "std_top1_accuracy": round(std_top1, 2),
        "mean_top2_accuracy": round(mean_top2, 2),
        "std_top2_accuracy": round(std_top2, 2),
        "per_class_metrics": per_class_metrics,
        "aggregated_confusion_matrix": agg_conf_matrix.tolist(),
        "feature_importance_by_class": feature_importance_by_class,
        "n_evaluations_total": int(np.sum(agg_conf_matrix))
    }

def generate_html_report(results, classes, output_path):
    cm = np.array(results["aggregated_confusion_matrix"])
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Relationship Evidence Classifier Evaluation</title>
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
  .coef-pos {{ color: #4ade80; font-family: monospace; }}
  .coef-neg {{ color: #f43f5e; font-family: monospace; }}
</style>
</head>
<body>
<h1>Relationship Evidence Classifier — Repeated Stratified 3-Fold CV (10 Repeats)</h1>
<div style="color: #94a3b8; font-size: 14px;">
  Evaluated on 101 benchmark cases across 5 core categories using compact physical relationship evidence with L2 regularized Logistic Regression.
</div>

<div class="metrics-banner">
  <div class="card">
    <div style="font-size: 14px; color: #94a3b8;">Mean Top-1 Accuracy</div>
    <div class="card-val">{results['mean_top1_accuracy']}%</div>
    <div class="card-sub">&plusmn; {results['std_top1_accuracy']}%</div>
  </div>
  <div class="card">
    <div style="font-size: 14px; color: #94a3b8;">Mean Top-2 Accuracy</div>
    <div class="card-val">{results['mean_top2_accuracy']}%</div>
    <div class="card-sub">&plusmn; {results['std_top2_accuracy']}%</div>
  </div>
  <div class="card">
    <div style="font-size: 14px; color: #94a3b8;">ViT+Evidence Baseline</div>
    <div class="card-val" style="color: #94a3b8;">41.58%</div>
    <div class="card-sub">Whole-screen hybrid baseline</div>
  </div>
  <div class="card">
    <div style="font-size: 14px; color: #94a3b8;">Total Fold Evaluations</div>
    <div class="card-val" style="color: #f8fafc;">{results['n_evaluations_total']}</div>
    <div class="card-sub">30 folds (10 repeats &times; 3 splits)</div>
  </div>
</div>

<h2>1. Per-Class Recall & Precision</h2>
<table>
  <thead>
    <tr>
      <th>Class Name</th>
      <th>Total GT Evaluations</th>
      <th>Correct</th>
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

<h2>2. Aggregated Confusion Matrix (Row = True GT, Col = Predicted)</h2>
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

<h2>3. Strongest Learned Logistic Regression Coefficients by Category</h2>
"""
    for c_name, top_coefs in results["feature_importance_by_class"].items():
        html += f"""
<h3 style="font-size:15px; color:#38bdf8; margin-top:18px;">Category: <code>{c_name}</code></h3>
<table>
  <thead>
    <tr>
      <th>Feature Name</th>
      <th>Mean Coefficient (Weight)</th>
      <th>Impact Direction</th>
    </tr>
  </thead>
  <tbody>
"""
        for feat_name, weight in top_coefs[:6]:
            cls_style = "coef-pos" if weight > 0 else "coef-neg"
            direction = "Increases probability (+)" if weight > 0 else "Decreases probability (-)"
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
    print("Loading compact relationship evidence features...", flush=True)
    X, y, classes, case_meta = load_data()
    print(f"Loaded {len(X)} cases across {len(classes)} classes with {X.shape[1]} features.")
    
    print("\nRunning Repeated Stratified 3-Fold Cross-Validation (10 Repeats = 30 total folds)...", flush=True)
    results = evaluate_repeated_stratified_cv(X, y, classes, n_splits=3, n_repeats=10)
    
    print(f"\n=======================================================")
    print(f"RELATIONSHIP EVIDENCE CLASSIFIER RESULTS (N = 101)")
    print(f"=======================================================")
    print(f"Mean Top-1 Accuracy : {results['mean_top1_accuracy']}%  (+/- {results['std_top1_accuracy']}%)")
    print(f"Mean Top-2 Accuracy : {results['mean_top2_accuracy']}%  (+/- {results['std_top2_accuracy']}%)")
    print(f"Previous Baseline   : 41.58% (Whole-Screen ViT+Evidence)")
    print(f"Delta vs Baseline   : {results['mean_top1_accuracy'] - 41.58:+.2f}%")
    
    print("\nPer-Class Recall:")
    for p in results["per_class_metrics"]:
        print(f"  {p['class_name']:18s}: Recall = {p['recall']:5.1f}% | Precision = {p['precision']:5.1f}%")
        
    print("\nAggregated Confusion Matrix (Row=True, Col=Pred):")
    cm = np.array(results["aggregated_confusion_matrix"])
    header = "  " + f"{'':18s}" + "".join([f"{c[:8]:>10s}" for c in classes])
    print(header)
    for r_idx, c_name in enumerate(classes):
        row_str = f"  {c_name:18s}" + "".join([f"{cm[r_idx, c_idx]:10d}" for c_idx in range(len(classes))])
        print(row_str)
        
    print("\nTop Learned Feature Coefficients (Strongest Positive Drivers):")
    for c_name, top_coefs in results["feature_importance_by_class"].items():
        pos_drivers = [f"{f} ({w:+.2f})" for f, w in top_coefs if w > 0][:3]
        print(f"  {c_name:18s}: {', '.join(pos_drivers)}")
        
    # Save JSON and HTML
    with open(OUTPUT_RESULTS_JSON, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved results to {OUTPUT_RESULTS_JSON.resolve()}")
    
    generate_html_report(results, classes, OUTPUT_REPORT_HTML)
    print(f"Saved visual HTML report to {OUTPUT_REPORT_HTML.resolve()}")

if __name__ == '__main__':
    main()
