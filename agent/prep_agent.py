"""
CUBE Prep Manager Unified Agent Pipeline.

Core inspection engine that:
- Runs ONNX object detection on all views
- Integrates detector outputs into the evidence pipeline
- Caches intermediate results to avoid duplicate processing
- Produces PASS / FAIL / UNCERTAIN verdicts from image evidence

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
import numpy as np
import onnxruntime as ort

from agent.spatial_features import SpatialFeatureExtractor
from agent.rule_engine import PrepRuleEngine
from agent.calibration import CalibrationManager

# ONNX model class labels
ONNX_CLASS_NAMES = ["package", "polybag", "fnsku", "warning", "barcode", "expiry", "handling_mark"]


class PrepManagerAgent:
    def __init__(self, onnx_model_path="models/best_detector.onnx"):
        self.extractor = SpatialFeatureExtractor()
        self.rule_engine = PrepRuleEngine()
        self.calibrator = CalibrationManager()

        # Initialize ONNX Runtime detector session
        self.onnx_session = None
        self.input_name = None
        self.output_name = None
        self._model_load_error = None

        if os.path.exists(onnx_model_path):
            try:
                sess_opts = ort.SessionOptions()
                sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                sess_opts.intra_op_num_threads = min(4, os.cpu_count() or 2)

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
                print(f"[PrepManagerAgent] ONNX detector loaded: {onnx_model_path} providers={active}")
            except Exception as e:
                self._model_load_error = str(e)
                print(f"[PrepManagerAgent] Warning: ONNX init failed ({e}), using OpenCV-only fallback")
        else:
            print(f"[PrepManagerAgent] ONNX model not found at {onnx_model_path}, using OpenCV-only fallback")

    def run_detector_onnx(self, image, imgsz=640, conf_thresh=0.25):
        """
        Run ONNX nano detector on a single image.
        Returns list of detections: [{"class_id": int, "class_name": str, "confidence": float, "box": [x,y,w,h]}]
        """
        if self.onnx_session is None or image is None or image.size == 0:
            return []
        try:
            h, w = image.shape[:2]
            # Preprocess: resize to 640x640 (letterbox would be better but this matches training)
            img_resized = cv2.resize(image, (imgsz, imgsz))
            img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
            input_tensor = img_rgb.transpose(2, 0, 1).astype(np.float32) / 255.0
            input_tensor = np.expand_dims(input_tensor, axis=0)

            outputs = self.onnx_session.run([self.output_name], {self.input_name: input_tensor})
            preds = outputs[0]  # shape: (1, num_classes+4, num_anchors) e.g. (1, 11, 8400)

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

                # Apply NMS per class
                if len(valid_boxes) > 0:
                    # Convert to xyxy for NMS
                    scale_x = w / imgsz
                    scale_y = h / imgsz
                    nms_boxes = []
                    for b in valid_boxes:
                        xc, yc, bw, bh = b
                        x1 = (xc - bw / 2) * scale_x
                        y1 = (yc - bh / 2) * scale_y
                        x2 = (xc + bw / 2) * scale_x
                        y2 = (yc + bh / 2) * scale_y
                        nms_boxes.append([x1, y1, x2, y2])

                    nms_boxes_arr = np.array(nms_boxes, dtype=np.float32)
                    indices = cv2.dnn.NMSBoxes(
                        nms_boxes_arr.tolist(),
                        valid_confs.tolist(),
                        conf_thresh,
                        0.45  # NMS IoU threshold
                    )

                    if len(indices) > 0:
                        indices = indices.flatten() if hasattr(indices, 'flatten') else indices
                        for idx in indices:
                            x1, y1, x2, y2 = nms_boxes_arr[idx]
                            cls_id = int(valid_classes[idx])
                            cls_name = ONNX_CLASS_NAMES[cls_id] if cls_id < len(ONNX_CLASS_NAMES) else f"class_{cls_id}"
                            detections.append({
                                "class_id": cls_id,
                                "class_name": cls_name,
                                "confidence": round(float(valid_confs[idx]), 3),
                                "box": [max(0, int(x1)), max(0, int(y1)),
                                        max(1, int(x2 - x1)), max(1, int(y2 - y1))]
                            })

            return detections
        except Exception as e:
            return []

    def inspect_unit(self, unit_id, front_img, back_img, label_img, work_order,
                     org_id="org_demo_alpha",
                     cached_ocr=None,
                     cached_detections=None,
                     cached_calibration=None):
        """
        Execute unified, batched single-call unit evaluation (Rule 2).

        Accepts optional cached results from pipeline streaming to avoid
        redundant OCR / detection / calibration.

        Returns complete evidence-grounded compliance record.
        """
        start_time = time.perf_counter()

        # Rule 3: Fail-open protection wrapper
        try:
            # Unreadable or missing image stream -> immediately fail open
            for view_name, img in [("front", front_img), ("back", back_img), ("label", label_img)]:
                if img is None or (isinstance(img, np.ndarray) and img.size == 0):
                    record = self.calibrator.execute_fail_open(
                        unit_id, f"Unreadable or missing {view_name} image stream", work_order, org_id=org_id
                    )
                    record["performance"] = {
                        "latency_ms": round((time.perf_counter() - start_time) * 1000.0, 2),
                        "detection_latency_ms": 0.0,
                        "evidence_latency_ms": 0.0,
                        "rule_latency_ms": 0.0,
                        "estimated_compute_cost_usd": 0.00005,
                        "target_max_check_cost_usd": float(work_order.get("target_max_check_cost_usd", 0.075)) if work_order else 0.075,
                        "cost_within_economics": True
                    }
                    return record

            # ── 1. Calibration & Quality (reuse cached or compute) ──
            if cached_calibration:
                f_calib, f_metrics, f_reason = cached_calibration["front"]
                b_calib, b_metrics, b_reason = cached_calibration["back"]
                l_calib, l_metrics, l_reason = cached_calibration["label"]
            else:
                f_calib, f_metrics, f_reason = self.calibrator.assess_quality(front_img)
                b_calib, b_metrics, b_reason = self.calibrator.assess_quality(back_img)
                l_calib, l_metrics, l_reason = self.calibrator.assess_quality(label_img)

            # ── 2. ONNX Detection (reuse cached or compute) ──
            t_det_start = time.perf_counter()
            if cached_detections:
                front_dets = cached_detections.get("front", [])
                back_dets = cached_detections.get("back", [])
                label_dets = cached_detections.get("label", [])
            else:
                front_dets = self.run_detector_onnx(front_img)
                back_dets = self.run_detector_onnx(back_img)
                label_dets = self.run_detector_onnx(label_img)
            det_latency_ms = (time.perf_counter() - t_det_start) * 1000.0

            # ── 3. Evidence extraction (passes ONNX detections downstream) ──
            t_evidence_start = time.perf_counter()
            evidence_vector = self.extractor.evaluate_unit_images(
                front_img, back_img, label_img, work_order,
                onnx_detections_front=front_dets,
                onnx_detections_back=back_dets,
                onnx_detections_label=label_dets,
                cached_ocr=cached_ocr
            )
            evidence_latency_ms = (time.perf_counter() - t_evidence_start) * 1000.0

            # ── 4. Rule-based compliance evaluation ──
            t_rule_start = time.perf_counter()
            verdict_result = self.rule_engine.evaluate(work_order, evidence_vector)
            rule_latency_ms = (time.perf_counter() - t_rule_start) * 1000.0

            total_latency_ms = (time.perf_counter() - start_time) * 1000.0

            # Estimate compute cost (CPU: ~$0.00008/inference, 3 views + OCR)
            unit_cost_usd = 0.00015

            # ── 5. ONNX detection summary for evidence ──
            detection_summary = {
                "front": [{"class": d["class_name"], "conf": d["confidence"]} for d in front_dets[:10]],
                "back": [{"class": d["class_name"], "conf": d["confidence"]} for d in back_dets[:10]],
                "label": [{"class": d["class_name"], "conf": d["confidence"]} for d in label_dets[:10]],
                "total_detections": len(front_dets) + len(back_dets) + len(label_dets)
            }

            # ── 6. Format standardized evidence record ──
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
                "onnx_detections": detection_summary,
                "calibration": {
                    "is_calibrated": bool(f_calib and b_calib and l_calib),
                    "front_quality": f_metrics,
                    "back_quality": b_metrics,
                    "label_quality": l_metrics
                },
                "performance": {
                    "latency_ms": round(total_latency_ms, 2),
                    "detection_latency_ms": round(det_latency_ms, 2),
                    "evidence_latency_ms": round(evidence_latency_ms, 2),
                    "rule_latency_ms": round(rule_latency_ms, 2),
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
                "detection_latency_ms": 0.0,
                "evidence_latency_ms": 0.0,
                "rule_latency_ms": 0.0,
                "estimated_compute_cost_usd": 0.00005,
                "target_max_check_cost_usd": float(work_order.get("target_max_check_cost_usd", 0.075)) if work_order else 0.075,
                "cost_within_economics": True
            }
            return record
