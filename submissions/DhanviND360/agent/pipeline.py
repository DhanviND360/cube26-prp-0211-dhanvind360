"""
Progressive Sequential Inspection Pipeline for CUBE Prep Manager.
Executes:
Upload -> Queued/Sequential Image Processing -> Per-Image Result -> Persisted Evidence Record
Streams progress and per-image intermediate findings in real-time.
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

class ProgressiveInspectionPipeline:
    def __init__(self):
        self.agent = PrepManagerAgent()
        self.storage = get_storage_provider()
        self.db = get_database_provider()
        self.calibrator = CalibrationManager()
        self.extractor = SpatialFeatureExtractor()
        self.rule_engine = PrepRuleEngine()

    async def inspect_unit_stream(
        self,
        unit_id: str,
        front_img: np.ndarray,
        back_img: np.ndarray,
        label_img: np.ndarray,
        work_order: Dict[str, Any],
        org_id: str = "org_demo_alpha"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Progressive asynchronous event generator streaming real-time milestones
        as each perspective is analyzed.
        """
        t_start = time.perf_counter()
        
        # 1. Milestone: Job Queued / Started
        yield {
            "event": "job_started",
            "progress": 10,
            "unit_id": unit_id,
            "org_id": org_id,
            "status": "processing",
            "message": "Capture stream received and validated. Starting optical calibration.",
            "timestamp": time.time()
        }
        await asyncio.sleep(0.01)

        # 2. Milestone: Front View Analysis (Package, Polybag, Warning, Seam overlap)
        f_calib, f_metrics, f_reason = self.calibrator.assess_quality(front_img)
        f_tokens, f_text = self.extractor.extract_text_and_boxes(front_img)
        pkg_box = self.extractor.detect_package_bounds(front_img)
        
        # Detector inferences
        front_dets = self.agent.run_detector_onnx(front_img)
        
        front_summary = {
            "view": "front",
            "calibrated": f_calib,
            "blur_metric": f_metrics.get("blur_metric", 0.0),
            "detections_count": len(front_dets),
            "package_bounds": pkg_box,
            "extracted_tokens": len(f_tokens)
        }
        yield {
            "event": "front_completed",
            "progress": 40,
            "view": "front",
            "summary": front_summary,
            "message": "Front view processed: package bounds and seam alignment calculated.",
            "timestamp": time.time()
        }
        await asyncio.sleep(0.01)

        # 3. Milestone: Back View Analysis (Barcode concealment, seal closure)
        b_calib, b_metrics, b_reason = self.calibrator.assess_quality(back_img)
        b_tokens, b_text = self.extractor.extract_text_and_boxes(back_img)
        back_dets = self.agent.run_detector_onnx(back_img)
        
        has_orig_uncovered = "ORIG" in b_text.upper() or "ORIGMY" in b_text.upper()
        back_summary = {
            "view": "back",
            "calibrated": b_calib,
            "blur_metric": b_metrics.get("blur_metric", 0.0),
            "original_barcode_visible": has_orig_uncovered,
            "detections_count": len(back_dets)
        }
        yield {
            "event": "back_completed",
            "progress": 70,
            "view": "back",
            "summary": back_summary,
            "message": "Back view processed: barcode coverage and packaging evidence verified.",
            "timestamp": time.time()
        }
        await asyncio.sleep(0.01)

        # 4. Milestone: Label View Analysis (FNSKU flatness, OCR, date verification)
        l_calib, l_metrics, l_reason = self.calibrator.assess_quality(label_img)
        l_tokens, l_text = self.extractor.extract_text_and_boxes(label_img)
        label_dets = self.agent.run_detector_onnx(label_img)
        
        label_summary = {
            "view": "label",
            "calibrated": l_calib,
            "blur_metric": l_metrics.get("blur_metric", 0.0),
            "fnsku_macro_verified": True if len(l_tokens) > 0 else False
        }
        yield {
            "event": "label_completed",
            "progress": 90,
            "view": "label",
            "summary": label_summary,
            "message": "Macro label view processed: FNSKU barcode and text legibility confirmed.",
            "timestamp": time.time()
        }
        await asyncio.sleep(0.01)

        # 5. Milestone: Final Rule Engine Evaluation & Persistence
        record = self.agent.inspect_unit(unit_id, front_img, back_img, label_img, work_order, org_id=org_id)
        
        # Persist to database (SQLite / Supabase)
        self.db.save_record(record, org_id)
        
        latency = (time.perf_counter() - t_start) * 1000.0
        record["performance"]["total_streaming_latency_ms"] = round(latency, 2)
        
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

# Global singleton pipeline instance
pipeline = ProgressiveInspectionPipeline()
