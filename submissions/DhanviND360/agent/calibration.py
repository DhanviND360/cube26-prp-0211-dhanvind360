"""
Calibration, Abstention, and Fail-Open Module for CUBE Prep Manager.
Implements:
- Engineering Rule 3: Fail open (unhandled exceptions yield pending_review records rather than blocking lines).
- Engineering Rule 4: UNCERTAIN as first-class calibrated abstention, not low-confidence guess.
- Quality gating: blur, illumination, resolution, and occlusion metrics.
"""

import time
import cv2
import numpy as np

class CalibrationManager:
    def __init__(self, min_blur=25.0, min_width=500, min_height=400, max_glare_ratio=0.35):
        self.min_blur = min_blur
        self.min_width = min_width
        self.min_height = min_height
        self.max_glare_ratio = max_glare_ratio

    def assess_quality(self, image):
        """
        Assess capture quality for calibration.
        Returns: is_calibrated (bool), metrics (dict), abstention_reason (str or None)
        """
        if image is None:
            return False, {}, "Missing or unreadable image stream"
            
        h, w = image.shape[:2]
        if w < self.min_width or h < self.min_height:
            return False, {"width": w, "height": h}, f"Image resolution ({w}x{h}) below minimum calibrated threshold ({self.min_width}x{self.min_height})"
            
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        
        # Glare ratio: pixels near saturation > 250
        glare_ratio = float(np.sum(gray > 250)) / float(w * h)
        
        metrics = {
            "resolution": [w, h],
            "blur_metric": round(blur, 2),
            "glare_ratio": round(glare_ratio, 4),
            "mean_brightness": round(float(gray.mean()), 2)
        }
        
        if blur < self.min_blur:
            return False, metrics, f"Defocus/motion blur detected (score: {blur:.1f} < threshold: {self.min_blur})"
            
        if glare_ratio > self.max_glare_ratio:
            return False, metrics, f"Severe specular reflection/glare detected ({glare_ratio*100:.1f}% saturated pixels)"
            
        return True, metrics, None

    def execute_fail_open(self, unit_id, error_message, work_order=None):
        """
        Engineering Rule 3: Fail Open.
        A model error or timeout still saves capture and produces a valid record marked pending_review.
        """
        record = {
            "unit_id": unit_id,
            "overall_status": "UNCERTAIN",
            "workflow_state": "pending_review",
            "fail_open_triggered": True,
            "error_detail": str(error_message),
            "timestamp": time.time(),
            "explanation": "Agent pipeline encountered a fail-open condition. Capture preserved and flagged for human operator review without line stoppage.",
            "checks": {
                "polybag_present_sealed": {"verdict": "UNCERTAIN", "detail": "Pending manual operator verification"},
                "suffocation_warning": {"verdict": "UNCERTAIN", "detail": "Pending manual operator verification"},
                "fnsku_label_placement": {"verdict": "UNCERTAIN", "detail": "Pending manual operator verification"},
                "original_barcode_covered": {"verdict": "UNCERTAIN", "detail": "Pending manual operator verification"},
                "expiry_date": {"verdict": "UNCERTAIN", "detail": "Pending manual operator verification"},
                "handling_marks": {"verdict": "UNCERTAIN", "detail": "Pending manual operator verification"}
            }
        }
        return record
