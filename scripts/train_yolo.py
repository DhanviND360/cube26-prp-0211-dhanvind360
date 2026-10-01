"""
Training and Experimentation Pipeline for CUBE Prep Manager YOLO Detectors.
Features:
- Transfer learning from pretrained YOLO11n and YOLOv8n
- Frozen-backbone warmup support
- Early stopping & validation checkpointing
- Evaluation on validation set (mAP, macro-F1, per-class recall)
- Controlled experiments comparing seeds and augmentations
- Export of best checkpoint to ONNX format
"""

import os
import json
import time
from ultralytics import YOLO

def run_experiment(model_type="yolov8n.pt", experiment_name="exp_yolov8n_seed42", seed=42, epochs=6, imgsz=640, freeze=10):
    print(f"\n=======================================================")
    print(f" Starting Experiment: {experiment_name}")
    print(f" Model: {model_type} | Seed: {seed} | Epochs: {epochs} | ImgSz: {imgsz}")
    print(f"=======================================================")
    
    data_yaml = os.path.abspath("data/yolo_dataset/data.yaml")
    
    model = YOLO(model_type)
    
    start_time = time.time()
    results = model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=16,
        seed=seed,
        freeze=freeze,
        patience=4,
        device="cpu",
        project="models",
        name=experiment_name,
        exist_ok=True,
        verbose=False,
        plots=True
    )
    training_duration = time.time() - start_time
    
    # Run validation on the validation set (kept separate from test set)
    val_results = model.val(data=data_yaml, split="val", imgsz=imgsz, device="cpu", verbose=False)
    
    # Extract validation metrics
    metrics = {
        "experiment_name": experiment_name,
        "model_type": model_type,
        "seed": seed,
        "epochs": epochs,
        "training_duration_sec": round(training_duration, 2),
        "map50": round(float(val_results.box.map50), 4),
        "map50_95": round(float(val_results.box.map), 4),
        "mp": round(float(val_results.box.mp), 4),
        "mr": round(float(val_results.box.mr), 4),
    }
    
    # Calculate Macro-F1 from mean precision and mean recall
    p = metrics["mp"]
    r = metrics["mr"]
    f1 = (2 * p * r / (p + r)) if (p + r) > 0 else 0.0
    metrics["val_macro_f1"] = round(f1, 4)
    
    # Per-class recall
    class_names = ["package", "polybag", "fnsku", "warning", "barcode", "expiry", "handling_mark"]
    per_class_recalls = {}
    if hasattr(val_results.box, "r") and len(val_results.box.r) == len(class_names):
        for idx, name in enumerate(class_names):
            per_class_recalls[name] = round(float(val_results.box.r[idx]), 4)
    metrics["per_class_recall"] = per_class_recalls
    
    # Save best checkpoint path
    best_weights = os.path.join("models", experiment_name, "weights", "best.pt")
    metrics["weights_path"] = best_weights
    
    print(f"Validation Completed:")
    print(f"  mAP@50     : {metrics['map50']:.4f}")
    print(f"  Mean Prec  : {metrics['mp']:.4f}")
    print(f"  Mean Recall: {metrics['mr']:.4f}")
    print(f"  Macro-F1   : {metrics['val_macro_f1']:.4f}")
    print(f"  Per-class recall: {per_class_recalls}")
    
    return model, metrics

def export_model_to_onnx(model, save_path="models/best_detector.onnx", imgsz=640):
    print(f"\nExporting best model to ONNX format at {save_path}...")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    onnx_file = model.export(format="onnx", imgsz=imgsz, dynamic=False, simplify=True)
    if os.path.exists(onnx_file):
        # Move or rename if needed
        if os.path.abspath(onnx_file) != os.path.abspath(save_path):
            import shutil
            shutil.copy2(onnx_file, save_path)
        print(f"ONNX export succeeded: {save_path} (size: {os.path.getsize(save_path)/(1024*1024):.2f} MB)")
        return save_path
    return onnx_file

def main():
    experiments = []
    
    # Experiment 1: YOLOv8n baseline (seed 42)
    m1, res1 = run_experiment("yolov8n.pt", "exp_yolov8n_seed42", seed=42, epochs=5, imgsz=640, freeze=10)
    experiments.append(res1)
    
    # Experiment 2: YOLO11n (seed 42)
    m2, res2 = run_experiment("yolo11n.pt", "exp_yolo11n_seed42", seed=42, epochs=5, imgsz=640, freeze=10)
    experiments.append(res2)
    
    # Experiment 3: Controlled seed variation (seed 101)
    m3, res3 = run_experiment("yolov8n.pt", "exp_yolov8n_seed101", seed=101, epochs=5, imgsz=640, freeze=8)
    experiments.append(res3)
    
    # Select best model based on validation macro-F1 + per-class recall
    best_exp = max(experiments, key=lambda x: (x["val_macro_f1"], x["mr"]))
    print("\n" + "=" * 60)
    print(f" BEST MODEL SELECTED: {best_exp['experiment_name']}")
    print(f" Validation Macro-F1: {best_exp['val_macro_f1']:.4f} | Recall: {best_exp['mr']:.4f}")
    print("=" * 60)
    
    # Export best model to ONNX
    best_model = YOLO(best_exp["weights_path"])
    export_model_to_onnx(best_model, "models/best_detector.onnx")
    
    # Save experiments report
    os.makedirs("reports", exist_ok=True)
    report_data = {
        "best_experiment": best_exp["experiment_name"],
        "selection_criteria": "Validation Macro-F1 + Mean Recall (test set untouched)",
        "experiments": experiments
    }
    with open("reports/model_experiments.json", "w") as f:
        json.dump(report_data, f, indent=2)
    print("Saved experiment results to reports/model_experiments.json")

if __name__ == "__main__":
    main()
