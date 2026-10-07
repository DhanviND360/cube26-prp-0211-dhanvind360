"""
Progressive Sequential Inspection Pipeline for CUBE Prep Manager.

Executes:
Upload -> Queued/Sequential Image Processing -> Per-Image Result -> Persisted Evidence Record

Key improvements:
- Caches OCR, detection, and calibration results from streaming milestones
- Passes cached results to inspect_unit() to eliminate duplicate processing
- Streams real-time progress while building evidence incrementally
"""

import os
import cv2
import time
import json
import asyncio
import numpy as np
from typing import AsyncGenerator, Dict, Any, Optional

from agent.prep_agent import PrepManagerAgent
from agent.spatial_features import SpatialFeatureExtractor
from agent.rule_engine import PrepRuleEngine
from agent.calibration import CalibrationManager
from agent.storage import get_storage_provider
from agent.db import get_database_provider
from agent.metrics import metrics_tracker


class ProgressiveInspectionPipeline:
    def __init__(self):
        self.agent = PrepManagerAgent()
        self.storage = get_storage_provider()
        self.db = get_database_provider()
        self.calibrator = CalibrationManager()
        self.extractor = SpatialFeatureExtractor()
        self.rule_engine = PrepRuleEngine()
        self.partial_states: Dict[str, Dict[str, Any]] = {}

    def get_partial_state(self, unit_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve intermediate findings for disconnected or polling clients."""
        return self.partial_states.get(unit_id)

    async def inspect_unit_stream(
        self,
        unit_id: str,
        front_img: Optional[np.ndarray],
        back_img: Optional[np.ndarray],
        label_img: Optional[np.ndarray],
        work_order: Dict[str, Any],
        org_id: str = "org_demo_alpha",
        timeout_seconds: float = 20.0
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Progressive asynchronous event generator streaming real-time milestones.

        Caches ALL intermediate results (calibration, OCR, ONNX detections)
        and passes them to inspect_unit() so nothing is recomputed.
        """
        metrics_tracker.record_start()
        t_start = time.perf_counter()
        view_latencies: Dict[str, float] = {}

        # Cache containers for intermediate results
        cached_calibration = {}
        cached_ocr = {}
        cached_detections = {}

        # Initialize partial state
        self.partial_states[unit_id] = {
            "unit_id": unit_id,
            "org_id": org_id,
            "status": "processing",
            "progress": 10,
            "started_at": time.time(),
            "milestones": {}
        }

        try:
            # 1. Milestone: Job Queued / Started
            start_event = {
                "event": "job_started",
                "progress": 10,
                "unit_id": unit_id,
                "org_id": org_id,
                "status": "processing",
                "message": "Capture stream received and validated. Starting optical calibration.",
                "timestamp": time.time()
            }
            yield start_event
            await asyncio.sleep(0.005)

            # Validate input matrices early
            if front_img is None or back_img is None or label_img is None:
                raise ValueError(f"One or more required image perspectives are missing or corrupted for {unit_id}")

            # 2. Milestone: Front View Analysis
            t_front_0 = time.perf_counter()
            f_calib, f_metrics, f_reason = self.calibrator.assess_quality(front_img)
            cached_calibration["front"] = (f_calib, f_metrics, f_reason)

            f_tokens, f_text = await asyncio.to_thread(self.extractor.extract_text_and_boxes, front_img)
            cached_ocr["front_tokens"] = f_tokens
            cached_ocr["front_text"] = f_text

            pkg_box = await asyncio.to_thread(self.extractor.detect_package_bounds, front_img)
            front_dets = await asyncio.to_thread(self.agent.run_detector_onnx, front_img)
            cached_detections["front"] = front_dets

            t_front_ms = round((time.perf_counter() - t_front_0) * 1000.0, 2)
            view_latencies["front"] = t_front_ms

            front_summary = {
                "view": "front",
                "calibrated": f_calib,
                "blur_metric": f_metrics.get("blur_metric", 0.0),
                "detections_count": len(front_dets),
                "detections": [{"class": d["class_name"], "conf": d["confidence"]} for d in front_dets[:5]],
                "package_bounds": pkg_box,
                "extracted_tokens": len(f_tokens),
                "latency_ms": t_front_ms
            }
            self.partial_states[unit_id]["progress"] = 40
            self.partial_states[unit_id]["milestones"]["front"] = front_summary

            yield {
                "event": "front_completed",
                "progress": 40,
                "view": "front",
                "summary": front_summary,
                "message": "Front view processed: package bounds and FNSKU alignment calculated.",
                "timestamp": time.time()
            }
            await asyncio.sleep(0.005)

            # 3. Milestone: Back View Analysis
            t_back_0 = time.perf_counter()
            b_calib, b_metrics, b_reason = self.calibrator.assess_quality(back_img)
            cached_calibration["back"] = (b_calib, b_metrics, b_reason)

            b_tokens, b_text = await asyncio.to_thread(self.extractor.extract_text_and_boxes, back_img)
            cached_ocr["back_tokens"] = b_tokens
            cached_ocr["back_text"] = b_text

            back_dets = await asyncio.to_thread(self.agent.run_detector_onnx, back_img)
            cached_detections["back"] = back_dets

            # Barcode detection for original barcode check
            b_barcodes = await asyncio.to_thread(self.extractor.detect_barcodes, back_img)

            t_back_ms = round((time.perf_counter() - t_back_0) * 1000.0, 2)
            view_latencies["back"] = t_back_ms

            back_summary = {
                "view": "back",
                "calibrated": b_calib,
                "blur_metric": b_metrics.get("blur_metric", 0.0),
                "barcodes_decoded": len(b_barcodes),
                "detections_count": len(back_dets),
                "latency_ms": t_back_ms
            }
            self.partial_states[unit_id]["progress"] = 70
            self.partial_states[unit_id]["milestones"]["back"] = back_summary

            yield {
                "event": "back_completed",
                "progress": 70,
                "view": "back",
                "summary": back_summary,
                "message": "Back view processed: barcode coverage and packaging evidence verified.",
                "timestamp": time.time()
            }
            await asyncio.sleep(0.005)

            # 4. Milestone: Label View Analysis
            t_label_0 = time.perf_counter()
            l_calib, l_metrics, l_reason = self.calibrator.assess_quality(label_img)
            cached_calibration["label"] = (l_calib, l_metrics, l_reason)

            l_tokens, l_text = await asyncio.to_thread(self.extractor.extract_text_and_boxes, label_img)
            cached_ocr["label_tokens"] = l_tokens
            cached_ocr["label_text"] = l_text

            label_dets = await asyncio.to_thread(self.agent.run_detector_onnx, label_img)
            cached_detections["label"] = label_dets

            t_label_ms = round((time.perf_counter() - t_label_0) * 1000.0, 2)
            view_latencies["label"] = t_label_ms

            label_summary = {
                "view": "label",
                "calibrated": l_calib,
                "blur_metric": l_metrics.get("blur_metric", 0.0),
                "fnsku_tokens_found": len([t for t in l_tokens if "X00" in t.get("text", "").upper()
                                           or "FNSKU" in t.get("text", "").upper()]),
                "detections_count": len(label_dets),
                "latency_ms": t_label_ms
            }
            self.partial_states[unit_id]["progress"] = 90
            self.partial_states[unit_id]["milestones"]["label"] = label_summary

            yield {
                "event": "label_completed",
                "progress": 90,
                "view": "label",
                "summary": label_summary,
                "message": "Macro label view processed: FNSKU barcode and text legibility analyzed.",
                "timestamp": time.time()
            }
            await asyncio.sleep(0.005)

            # 5. Milestone: Final Rule Engine Evaluation & Persistence
            # Pass ALL cached results to avoid re-running OCR/detection/calibration
            record = await asyncio.to_thread(
                self.agent.inspect_unit,
                unit_id,
                front_img,
                back_img,
                label_img,
                work_order,
                org_id=org_id,
                cached_ocr=cached_ocr,
                cached_detections=cached_detections,
                cached_calibration=cached_calibration
            )

            total_streaming_latency_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
            record["performance"]["total_streaming_latency_ms"] = total_streaming_latency_ms

            # Persist to database (SQLite / Supabase)
            self.db.save_record(record, org_id)

            # Update partial / final cache
            self.partial_states[unit_id]["progress"] = 100
            self.partial_states[unit_id]["status"] = "completed"
            self.partial_states[unit_id]["record"] = record

            # Telemetry tracking
            metrics_tracker.record_finish(
                unit_id=unit_id,
                org_id=org_id,
                verdict=record["overall_status"],
                total_latency_ms=total_streaming_latency_ms,
                view_latencies=view_latencies,
                cost_usd=record["performance"].get("estimated_compute_cost_usd", 0.00015)
            )

            yield {
                "event": "inspection_completed",
                "progress": 100,
                "unit_id": unit_id,
                "org_id": org_id,
                "overall_status": record["overall_status"],
                "issue_explanation": record["issue_explanation"],
                "record": record,
                "message": f"Compliance inspection completed with verdict: {record['overall_status']}.",
                "timestamp": time.time()
            }

        except Exception as e:
            # Rule 3: Fail Open Guarantee
            err_msg = str(e)
            metrics_tracker.record_error(unit_id, org_id, err_msg)

            # Generate contract-compliant fail-open record
            fail_open_record = self.calibrator.execute_fail_open(unit_id, err_msg, work_order, org_id=org_id)
            elapsed_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
            fail_open_record["performance"]["latency_ms"] = elapsed_ms
            fail_open_record["performance"]["total_streaming_latency_ms"] = elapsed_ms

            # Save fail-open record to database
            self.db.save_record(fail_open_record, org_id)

            self.partial_states[unit_id]["progress"] = 100
            self.partial_states[unit_id]["status"] = "fail_open"
            self.partial_states[unit_id]["record"] = fail_open_record

            metrics_tracker.record_finish(
                unit_id=unit_id,
                org_id=org_id,
                verdict="UNCERTAIN",
                total_latency_ms=elapsed_ms,
                view_latencies=view_latencies,
                cost_usd=0.00005
            )

            yield {
                "event": "inspection_completed",
                "progress": 100,
                "unit_id": unit_id,
                "org_id": org_id,
                "overall_status": "UNCERTAIN",
                "issue_explanation": f"Fail-open condition triggered: {err_msg}",
                "record": fail_open_record,
                "message": "Inspection completed under fail-open guarantee (UNCERTAIN - pending manual review).",
                "timestamp": time.time()
            }

# Global singleton pipeline instance
pipeline = ProgressiveInspectionPipeline()
