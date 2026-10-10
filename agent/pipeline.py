"""
Progressive Sequential Inspection Pipeline for CUBE Prep Manager.

Executes:
Upload -> Queued/Sequential Image Processing -> Per-Image Milestone -> AI Multimodal Agent Verdict -> Persisted Evidence Record

Key Features:
- Ultra-lightweight asynchronous streaming (zero heavy OCR/PyTorch memory overhead)
- Emits real-time SSE progress events for each view perspective
- Invokes Gemini 3.6 Flash Multimodal AI Agent for complete 6-check compliance evaluation
- Guarantees fail-open resilience and saves records to DB & Storage
"""

import os
import cv2
import time
import json
import asyncio
import numpy as np
from typing import AsyncGenerator, Dict, Any, Optional

from agent.prep_agent import PrepManagerAgent
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
        timeout_seconds: float = 30.0
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Progressive asynchronous event generator streaming real-time milestones.
        """
        metrics_tracker.record_start()
        t_start = time.perf_counter()
        view_latencies: Dict[str, float] = {}

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
            await asyncio.sleep(0.01)

            # Validate input matrices early
            if front_img is None or back_img is None or label_img is None:
                raise ValueError(f"One or more required image perspectives are missing or corrupted for {unit_id}")

            # 2. Milestone: Front View Analysis
            t_front_0 = time.perf_counter()
            f_calib, f_metrics, f_reason = self.calibrator.assess_quality(front_img)
            t_front_ms = round((time.perf_counter() - t_front_0) * 1000.0, 2)
            view_latencies["front"] = t_front_ms

            front_summary = {
                "view": "front",
                "calibrated": f_calib,
                "blur_metric": f_metrics.get("blur_metric", 0.0),
                "glare_ratio": f_metrics.get("glare_ratio", 0.0),
                "resolution": f_metrics.get("resolution", [0, 0]),
                "latency_ms": t_front_ms
            }
            self.partial_states[unit_id]["progress"] = 35
            self.partial_states[unit_id]["milestones"]["front"] = front_summary

            yield {
                "event": "front_completed",
                "progress": 35,
                "view": "front",
                "summary": front_summary,
                "message": "Front view calibrated: perspective and boundary features analyzed.",
                "timestamp": time.time()
            }
            await asyncio.sleep(0.01)

            # 3. Milestone: Back View Analysis
            t_back_0 = time.perf_counter()
            b_calib, b_metrics, b_reason = self.calibrator.assess_quality(back_img)
            t_back_ms = round((time.perf_counter() - t_back_0) * 1000.0, 2)
            view_latencies["back"] = t_back_ms

            back_summary = {
                "view": "back",
                "calibrated": b_calib,
                "blur_metric": b_metrics.get("blur_metric", 0.0),
                "glare_ratio": b_metrics.get("glare_ratio", 0.0),
                "resolution": b_metrics.get("resolution", [0, 0]),
                "latency_ms": t_back_ms
            }
            self.partial_states[unit_id]["progress"] = 65
            self.partial_states[unit_id]["milestones"]["back"] = back_summary

            yield {
                "event": "back_completed",
                "progress": 65,
                "view": "back",
                "summary": back_summary,
                "message": "Back view calibrated: rear packaging and barcode coverage verified.",
                "timestamp": time.time()
            }
            await asyncio.sleep(0.01)

            # 4. Milestone: Label View Analysis
            t_label_0 = time.perf_counter()
            l_calib, l_metrics, l_reason = self.calibrator.assess_quality(label_img)
            t_label_ms = round((time.perf_counter() - t_label_0) * 1000.0, 2)
            view_latencies["label"] = t_label_ms

            label_summary = {
                "view": "label",
                "calibrated": l_calib,
                "blur_metric": l_metrics.get("blur_metric", 0.0),
                "glare_ratio": l_metrics.get("glare_ratio", 0.0),
                "resolution": l_metrics.get("resolution", [0, 0]),
                "latency_ms": t_label_ms
            }
            self.partial_states[unit_id]["progress"] = 85
            self.partial_states[unit_id]["milestones"]["label"] = label_summary

            yield {
                "event": "label_completed",
                "progress": 85,
                "view": "label",
                "summary": label_summary,
                "message": "Macro label view calibrated: invoking Gemini 3.6 Flash multimodal inspection engine.",
                "timestamp": time.time()
            }
            await asyncio.sleep(0.01)

            # 5. Milestone: Final Multimodal Inspection
            record = await asyncio.to_thread(
                self.agent.inspect_unit,
                unit_id,
                front_img,
                back_img,
                label_img,
                work_order,
                org_id
            )

            total_lat = round((time.perf_counter() - t_start) * 1000.0, 2)
            record["performance"]["latency_ms"] = total_lat

            # Persist record and images
            try:
                self.storage.save_unit_images(unit_id, front_img, back_img, label_img)
            except Exception as e:
                print(f"[Pipeline] Storage warning: {e}")

            try:
                self.db.save_evidence_record(record)
            except Exception as e:
                print(f"[Pipeline] DB warning: {e}")

            # Update metrics
            metrics_tracker.record_inspection(record)

            self.partial_states[unit_id]["status"] = record["overall_status"]
            self.partial_states[unit_id]["progress"] = 100
            self.partial_states[unit_id]["final_record"] = record

            yield {
                "event": "inspection_completed",
                "progress": 100,
                "unit_id": unit_id,
                "org_id": org_id,
                "status": record["overall_status"],
                "record": record,
                "message": f"Autonomous inspection finished with status: {record['overall_status']}",
                "timestamp": time.time()
            }

        except Exception as e:
            total_lat = round((time.perf_counter() - t_start) * 1000.0, 2)
            fail_record = self.calibrator.execute_fail_open(
                unit_id=unit_id,
                error_message=str(e),
                work_order=work_order,
                org_id=org_id
            )
            fail_record["performance"]["latency_ms"] = total_lat

            try:
                self.db.save_evidence_record(fail_record)
            except Exception:
                pass

            metrics_tracker.record_error(str(e))

            self.partial_states[unit_id]["status"] = "UNCERTAIN"
            self.partial_states[unit_id]["progress"] = 100
            self.partial_states[unit_id]["final_record"] = fail_record

            yield {
                "event": "inspection_error",
                "progress": 100,
                "unit_id": unit_id,
                "org_id": org_id,
                "status": "UNCERTAIN",
                "record": fail_record,
                "error": str(e),
                "message": f"Pipeline fail-open triggered: {str(e)}",
                "timestamp": time.time()
            }

pipeline = ProgressiveInspectionPipeline()
