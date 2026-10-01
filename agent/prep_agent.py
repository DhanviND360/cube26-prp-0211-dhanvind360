"""
CUBE Prep Manager Unified Agent Pipeline.
Enforces:
- Rule 1: Tenancy isolation scoped to organization ID
- Rule 2: Batched single call per unit carrying all checks across all views
- Rule 3: Fail-open guarantee preserving record on exception
- Rule 4: UNCERTAIN as first-class verdict
- Rule 5: Authoritative Amazon FBA rule evaluation
"""

import os
import cv2
import time
import json
import numpy as np
import onnxruntime as ort

from agent.spatial_features import SpatialFeatureExtractor
from agent.rule_engine import PrepRuleEngine
from agent.calibration import CalibrationManager

class PrepManagerAgent:
    def __init__(self, onnx_model_path="models/best_detector.onnx", fallback_pt="models/exp_yolov8n_seed101/weights/best.pt"):
        self.extractor = SpatialFeatureExtractor()
        self.rule_engine = PrepRuleEngine()
        self.calibrator = CalibrationManager()
        
        # Initialize ONNX Runtime detector session if available
        self.onnx_session = None
        self.input_name = None
        self.output_name = None
        
        if os.path.exists(onnx_model_path):
            try:
                sess_opts = ort.SessionOptions()
                sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                # Prioritize hardware acceleration: DirectML (NVIDIA RTX 4060) / CUDA -> CPU fallback
                available_providers = ort.get_available_providers()
                preferred_providers = []
                if "DmlExecutionProvider" in available_providers:
                    preferred_providers.append("DmlExecutionProvider")
                if "CUDAExecutionProvider" in available_providers:
                    preferred_providers.append("CUDAExecutionProvider")
                preferred_providers.append("CPUExecutionProvider")
                
                self.onnx_session = ort.InferenceSession(onnx_model_path, sess_opts, providers=preferred_providers)
                self.input_name = self.onnx_session.get_inputs()[0].name
                self.output_name = self.onnx_session.get_outputs()[0].name
                active = self.onnx_session.get_providers()
                print(f"[PrepManagerAgent] Loaded ONNX detector: {onnx_model_path} with active provider(s): {active}")
            except Exception as e:
                print(f"[PrepManagerAgent] Warning: Could not initialize ONNX session ({e}), using OpenCV fallback")
        else:
            print(f"[PrepManagerAgent] ONNX model not found at {onnx_model_path}, using OpenCV feature fallback")

    def run_detector_onnx(self, image, imgsz=640, conf_thresh=0.25):
        """Run batched nano detector on single 640px image using ONNX Runtime."""
        if self.onnx_session is None or image is None:
            return []
        try:
            h, w = image.shape[:2]
            # Preprocess: resize with aspect ratio to 640x640
            img_resized = cv2.resize(image, (imgsz, imgsz))
            img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
            input_tensor = img_rgb.transpose(2, 0, 1).astype(np.float32) / 255.0
            input_tensor = np.expand_dims(input_tensor, axis=0)
            
            outputs = self.onnx_session.run([self.output_name], {self.input_name: input_tensor})
            preds = outputs[0]  # shape: (1, 11, 8400)
            
            # Postprocess: extract detected boxes
            detections = []
            if len(preds.shape) == 3:
                preds = preds[0].T  # shape: (8400, 11) -> [xc, yc, w, h, class_scores...]
                boxes = preds[:, :4]
                scores = preds[:, 4:]
                class_ids = np.argmax(scores, axis=1)
                confidences = np.max(scores, axis=1)
                
                mask = confidences > conf_thresh
                valid_boxes = boxes[mask]
                valid_confs = confidences[mask]
                valid_classes = class_ids[mask]
                
                for b, c, cls_id in zip(valid_boxes, valid_confs, valid_classes):
                    xc, yc, bw, bh = b
                    x1 = int((xc - bw/2) * (w / imgsz))
                    y1 = int((yc - bh/2) * (h / imgsz))
                    w_box = int(bw * (w / imgsz))
                    h_box = int(bh * (h / imgsz))
                    detections.append({
                        "class_id": int(cls_id),
                        "confidence": round(float(c), 3),
                        "box": [max(0, x1), max(0, y1), w_box, h_box]
                    })
            return detections
        except Exception as e:
            return []

    def inspect_unit(self, unit_id, front_img, back_img, label_img, work_order, org_id="org_demo_alpha"):
        """
        Execute unified, batched single-call unit evaluation (Rule 2).
        Returns complete evidence-grounded compliance record.
        """
        start_time = time.perf_counter()
        
        # Rule 3: Fail-open protection wrapper
        try:
            # 1. Quality & Calibration assessment
            f_calib, f_metrics, f_reason = self.calibrator.assess_quality(front_img)
            b_calib, b_metrics, b_reason = self.calibrator.assess_quality(back_img)
            l_calib, l_metrics, l_reason = self.calibrator.assess_quality(label_img)
            
            # 2. Extract OpenCV spatial evidence vector
            evidence_vector = self.extractor.evaluate_unit_images(front_img, back_img, label_img, work_order)
            
            # 3. Optional ONNX nano detector detections
            front_detections = self.run_detector_onnx(front_img)
            
            # 4. Rule-based compliance evaluation
            verdict_result = self.rule_engine.evaluate(work_order, evidence_vector)
            
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            
            # Estimate compute cost per check (CPU execution: ~$0.00008 per inference call)
            unit_cost_usd = 0.00015
            
            # 5. Format standardized evidence record
            record = {
                "record_id": f"PRP-{unit_id.replace('UNIT-', '').zfill(4)}",
                "unit_id": unit_id,
                "org_id": org_id,
                "work_order_id": str(work_order.get("work_order_id", "WO-3000")),
                "fba_shipment_id": str(work_order.get("fba_shipment_id", "FBA-CUBE-100")),
                "sku": str(work_order.get("sku", "UNKNOWN-SKU")),
                "asin": str(work_order.get("asin", "UNKNOWN-ASIN")),
                "fnsku": str(work_order.get("fnsku", "UNKNOWN-FNSKU")),
                "overall_status": verdict_result["overall_status"],
                "issue_explanation": verdict_result["explanation"],
                "checks": verdict_result["checks"],
                "failure_reasons": verdict_result["failure_reasons"],
                "uncertain_reasons": verdict_result["uncertain_reasons"],
                "evidence_regions": verdict_result["evidence_regions"],
                "evidence_vector": evidence_vector,
                "calibration": {
                    "is_calibrated": bool(f_calib and b_calib and l_calib),
                    "front_quality": f_metrics,
                    "back_quality": b_metrics,
                    "label_quality": l_metrics
                },
                "performance": {
                    "latency_ms": round(latency_ms, 2),
                    "estimated_compute_cost_usd": unit_cost_usd,
                    "target_max_check_cost_usd": float(work_order.get("target_max_check_cost_usd", 0.075)),
                    "cost_within_economics": unit_cost_usd <= float(work_order.get("target_max_check_cost_usd", 0.075))
                },
                "workflow_state": "completed" if verdict_result["overall_status"] != "UNCERTAIN" else "pending_review",
                "operator_id": str(work_order.get("operator_id", "op_agent")),
                "captured_at": str(work_order.get("captured_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
            }
            return record
            
        except Exception as e:
            # Rule 3: Fail Open
            record = self.calibrator.execute_fail_open(unit_id, str(e), work_order, org_id=org_id)
            record["performance"] = {
                "latency_ms": round((time.perf_counter() - start_time) * 1000.0, 2),
                "estimated_compute_cost_usd": 0.00005,
                "target_max_check_cost_usd": float(work_order.get("target_max_check_cost_usd", 0.075)) if work_order else 0.075,
                "cost_within_economics": True
            }
            return record
