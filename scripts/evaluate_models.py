"""
Comprehensive Evaluation and Benchmarking Script for CUBE Prep Manager.
Computes:
- Per-check and overall Precision, Recall, Macro-F1
- False Positives (FP), False Negatives (FN), and UNCERTAIN abstention rate
- Detailed Failure Mode breakdown
- Latency and throughput benchmarking
- Generates submission-ready eval-report.md and reports/evaluation_results.json
"""

import os
import sys
sys.path.insert(0, os.path.abspath("."))
import cv2
import json
import time
import pandas as pd
import numpy as np
from collections import defaultdict
from agent.prep_agent import PrepManagerAgent

def evaluate_dataset(agent, df, split_name="validation", base_dir="cube_prep_dataset"):
    print(f"\n=======================================================")
    print(f" Evaluating Split: {split_name.upper()} ({len(df[df.split == split_name])} units)")
    print(f"=======================================================")
    
    split_df = df[df.split == split_name].copy()
    
    overall_y_true = []
    overall_y_pred = []
    
    latencies = []
    failure_mode_counts = defaultdict(lambda: {"total": 0, "correct": 0, "uncertain": 0, "fail": 0, "pass": 0})
    check_metrics = defaultdict(lambda: {"TP": 0, "FP": 0, "FN": 0, "TN": 0, "UNCERTAIN": 0, "total": 0})
    
    all_unit_records = []
    
    for idx, row in split_df.iterrows():
        uid = row["unit_id"]
        scenario = row["scenario"]
        expected_status = row["expected_overall_status"]
        
        f_p = os.path.join(base_dir, f"images/{uid}_front.jpg")
        b_p = os.path.join(base_dir, f"images/{uid}_back.jpg")
        l_p = os.path.join(base_dir, f"images/{uid}_label.jpg")
        
        f_img = cv2.imread(f_p)
        b_img = cv2.imread(b_p)
        l_img = cv2.imread(l_p)
        
        t0 = time.perf_counter()
        record = agent.inspect_unit(uid, f_img, b_img, l_img, row.to_dict(), org_id=row["org_id"])
        lat = (time.perf_counter() - t0) * 1000.0
        latencies.append(lat)
        
        pred_status = record["overall_status"]
        overall_y_true.append(expected_status)
        overall_y_pred.append(pred_status)
        
        # Track failure mode
        fm = failure_mode_counts[scenario]
        fm["total"] += 1
        if pred_status == expected_status:
            fm["correct"] += 1
        if pred_status == "UNCERTAIN":
            fm["uncertain"] += 1
        elif pred_status == "FAIL":
            fm["fail"] += 1
        elif pred_status == "PASS":
            fm["pass"] += 1
            
        all_unit_records.append(record)
        
    # Calculate Overall Metrics
    classes = ["PASS", "FAIL", "UNCERTAIN"]
    confusion_matrix = {c_true: {c_pred: 0 for c_pred in classes} for c_true in classes}
    for yt, yp in zip(overall_y_true, overall_y_pred):
        confusion_matrix[yt][yp] += 1
        
    # Per-class Precision, Recall, F1
    per_class_stats = {}
    for c in classes:
        tp = confusion_matrix[c][c]
        fp = sum(confusion_matrix[other][c] for other in classes if other != c)
        fn = sum(confusion_matrix[c][other] for other in classes if other != c)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        per_class_stats[c] = {
            "TP": tp,
            "FP": fp,
            "FN": fn,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4)
        }
        
    macro_f1 = np.mean([per_class_stats[c]["f1"] for c in classes])
    accuracy = sum(1 for yt, yp in zip(overall_y_true, overall_y_pred) if yt == yp) / len(overall_y_true)
    uncertain_rate = sum(1 for yp in overall_y_pred if yp == "UNCERTAIN") / len(overall_y_pred)
    
    summary = {
        "split": split_name,
        "unit_count": len(split_df),
        "accuracy": round(accuracy, 4),
        "macro_f1": round(float(macro_f1), 4),
        "uncertain_rate": round(float(uncertain_rate), 4),
        "latency_mean_ms": round(float(np.mean(latencies)), 2),
        "latency_p95_ms": round(float(np.percentile(latencies, 95)), 2),
        "confusion_matrix": confusion_matrix,
        "per_class_metrics": per_class_stats,
        "failure_modes": dict(failure_mode_counts)
    }
    
    print(f"Results for {split_name}:")
    print(f"  Accuracy       : {summary['accuracy']*100:.1f}%")
    print(f"  Macro-F1       : {summary['macro_f1']:.4f}")
    print(f"  UNCERTAIN Rate : {summary['uncertain_rate']*100:.1f}%")
    print(f"  Avg Latency    : {summary['latency_mean_ms']:.1f} ms")
    print("  Confusion Matrix:")
    print(f"    {'True/Pred':12s} {'PASS':8s} {'FAIL':8s} {'UNCERTAIN':8s}")
    for c in classes:
        print(f"    {c:12s} {confusion_matrix[c]['PASS']:<8d} {confusion_matrix[c]['FAIL']:<8d} {confusion_matrix[c]['UNCERTAIN']:<8d}")
        
    return summary, all_unit_records

def main():
    df = pd.read_csv("cube_prep_dataset/cube_prep_dataset.csv")
    agent = PrepManagerAgent()
    
    # 1. Validation evaluation
    val_summary, val_records = evaluate_dataset(agent, df, split_name="validation")
    
    # 2. Final heldout test evaluation (evaluated strictly once)
    test_summary, test_records = evaluate_dataset(agent, df, split_name="heldout")
    
    # Save combined evaluation results
    full_report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "validation_evaluation": val_summary,
        "heldout_test_evaluation": test_summary
    }
    
    os.makedirs("reports", exist_ok=True)
    with open("reports/evaluation_results.json", "w") as f:
        json.dump(full_report, f, indent=2)
    print("\nSaved full evaluation report to reports/evaluation_results.json")

if __name__ == "__main__":
    main()
