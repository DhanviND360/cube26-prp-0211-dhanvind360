"""
ONNX Export and Benchmark Script for CUBE Prep Manager.
Exports best PyTorch checkpoint to ONNX, runs ONNX Runtime validation,
and benchmarks inference speed/size.
"""

import os
import time
import json
import numpy as np
from ultralytics import YOLO
import onnxruntime as ort

def export_and_benchmark(best_weights_path="models/exp_yolov8n_seed101/weights/best.pt",
                         output_onnx_path="models/best_detector.onnx",
                         imgsz=640):
    print("=" * 60)
    print(" ONNX EXPORT & BENCHMARKING")
    print("=" * 60)
    
    if not os.path.exists(best_weights_path):
        # Fallback to other available weights if seed101 is not found
        for cand in ["models/exp_yolov8n_seed42/weights/best.pt", "models/exp_yolo11n_seed42/weights/best.pt"]:
            if os.path.exists(cand):
                best_weights_path = cand
                break
                
    print(f"Loading best checkpoint from: {best_weights_path}")
    model = YOLO(best_weights_path)
    
    # Export to ONNX
    print(f"Exporting to ONNX at {output_onnx_path} (input size: {imgsz}x{imgsz})...")
    exported_path = model.export(format="onnx", imgsz=imgsz, dynamic=False, simplify=True)
    
    if os.path.exists(exported_path) and os.path.abspath(exported_path) != os.path.abspath(output_onnx_path):
        import shutil
        os.makedirs(os.path.dirname(output_onnx_path), exist_ok=True)
        shutil.copy2(exported_path, output_onnx_path)
        actual_onnx = output_onnx_path
    else:
        actual_onnx = exported_path
        
    file_size_mb = os.path.getsize(actual_onnx) / (1024 * 1024)
    print(f"ONNX Model saved: {actual_onnx}")
    print(f"Model file size : {file_size_mb:.2f} MB")
    
    # ONNX Runtime Benchmark
    print("\nInitializing ONNX Runtime inference session...")
    sess_options = ort.SessionOptions()
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    sess_options.intra_op_num_threads = 4
    
    session = ort.InferenceSession(actual_onnx, sess_options, providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name
    
    print(f"Input Name: {input_name}, Shape: {session.get_inputs()[0].shape}")
    print(f"Output Name: {output_name}, Shape: {session.get_outputs()[0].shape}")
    
    # Warmup
    dummy_input = np.zeros((1, 3, imgsz, imgsz), dtype=np.float32)
    for _ in range(5):
        _ = session.run([output_name], {input_name: dummy_input})
        
    # Latency Benchmark over 30 runs
    latencies = []
    for _ in range(30):
        t0 = time.perf_counter()
        _ = session.run([output_name], {input_name: dummy_input})
        latencies.append((time.perf_counter() - t0) * 1000.0)
        
    avg_latency = np.mean(latencies)
    p95_latency = np.percentile(latencies, 95)
    fps = 1000.0 / avg_latency
    
    print(f"\n--- ONNX Runtime Performance ---")
    print(f"  Average Latency: {avg_latency:.2f} ms")
    print(f"  P95 Latency    : {p95_latency:.2f} ms")
    print(f"  Throughput     : {fps:.1f} inferences/sec")
    
    bench_data = {
        "model_file": actual_onnx,
        "file_size_mb": round(file_size_mb, 2),
        "input_resolution": [imgsz, imgsz],
        "execution_provider": "CPUExecutionProvider",
        "avg_latency_ms": round(float(avg_latency), 2),
        "p95_latency_ms": round(float(p95_latency), 2),
        "throughput_fps": round(float(fps), 2)
    }
    
    os.makedirs("reports", exist_ok=True)
    with open("reports/onnx_benchmark.json", "w") as f:
        json.dump(bench_data, f, indent=2)
    print("Benchmark saved to reports/onnx_benchmark.json")
    return bench_data

if __name__ == "__main__":
    export_and_benchmark()
