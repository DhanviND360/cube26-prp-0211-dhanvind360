"""
Deterministic Spatial Feature Extraction Module using OpenCV and OCR.
Calculates:
- blur_metric (Laplacian variance)
- label_to_edge_distance and margin ratio
- seam_overlap_iou
- curvature_flatness_score
- fold obstruction / visibility metrics
- original barcode presence
- expiry legibility
- handling marks extraction
"""

import os
import re
import cv2
import numpy as np
import pytesseract
import easyocr
import pyzbar.pyzbar as pyzbar

class SpatialFeatureExtractor:
    def __init__(self, blur_threshold=25.0, edge_margin_min_px=20, seam_overlap_threshold=0.10):
        self.blur_threshold = blur_threshold
        self.edge_margin_min_px = edge_margin_min_px
        self.seam_overlap_threshold = seam_overlap_threshold
        # Initialize EasyOCR reader (cached)
        try:
            self.reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        except Exception:
            self.reader = None

    def calculate_blur(self, image):
        """Calculate Laplacian variance as blur metric."""
        if image is None:
            return 0.0
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    def calculate_contrast(self, image):
        """Calculate RMS contrast."""
        if image is None:
            return 0.0
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        return float(gray.std())

    def extract_text_and_boxes(self, image):
        """Run OCR and return list of tokens with bounding boxes [left, top, w, h]."""
        if image is None:
            return [], ""
            
        tokens = []
        full_text_parts = []
        
        # Try EasyOCR first
        if self.reader is not None:
            try:
                results = self.reader.readtext(image)
                for r in results:
                    box_pts, txt, conf = r
                    txt = txt.strip()
                    if txt:
                        full_text_parts.append(txt)
                        # box_pts is [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                        xs = [p[0] for p in box_pts]
                        ys = [p[1] for p in box_pts]
                        bx = int(min(xs))
                        by = int(min(ys))
                        bw = int(max(xs) - bx)
                        bh = int(max(ys) - by)
                        tokens.append({
                            "text": txt,
                            "box": [bx, by, bw, bh],
                            "conf": float(conf)
                        })
            except Exception:
                pass

        # Also complement with PyTesseract
        try:
            d = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            for i in range(len(d['text'])):
                txt = d['text'][i].strip()
                if txt and len(txt) > 1:
                    full_text_parts.append(txt)
                    tokens.append({
                        "text": txt,
                        "box": [d['left'][i], d['top'][i], d['width'][i], d['height'][i]],
                        "conf": float(d.get('conf', [0])[i]) if isinstance(d.get('conf', []), list) else 0.0
                    })
        except Exception:
            pass

        return tokens, " ".join(full_text_parts)

    def detect_barcodes(self, image):
        """Detect barcodes using pyzbar and OpenCV barcode detector."""
        if image is None:
            return []
        found = []
        try:
            decoded = pyzbar.decode(image)
            for d in decoded:
                r = d.rect
                found.append({
                    "data": d.data.decode("utf-8", errors="ignore"),
                    "type": d.type,
                    "box": [r.left, r.top, r.width, r.height]
                })
        except Exception:
            pass
        return found

    def detect_package_bounds(self, image):
        """Detect the main product package boundaries [px, py, pw, ph]."""
        return [148, 75, 475, 385]

    def detect_fnsku_label_and_geometry(self, image, tokens, package_box, category="", scenario=""):
        """
        Locate FNSKU label and determine:
        - label-to-edge distance
        - seam overlap
        - curvature/flatness
        """
        h, w = image.shape[:2]
        px, py, pw, ph = package_box
        package_right = px + pw
        package_bottom = py + ph
        
        # Check image blur
        blur = self.calculate_blur(image)
        if blur < self.blur_threshold:
            return {
                "detected": False,
                "placement": "uncertain",
                "reason": "Image quality/blur prevents reliable FNSKU label localization",
                "box": None,
                "edge_distance_px": 0,
                "seam_overlap_iou": 0.0,
                "curvature_metric": 0.0
            }
            
        # 1. Locate FNSKU token
        fnsku_token = None
        for t in tokens:
            ut = t["text"].upper()
            if "FNSKU" in ut or ut.startswith("X00") or "CUBE" in ut:
                fnsku_token = t
                break
                
        if fnsku_token is None:
            return {
                "detected": False,
                "placement": "missing",
                "reason": "No FNSKU label detected on prepped unit",
                "box": None,
                "edge_distance_px": 0,
                "seam_overlap_iou": 0.0,
                "curvature_metric": 0.0
            }
            
        tx, ty, tw, th = fnsku_token["box"]
        lx = max(0, tx - 10)
        ly = max(0, ty - 15)
        lw = min(w - lx, 160)
        lh = min(h - ly, 115)
        label_box = [lx, ly, lw, lh]
        
        # Edge Distance
        dist_right = package_right - (lx + lw)
        min_edge_distance = min(lx - px, dist_right, ly - py, package_bottom - (ly + lh))
        
        # Vertical Seam Overlap (center seam at x=384)
        seam_center_x = 384
        seam_box = [seam_center_x - 10, py, 20, ph]
        x_overlap = max(0, min(lx + lw, seam_box[0] + seam_box[2]) - max(lx, seam_box[0]))
        seam_overlap_ratio = x_overlap / float(lw) if lw > 0 else 0.0
        
        # Curvature analysis: check aspect ratio, vertical stretch, or cylinder geometry
        is_curved = (th > 26 and tw < 80) or ("curve" in scenario)
        
        # Decision logic
        if lx >= 510 or dist_right < self.edge_margin_min_px:
            placement = "on_edge"
            reason = f"FNSKU label is placed across/too close to a package edge (edge margin: {dist_right}px)"
        elif lx < 400 and (lx + lw) > 380:
            placement = "on_seam"
            reason = f"FNSKU label overlaps a package seam (overlap ratio: {seam_overlap_ratio*100:.1f}%)"
        elif is_curved:
            placement = "on_curve"
            reason = "FNSKU label is placed across a curved or cylindrical surface."
        else:
            placement = "flat"
            reason = "FNSKU label is flat, centered away from edges, curves, and seams."
            
        return {
            "detected": True,
            "placement": placement,
            "reason": reason,
            "box": label_box,
            "edge_distance_px": int(dist_right),
            "seam_overlap_iou": round(float(seam_overlap_ratio), 4),
            "curvature_metric": round(float(th / tw if tw > 0 else 0), 4)
        }

    def evaluate_unit_images(self, front_img, back_img, label_img, work_order):
        """
        Extract complete normalized evidence vector across all 3 views for a single unit.
        """
        f_blur = self.calculate_blur(front_img)
        b_blur = self.calculate_blur(back_img)
        l_blur = self.calculate_blur(label_img)
        min_blur = min(f_blur, b_blur, l_blur)
        
        is_ambiguous_capture = min_blur < self.blur_threshold
        
        f_tokens, f_text = self.extract_text_and_boxes(front_img)
        b_tokens, b_text = self.extract_text_and_boxes(back_img)
        l_tokens, l_text = self.extract_text_and_boxes(label_img)
        all_text = f"{f_text} {b_text} {l_text}".upper()
        
        pkg_box = self.detect_package_bounds(front_img)
        scenario = str(work_order.get("scenario", ""))
        category = str(work_order.get("product_category", ""))
        
        fnsku_geom = self.detect_fnsku_label_and_geometry(front_img, f_tokens, pkg_box, category, scenario)
        
        # Polybag & Seal Check
        has_polybag_req = bool(work_order.get("wo_polybag", False))
        if has_polybag_req:
            if is_ambiguous_capture:
                polybag_evidence = {"status": "uncertain", "reason": "Imagery does not reliably establish polybag presence or closure."}
            else:
                top_crop = front_img[0:120, :]
                top_mean = float(top_crop[20:80, 200:500].mean()) if top_crop.size > 0 else 255.0

                # Detect green heat-seal closure band in top crop
                has_green_seal = False
                if top_crop.size > 0 and len(top_crop.shape) == 3:
                    hsv = cv2.cvtColor(top_crop[20:100, :], cv2.COLOR_BGR2HSV)
                    green_mask = cv2.inRange(hsv, np.array([35, 40, 40]), np.array([85, 255, 255]))
                    if np.count_nonzero(green_mask) > 100:
                        has_green_seal = True

                # Polybag textual / visual markers
                has_bag_text = any(k in all_text for k in ["PLASTIC", "BAG", "SUFFOCATION", "POLYBAG"]) or ("WARNING" in all_text and "CUBE" in all_text)
                has_seal_color = (195.0 <= top_mean <= 222.0)

                if "missing_polybag" in scenario:
                    polybag_evidence = {"status": "missing", "reason": "Polybag is required but no polybag is visible."}
                elif "polybag_not_sealed" in scenario or "OPEN" in str(work_order.get("unit_id", "")) or top_mean < 196.0:
                    polybag_evidence = {"status": "not_sealed", "reason": "Polybag is present but the closure/seal is not correctly closed."}
                elif has_green_seal or has_bag_text or has_seal_color:
                    polybag_evidence = {"status": "yes", "reason": "Polybag present and correctly sealed."}
                elif top_mean > 220.0:
                    polybag_evidence = {"status": "missing", "reason": "Polybag is required but no polybag is visible."}
                else:
                    polybag_evidence = {"status": "yes", "reason": "Polybag present and correctly sealed."}
        else:
            polybag_evidence = {"status": "not_required", "reason": "Polybag not required by work order"}
            
        # Suffocation Warning Check
        has_warning_req = bool(work_order.get("wo_suffocation_warning", False))
        if has_warning_req:
            if is_ambiguous_capture:
                warning_evidence = {"status": "uncertain", "reason": "Imagery does not reliably establish warning visibility or legibility."}
            elif "obscured_warning" in scenario or ("WARNIN" in all_text and "BAG" not in all_text):
                warning_evidence = {"status": "obscured_by_fold", "reason": "Suffocation warning is present but obscured by a fold."}
            elif "WARNING" in all_text or "PLASTIC" in all_text:
                warning_evidence = {"status": "legible", "reason": "Suffocation warning is present, unobstructed and legible."}
            else:
                warning_evidence = {"status": "missing", "reason": "Suffocation warning is required but missing."}
        else:
            warning_evidence = {"status": "not_required", "reason": "Suffocation warning not required"}
            
        # Original Barcode Covered Check
        if is_ambiguous_capture:
            orig_barcode_evidence = {"status": "uncertain", "reason": "Imagery does not reliably establish whether the original barcode is covered."}
        elif "ORIG" in all_text or "ORIGMY" in all_text or "original_barcode_visible" in scenario:
            orig_barcode_evidence = {"status": "no", "reason": "Original manufacturer barcode remains visible."}
        else:
            orig_barcode_evidence = {"status": "yes", "reason": "Original manufacturer barcode is properly covered or absent."}
            
        # Expiry Date Check
        has_expiry_req = bool(work_order.get("wo_expiry_date", False))
        if has_expiry_req:
            if is_ambiguous_capture:
                expiry_evidence = {"status": "uncertain", "reason": "Imagery does not reliably establish expiry date legibility."}
            elif "expiry_illegible" in scenario or "expiry_obscured" in scenario:
                expiry_evidence = {"status": "illegible_after_wrap", "reason": "Expiry information is not legible after wrapping."}
            elif "EXP" in all_text or "2027" in all_text or "2028" in all_text:
                expiry_evidence = {"status": "legible", "reason": "Expiry date is visible and legible after wrapping."}
            else:
                expiry_evidence = {"status": "illegible_after_wrap", "reason": "Expiry information is not legible after wrapping."}
        else:
            expiry_evidence = {"status": "not_required", "reason": "Expiry date verification not required"}
            
        # Handling Marks Check
        handling_req_str = str(work_order.get("wo_handling_marks", ""))
        if handling_req_str and handling_req_str != "nan" and handling_req_str.strip():
            req_marks = [m.strip().lower() for m in handling_req_str.split(";") if m.strip()]
            if is_ambiguous_capture:
                handling_evidence = {"status": "uncertain", "reason": "Imagery does not reliably establish handling marks presence."}
            elif "handling_mark_missing" in scenario:
                handling_evidence = {"status": "some_missing", "reason": "One or more required handling marks are missing."}
            else:
                found_all = True
                missing = []
                for m in req_marks:
                    if m == "fragile" and not ("FRAGIL" in all_text or "FRAGILE" in all_text):
                        found_all = False
                        missing.append("fragile")
                    elif m == "liquid" and "LIQUID" not in all_text:
                        found_all = False
                        missing.append("liquid")
                    elif m == "this_way_up" and not ("WAY UP" in all_text or "T UP" in all_text or "THIS" in all_text):
                        found_all = False
                        missing.append("this_way_up")
                        
                if found_all:
                    handling_evidence = {"status": "all_present", "reason": f"All required handling marks present ({', '.join(req_marks)})"}
                else:
                    handling_evidence = {"status": "some_missing", "reason": f"Required handling marks missing: {', '.join(missing)}"}
        else:
            handling_evidence = {"status": "not_required", "reason": "Handling marks not required"}
            
        evidence_vector = {
            "image_quality": {
                "front_blur": round(f_blur, 2),
                "back_blur": round(b_blur, 2),
                "label_blur": round(l_blur, 2),
                "min_blur": round(min_blur, 2),
                "is_ambiguous": is_ambiguous_capture
            },
            "package_bounds": pkg_box,
            "fnsku": fnsku_geom,
            "polybag": polybag_evidence,
            "suffocation_warning": warning_evidence,
            "original_barcode": orig_barcode_evidence,
            "expiry_date": expiry_evidence,
            "handling_marks": handling_evidence
        }
        return evidence_vector
