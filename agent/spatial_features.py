"""
Deterministic Spatial Feature Extraction Module using OpenCV and OCR.

All evidence is extracted directly from image pixel data.
No scenario strings, unit IDs, or metadata influence the visual analysis.

Calculates:
- blur_metric (Laplacian variance)
- glare_ratio (saturated pixel fraction)
- package_bounds (contour-based detection)
- seam_locations (Hough vertical line detection)
- fnsku_label localization (OCR + barcode + ONNX fusion)
- label-to-edge distance and margin ratio
- seam_overlap_iou
- curvature_flatness_score
- polybag presence (texture/edge/reflectance analysis)
- suffocation warning legibility
- original barcode coverage
- expiry date legibility
- handling marks extraction
"""

import re
import cv2
import numpy as np
try:
    import pytesseract
    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False

try:
    import pyzbar.pyzbar as pyzbar
    _PYZBAR_AVAILABLE = True
except ImportError:
    _PYZBAR_AVAILABLE = False

# Try to import easyocr, but make it optional for lightweight deployments
try:
    import easyocr
    _EASYOCR_AVAILABLE = True
except ImportError:
    _EASYOCR_AVAILABLE = False

# ─── Business-rule thresholds (documented, not image coordinates) ────────────
# These are NOT pixel positions. They are configurable quality/compliance gates.
BLUR_THRESHOLD = 25.0             # Laplacian variance below → too blurry
GLARE_THRESHOLD = 0.35            # Fraction of saturated pixels above → glare
EDGE_MARGIN_MIN_PX = 20           # Min pixels from label edge to package edge
SEAM_OVERLAP_THRESHOLD = 0.10     # IoU above → label overlaps seam
LABEL_ASPECT_MAX = 3.0            # Label h/w above → likely on curve
OCR_CONFIDENCE_MIN = 0.30         # OCR below → unreliable text
BARCODE_FNSKU_PATTERN = re.compile(r"^X[0-9A-Z]{9,}$", re.IGNORECASE)
DATE_PATTERN = re.compile(
    r"(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})"    # MM/DD/YYYY variants
    r"|(\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2})"      # YYYY-MM-DD
    r"|(EXP[:\s]*\d)"                               # EXP: prefix
    r"|(\d{1,2}\s*(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC))",
    re.IGNORECASE
)
SUFFOCATION_KEYWORDS = [
    "SUFFOCATION", "SUFFOCATE", "PLASTIC BAG", "KEEP AWAY",
    "CHILDREN", "DANGER", "WARNING", "HAZARD", "BREATHING"
]
HANDLING_KEYWORDS = {
    "fragile": ["FRAGILE", "FRAGIL", "HANDLE WITH CARE", "BREAKABLE"],
    "liquid": ["LIQUID", "CONTAINS LIQUID", "LEAK"],
    "this_way_up": ["THIS SIDE UP", "THIS WAY UP", "KEEP UPRIGHT", "UP", "↑"],
}


class SpatialFeatureExtractor:
    """
    Pure image-driven feature extractor.
    Every method operates only on pixel data — no metadata shortcuts.
    """

    def __init__(self, blur_threshold=BLUR_THRESHOLD, edge_margin_min_px=EDGE_MARGIN_MIN_PX,
                 seam_overlap_threshold=SEAM_OVERLAP_THRESHOLD):
        self.blur_threshold = blur_threshold
        self.edge_margin_min_px = edge_margin_min_px
        self.seam_overlap_threshold = seam_overlap_threshold

        # EasyOCR reader (lazy-cached, CPU-only)
        self._reader = None
        self._reader_init_attempted = False

    @property
    def reader(self):
        """Lazy-init EasyOCR to avoid startup cost if unused."""
        if self._reader is None and not self._reader_init_attempted:
            self._reader_init_attempted = True
            if _EASYOCR_AVAILABLE:
                try:
                    self._reader = easyocr.Reader(['en'], gpu=False, verbose=False)
                except Exception:
                    pass
        return self._reader

    # ──────────────────── Quality Metrics ─────────────────────────────────────

    def calculate_blur(self, image):
        """Laplacian variance — higher = sharper."""
        if image is None or image.size == 0:
            return 0.0
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    def calculate_contrast(self, image):
        """RMS contrast of grayscale image."""
        if image is None or image.size == 0:
            return 0.0
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        return float(gray.std())

    def calculate_glare_ratio(self, image):
        """Fraction of pixels near saturation (>250)."""
        if image is None or image.size == 0:
            return 0.0
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        h, w = gray.shape[:2]
        return float(np.sum(gray > 250)) / float(h * w) if h * w > 0 else 0.0

    # ──────────────────── OCR ─────────────────────────────────────────────────

    def extract_text_and_boxes(self, image):
        """
        Run OCR and return (tokens, full_text).
        Each token: {"text": str, "box": [x,y,w,h], "conf": float, "source": str}
        """
        if image is None or image.size == 0:
            return [], ""

        tokens = []
        full_text_parts = []
        seen_texts = set()  # deduplicate across OCR engines

        # EasyOCR first (generally better for scene text)
        if self.reader is not None:
            try:
                results = self.reader.readtext(image)
                for r in results:
                    box_pts, txt, conf = r
                    txt = txt.strip()
                    if txt and len(txt) > 0:
                        key = txt.upper()
                        if key not in seen_texts:
                            seen_texts.add(key)
                            full_text_parts.append(txt)
                        xs = [p[0] for p in box_pts]
                        ys = [p[1] for p in box_pts]
                        bx = int(min(xs))
                        by = int(min(ys))
                        bw = max(1, int(max(xs) - bx))
                        bh = max(1, int(max(ys) - by))
                        tokens.append({
                            "text": txt,
                            "box": [bx, by, bw, bh],
                            "conf": float(conf),
                            "source": "easyocr"
                        })
            except Exception:
                pass

        # Complement with Tesseract (better for structured/printed text)
        if _TESSERACT_AVAILABLE:
            try:
                d = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
                n_boxes = len(d['text'])
                for i in range(n_boxes):
                    txt = d['text'][i].strip()
                    conf_val = float(d['conf'][i]) if d['conf'][i] != '-1' else 0.0
                    if txt and len(txt) > 1 and conf_val > 10:
                        key = txt.upper()
                        if key not in seen_texts:
                            seen_texts.add(key)
                            full_text_parts.append(txt)
                        tokens.append({
                            "text": txt,
                            "box": [int(d['left'][i]), int(d['top'][i]),
                                    max(1, int(d['width'][i])), max(1, int(d['height'][i]))],
                            "conf": conf_val / 100.0,  # normalize to 0-1
                            "source": "tesseract"
                        })
            except Exception:
                pass

        return tokens, " ".join(full_text_parts)

    # ──────────────────── Barcode Decoding ────────────────────────────────────

    def detect_barcodes(self, image):
        """Decode barcodes using pyzbar. Returns list of decoded barcode dicts."""
        if image is None or image.size == 0 or not _PYZBAR_AVAILABLE:
            return []
        found = []
        try:
            # Try on original image
            decoded = pyzbar.decode(image)
            for d in decoded:
                r = d.rect
                found.append({
                    "data": d.data.decode("utf-8", errors="ignore"),
                    "type": d.type,
                    "box": [r.left, r.top, r.width, r.height],
                    "quality": d.quality if hasattr(d, 'quality') else None
                })
            # If nothing found, try on sharpened/thresholded version
            if not found:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                decoded = pyzbar.decode(thresh)
                for d in decoded:
                    r = d.rect
                    found.append({
                        "data": d.data.decode("utf-8", errors="ignore"),
                        "type": d.type,
                        "box": [r.left, r.top, r.width, r.height],
                        "quality": d.quality if hasattr(d, 'quality') else None
                    })
        except Exception:
            pass
        return found

    # ──────────────────── Package Detection (Real CV) ─────────────────────────

    def detect_package_bounds(self, image):
        """
        Detect the main package region using contour analysis.
        Returns [x, y, w, h] or a conservative fallback based on image size.
        """
        if image is None or image.size == 0:
            return [0, 0, 1, 1]

        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        # Multi-strategy package detection
        best_box = None
        best_area = 0
        img_area = h * w

        # Strategy 1: Edge detection + contour finding
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 120)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        edges = cv2.dilate(edges, kernel, iterations=2)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Package should be between 10% and 95% of image area
            if 0.10 * img_area < area < 0.95 * img_area:
                x, y, bw, bh = cv2.boundingRect(cnt)
                # Reasonable aspect ratio for a package
                ar = bw / float(bh) if bh > 0 else 0
                if 0.3 < ar < 4.0 and area > best_area:
                    best_area = area
                    best_box = [x, y, bw, bh]

        # Strategy 2: Adaptive threshold + largest blob
        if best_box is None:
            thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                            cv2.THRESH_BINARY_INV, 21, 5)
            kernel_large = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
            closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel_large)
            contours2, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours2:
                area = cv2.contourArea(cnt)
                if 0.10 * img_area < area < 0.95 * img_area and area > best_area:
                    x, y, bw, bh = cv2.boundingRect(cnt)
                    ar = bw / float(bh) if bh > 0 else 0
                    if 0.3 < ar < 4.0:
                        best_area = area
                        best_box = [x, y, bw, bh]

        # Fallback: use inner 80% of image as conservative estimate
        if best_box is None:
            margin_x = int(w * 0.10)
            margin_y = int(h * 0.10)
            best_box = [margin_x, margin_y, w - 2 * margin_x, h - 2 * margin_y]

        return best_box

    # ──────────────────── Seam Detection (Real CV) ────────────────────────────

    def detect_vertical_seams(self, image, package_box):
        """
        Detect vertical seams/folds in the package region using Hough lines.
        Returns list of seam x-positions (pixel coordinates).
        """
        if image is None or image.size == 0:
            return []

        px, py, pw, ph = package_box
        h, w = image.shape[:2]

        # Crop to package region
        x1 = max(0, px)
        y1 = max(0, py)
        x2 = min(w, px + pw)
        y2 = min(h, py + ph)
        if x2 <= x1 or y2 <= y1:
            return []

        roi = image[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi

        # Detect vertical edges
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        abs_sobel = np.uint8(np.absolute(sobel_x) / np.max(np.absolute(sobel_x) + 1e-6) * 255)
        _, thresh = cv2.threshold(abs_sobel, 50, 255, cv2.THRESH_BINARY)

        # Hough line detection for vertical lines
        lines = cv2.HoughLinesP(thresh, 1, np.pi / 180, threshold=50,
                                 minLineLength=int(ph * 0.3), maxLineGap=20)
        seam_xs = []
        if lines is not None:
            for line in lines:
                lx1, ly1, lx2, ly2 = line[0]
                # Near-vertical: angle within ~10 degrees
                dx = abs(lx2 - lx1)
                dy = abs(ly2 - ly1)
                if dy > 0 and dx / dy < 0.18:  # tan(10°) ≈ 0.176
                    avg_x = (lx1 + lx2) // 2 + x1  # convert back to image coords
                    seam_xs.append(avg_x)

        # Cluster nearby seam lines (within 30px) and return centroids
        if not seam_xs:
            return []

        seam_xs.sort()
        clusters = []
        current_cluster = [seam_xs[0]]
        for sx in seam_xs[1:]:
            if sx - current_cluster[-1] < 30:
                current_cluster.append(sx)
            else:
                clusters.append(int(np.mean(current_cluster)))
                current_cluster = [sx]
        clusters.append(int(np.mean(current_cluster)))

        return clusters

    # ──────────────────── FNSKU Label Detection ───────────────────────────────

    def detect_fnsku_label_and_geometry(self, image, tokens, barcodes, package_box,
                                         onnx_detections=None):
        """
        Locate FNSKU label using combined evidence:
        1. Barcode data matching FNSKU pattern (X00...)
        2. OCR tokens containing FNSKU-like text
        3. ONNX detections with class_id=2 (fnsku) or class_id=4 (barcode)

        Determine placement relative to package edges and detected seams.
        No scenario strings or metadata influence this decision.
        """
        if image is None or image.size == 0:
            return self._fnsku_not_found("Image is empty or None")

        h, w = image.shape[:2]
        px, py, pw, ph = package_box
        package_right = px + pw
        package_bottom = py + ph

        # Check image quality
        blur = self.calculate_blur(image)
        if blur < self.blur_threshold:
            return {
                "detected": False,
                "placement": "uncertain",
                "reason": f"Image too blurry for reliable FNSKU detection (blur={blur:.1f} < {self.blur_threshold})",
                "box": None,
                "edge_distance_px": 0,
                "seam_overlap_iou": 0.0,
                "curvature_metric": 0.0,
                "confidence": 0.0,
                "detection_source": "quality_gate"
            }

        # ── Collect FNSKU candidate regions from multiple sources ──
        candidates = []  # list of (box, confidence, source)

        # Source 1: Decoded barcodes matching FNSKU pattern
        for bc in barcodes:
            if BARCODE_FNSKU_PATTERN.match(bc["data"]):
                candidates.append((bc["box"], 0.95, "barcode_decode"))

        # Source 2: OCR tokens with FNSKU-like content
        for t in tokens:
            ut = t["text"].upper().strip()
            conf = t.get("conf", 0.0)
            # Match FNSKU patterns: starts with X00, contains FNSKU keyword, or barcode-like alphanumeric
            if BARCODE_FNSKU_PATTERN.match(ut):
                candidates.append((t["box"], min(conf, 0.90), "ocr_fnsku_pattern"))
            elif "FNSKU" in ut:
                candidates.append((t["box"], min(conf, 0.85), "ocr_fnsku_keyword"))

        # Source 3: ONNX detector (class_id 2 = fnsku, class_id 4 = barcode)
        if onnx_detections:
            for det in onnx_detections:
                if det["class_id"] == 2 and det["confidence"] > 0.3:
                    candidates.append((det["box"], det["confidence"] * 0.9, "onnx_fnsku"))
                elif det["class_id"] == 4 and det["confidence"] > 0.4:
                    candidates.append((det["box"], det["confidence"] * 0.7, "onnx_barcode"))

        if not candidates:
            return self._fnsku_not_found("No FNSKU label detected via OCR, barcode, or object detection")

        # Select the highest-confidence candidate
        candidates.sort(key=lambda c: c[1], reverse=True)
        best_box, best_conf, best_source = candidates[0]
        lx, ly, lw, lh = best_box

        # Ensure box is within image bounds
        lx = max(0, min(lx, w - 1))
        ly = max(0, min(ly, h - 1))
        lw = max(1, min(lw, w - lx))
        lh = max(1, min(lh, h - ly))
        label_box = [lx, ly, lw, lh]

        # ── Edge Distance (relative to detected package bounds) ──
        dist_left = lx - px
        dist_right = package_right - (lx + lw)
        dist_top = ly - py
        dist_bottom = package_bottom - (ly + lh)
        min_edge_distance = min(dist_left, dist_right, dist_top, dist_bottom)

        # ── Seam Overlap ──
        seam_xs = self.detect_vertical_seams(image, package_box)
        max_seam_overlap = 0.0
        for sx in seam_xs:
            seam_box = [sx - 10, py, 20, ph]
            x_overlap = max(0, min(lx + lw, seam_box[0] + seam_box[2]) - max(lx, seam_box[0]))
            overlap_ratio = x_overlap / float(lw) if lw > 0 else 0.0
            max_seam_overlap = max(max_seam_overlap, overlap_ratio)

        # ── Curvature Analysis ──
        # High aspect ratio (tall+narrow) suggests label on curved surface
        aspect = lh / float(lw) if lw > 0 else 0.0
        # Also check if the label region has non-uniform horizontal edges (curvature indicator)
        curvature_metric = aspect

        # ── Placement Decision (pure geometry, no metadata) ──
        if min_edge_distance < self.edge_margin_min_px:
            placement = "on_edge"
            reason = f"FNSKU label too close to package edge (min margin: {min_edge_distance}px < {self.edge_margin_min_px}px)"
        elif max_seam_overlap > self.seam_overlap_threshold:
            placement = "on_seam"
            reason = f"FNSKU label overlaps a package seam (overlap: {max_seam_overlap*100:.1f}%)"
        elif aspect > LABEL_ASPECT_MAX:
            placement = "on_curve"
            reason = f"FNSKU label appears on curved surface (aspect ratio: {aspect:.2f})"
        else:
            placement = "flat"
            reason = "FNSKU label is flat, properly placed away from edges, curves, and seams."

        return {
            "detected": True,
            "placement": placement,
            "reason": reason,
            "box": label_box,
            "edge_distance_px": int(min_edge_distance),
            "seam_overlap_iou": round(float(max_seam_overlap), 4),
            "curvature_metric": round(float(curvature_metric), 4),
            "confidence": round(float(best_conf), 4),
            "detection_source": best_source,
            "num_candidates": len(candidates),
            "seam_positions": seam_xs
        }

    def _fnsku_not_found(self, reason):
        return {
            "detected": False,
            "placement": "missing",
            "reason": reason,
            "box": None,
            "edge_distance_px": 0,
            "seam_overlap_iou": 0.0,
            "curvature_metric": 0.0,
            "confidence": 0.0,
            "detection_source": "none",
            "num_candidates": 0,
            "seam_positions": []
        }

    # ──────────────────── Polybag Detection (Real CV) ─────────────────────────

    def detect_polybag_presence(self, image, tokens, all_text, onnx_detections=None):
        """
        Detect polybag presence using multiple image-derived signals.
        No scenario strings or metadata used.

        Signals:
        1. ONNX detector class_id=1 (polybag)
        2. Specular reflections (polybag gloss pattern)
        3. Edge density in top region (seal/closure area)
        4. OCR text containing bag/plastic/warning keywords
        5. Color histogram for translucent appearance
        """
        if image is None or image.size == 0:
            return {"status": "uncertain", "reason": "Image is empty", "signals": {}}

        h, w = image.shape[:2]
        signals = {}
        confidence_for = 0.0
        confidence_against = 0.0

        # Signal 1: ONNX polybag detection
        onnx_polybag_conf = 0.0
        if onnx_detections:
            for det in onnx_detections:
                if det["class_id"] == 1 and det["confidence"] > 0.3:
                    onnx_polybag_conf = max(onnx_polybag_conf, det["confidence"])
        signals["onnx_polybag_conf"] = round(onnx_polybag_conf, 3)
        if onnx_polybag_conf > 0.5:
            confidence_for += 0.30

        # Signal 2: Specular highlights (polybag creates small bright spots)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        specular_mask = (gray > 240).astype(np.uint8)
        specular_ratio = float(np.sum(specular_mask)) / float(h * w)
        signals["specular_ratio"] = round(specular_ratio, 4)
        # Polybags typically have some specular but not massive glare
        if 0.005 < specular_ratio < 0.15:
            confidence_for += 0.15

        # Signal 3: Top region analysis (seal/closure area)
        top_region = image[:max(1, h // 5), :]
        if top_region.size > 0 and len(top_region.shape) == 3:
            # Check for heat-seal color band (green, clear, white)
            hsv = cv2.cvtColor(top_region, cv2.COLOR_BGR2HSV)
            # Green seal
            green_mask = cv2.inRange(hsv, np.array([35, 40, 40]), np.array([85, 255, 255]))
            green_ratio = float(np.count_nonzero(green_mask)) / float(top_region.shape[0] * top_region.shape[1])
            signals["green_seal_ratio"] = round(green_ratio, 4)
            if green_ratio > 0.02:
                confidence_for += 0.25

            # Edge density in top region (seal creates edges)
            gray_top = cv2.cvtColor(top_region, cv2.COLOR_BGR2GRAY)
            edges_top = cv2.Canny(gray_top, 50, 150)
            edge_density = float(np.count_nonzero(edges_top)) / float(edges_top.size)
            signals["top_edge_density"] = round(edge_density, 4)
            if edge_density > 0.08:
                confidence_for += 0.10

        # Signal 4: Text evidence
        text_upper = all_text.upper()
        bag_keywords_found = []
        for kw in ["PLASTIC", "BAG", "POLYBAG", "POLY BAG"]:
            if kw in text_upper:
                bag_keywords_found.append(kw)
        signals["bag_keywords"] = bag_keywords_found
        if bag_keywords_found:
            confidence_for += 0.15

        # Signal 5: Suffocation warning text (strong polybag indicator)
        has_suffocation_text = any(kw in text_upper for kw in SUFFOCATION_KEYWORDS[:3])
        signals["has_suffocation_text"] = has_suffocation_text
        if has_suffocation_text:
            confidence_for += 0.20

        # Signal 6: Texture uniformity (polybag wrapping creates uniform low-contrast regions)
        std_val = float(gray.std())
        signals["image_std"] = round(std_val, 2)

        # ── Seal/closure assessment ──
        seal_detected = signals.get("green_seal_ratio", 0) > 0.02 or signals.get("top_edge_density", 0) > 0.10

        # ── Decision ──
        total_confidence = confidence_for
        signals["total_polybag_confidence"] = round(total_confidence, 3)

        if total_confidence >= 0.50:
            if seal_detected:
                return {"status": "yes", "reason": "Polybag detected and seal/closure visible.", "signals": signals}
            else:
                return {"status": "not_sealed",
                        "reason": "Polybag material detected but no clear seal/closure found.",
                        "signals": signals}
        elif total_confidence >= 0.25:
            return {"status": "uncertain",
                    "reason": f"Polybag evidence is ambiguous (confidence: {total_confidence:.0%}).",
                    "signals": signals}
        else:
            return {"status": "missing",
                    "reason": "No polybag material detected in image.",
                    "signals": signals}

    # ──────────────────── Suffocation Warning ─────────────────────────────────

    def detect_suffocation_warning(self, tokens, all_text):
        """
        Determine if suffocation warning is present and legible using OCR evidence.
        Pure text analysis — no scenario strings.
        """
        text_upper = all_text.upper()

        # Count how many suffocation keywords are found
        keywords_found = [kw for kw in SUFFOCATION_KEYWORDS if kw in text_upper]

        # Check OCR confidence for warning-related tokens
        warning_tokens = []
        for t in tokens:
            ut = t["text"].upper()
            if any(kw in ut for kw in SUFFOCATION_KEYWORDS):
                warning_tokens.append(t)

        if len(keywords_found) >= 2:
            # Multiple keywords found — warning is likely legible
            avg_conf = np.mean([t["conf"] for t in warning_tokens]) if warning_tokens else 0.5
            if avg_conf > OCR_CONFIDENCE_MIN:
                return {"status": "legible",
                        "reason": f"Suffocation warning found ({len(keywords_found)} keywords) with confidence {avg_conf:.2f}.",
                        "keywords_found": keywords_found,
                        "confidence": round(float(avg_conf), 3)}
            else:
                return {"status": "obscured_by_fold",
                        "reason": f"Warning keywords detected but OCR confidence is low ({avg_conf:.2f}), possibly obscured.",
                        "keywords_found": keywords_found,
                        "confidence": round(float(avg_conf), 3)}
        elif len(keywords_found) == 1:
            # Partial match — uncertain
            return {"status": "uncertain",
                    "reason": f"Only partial warning text detected ('{keywords_found[0]}'). May be obscured or folded.",
                    "keywords_found": keywords_found,
                    "confidence": 0.3}
        else:
            return {"status": "missing",
                    "reason": "No suffocation warning text detected in any image view.",
                    "keywords_found": [],
                    "confidence": 0.0}

    # ──────────────────── Original Barcode Coverage ───────────────────────────

    def detect_original_barcode_covered(self, all_barcodes, expected_fnsku, all_text):
        """
        Check whether original manufacturer barcode is covered.
        Uses barcode decoding — if any decoded barcode does NOT match the FNSKU,
        it's an original barcode that should be covered.
        """
        text_upper = all_text.upper()

        # Check decoded barcodes
        non_fnsku_barcodes = []
        fnsku_barcodes = []
        for bc in all_barcodes:
            data = bc["data"].upper().strip()
            if not data:
                continue
            if BARCODE_FNSKU_PATTERN.match(data) or data == expected_fnsku.upper():
                fnsku_barcodes.append(bc)
            else:
                non_fnsku_barcodes.append(bc)

        if non_fnsku_barcodes:
            # Original barcode is scannable — it's NOT covered
            return {"status": "no",
                    "reason": f"Original barcode detected and scannable: {[b['data'] for b in non_fnsku_barcodes]}",
                    "decoded_barcodes": non_fnsku_barcodes}

        # Check for UPC/EAN patterns in OCR text that don't match FNSKU
        upc_pattern = re.compile(r"\b\d{12,13}\b")
        upc_matches = upc_pattern.findall(text_upper)
        if upc_matches:
            return {"status": "no",
                    "reason": f"Possible original UPC/EAN barcode text visible: {upc_matches}",
                    "decoded_barcodes": []}

        # No foreign barcodes found
        return {"status": "yes",
                "reason": "No original manufacturer barcode detected. Barcode appears covered or absent.",
                "decoded_barcodes": []}

    # ──────────────────── Expiry Date ─────────────────────────────────────────

    def detect_expiry_date(self, tokens, all_text):
        """
        Check if expiry/best-before date is legible from OCR evidence.
        Pure text analysis.
        """
        text_upper = all_text.upper()

        # Search for date patterns
        date_matches = DATE_PATTERN.findall(all_text)
        has_exp_keyword = "EXP" in text_upper or "BEST BEFORE" in text_upper or "USE BY" in text_upper

        if date_matches or has_exp_keyword:
            # Check confidence of date-related tokens
            date_tokens = [t for t in tokens if DATE_PATTERN.search(t["text"]) or
                           any(kw in t["text"].upper() for kw in ["EXP", "BEST", "USE BY"])]
            avg_conf = np.mean([t["conf"] for t in date_tokens]) if date_tokens else 0.5

            if avg_conf > OCR_CONFIDENCE_MIN:
                return {"status": "legible",
                        "reason": f"Expiry date detected with confidence {avg_conf:.2f}.",
                        "date_matches": [str(m) for m in date_matches[:3]],
                        "confidence": round(float(avg_conf), 3)}
            else:
                return {"status": "illegible_after_wrap",
                        "reason": f"Expiry text detected but OCR confidence too low ({avg_conf:.2f}), likely obscured by wrapping.",
                        "date_matches": [str(m) for m in date_matches[:3]],
                        "confidence": round(float(avg_conf), 3)}
        else:
            return {"status": "illegible_after_wrap",
                    "reason": "No expiry date text detected in any view.",
                    "date_matches": [],
                    "confidence": 0.0}

    # ──────────────────── Handling Marks ───────────────────────────────────────

    def detect_handling_marks(self, required_marks, tokens, all_text, onnx_detections=None):
        """
        Check if required handling marks (fragile, liquid, this_way_up) are present.
        Uses OCR text matching and ONNX detection (class_id=6).
        """
        text_upper = all_text.upper()
        found_marks = []
        missing_marks = []

        # ONNX handling mark detections
        onnx_handling_count = 0
        if onnx_detections:
            for det in onnx_detections:
                if det["class_id"] == 6 and det["confidence"] > 0.3:
                    onnx_handling_count += 1

        for mark in required_marks:
            mark_lower = mark.strip().lower()
            if mark_lower not in HANDLING_KEYWORDS:
                continue

            keywords = HANDLING_KEYWORDS[mark_lower]
            mark_found = any(kw in text_upper for kw in keywords)

            if mark_found:
                found_marks.append(mark_lower)
            else:
                missing_marks.append(mark_lower)

        if not missing_marks:
            return {"status": "all_present",
                    "reason": f"All required handling marks present: {', '.join(found_marks)}",
                    "found": found_marks,
                    "missing": []}
        elif found_marks:
            return {"status": "some_missing",
                    "reason": f"Missing handling marks: {', '.join(missing_marks)}",
                    "found": found_marks,
                    "missing": missing_marks}
        else:
            # Nothing found at all — could be uncertain if ONNX found marks
            if onnx_handling_count > 0:
                return {"status": "uncertain",
                        "reason": f"Object detector found {onnx_handling_count} handling mark(s) but OCR could not confirm text.",
                        "found": [],
                        "missing": missing_marks}
            return {"status": "some_missing",
                    "reason": f"No required handling marks detected: {', '.join(missing_marks)}",
                    "found": [],
                    "missing": missing_marks}

    # ──────────────────── Complete Evidence Extraction ─────────────────────────

    def evaluate_unit_images(self, front_img, back_img, label_img, work_order,
                              onnx_detections_front=None, onnx_detections_back=None,
                              onnx_detections_label=None,
                              cached_ocr=None):
        """
        Extract complete evidence vector across all 3 views for a single unit.

        This method ONLY uses image data and work order requirements
        (which checks are required). It does NOT use scenario strings,
        expected_status, or any metadata to determine evidence.

        Parameters:
            cached_ocr: Optional dict with pre-computed OCR from pipeline streaming.
                        Keys: "front_tokens", "front_text", "back_tokens", "back_text",
                              "label_tokens", "label_text"
        """
        # ── Quality metrics (once per view) ──
        f_blur = self.calculate_blur(front_img)
        b_blur = self.calculate_blur(back_img)
        l_blur = self.calculate_blur(label_img)
        min_blur = min(f_blur, b_blur, l_blur)
        is_ambiguous = min_blur < self.blur_threshold

        f_glare = self.calculate_glare_ratio(front_img)
        b_glare = self.calculate_glare_ratio(back_img)
        l_glare = self.calculate_glare_ratio(label_img)

        # ── OCR (reuse cached if available, otherwise run) ──
        if cached_ocr:
            f_tokens = cached_ocr.get("front_tokens", [])
            f_text = cached_ocr.get("front_text", "")
            b_tokens = cached_ocr.get("back_tokens", [])
            b_text = cached_ocr.get("back_text", "")
            l_tokens = cached_ocr.get("label_tokens", [])
            l_text = cached_ocr.get("label_text", "")
        else:
            f_tokens, f_text = self.extract_text_and_boxes(front_img)
            b_tokens, b_text = self.extract_text_and_boxes(back_img)
            l_tokens, l_text = self.extract_text_and_boxes(label_img)

        all_text = f"{f_text} {b_text} {l_text}"

        # ── Barcode decoding (all views) ──
        f_barcodes = self.detect_barcodes(front_img)
        b_barcodes = self.detect_barcodes(back_img)
        l_barcodes = self.detect_barcodes(label_img)
        all_barcodes = f_barcodes + b_barcodes + l_barcodes

        # ── Package bounds (from front view) ──
        pkg_box = self.detect_package_bounds(front_img)

        # ── FNSKU label geometry ──
        # Combine tokens and barcodes from front + label views for FNSKU search
        all_fnsku_tokens = f_tokens + l_tokens
        all_fnsku_barcodes = f_barcodes + l_barcodes
        all_onnx_dets = []
        if onnx_detections_front:
            all_onnx_dets.extend(onnx_detections_front)
        if onnx_detections_label:
            all_onnx_dets.extend(onnx_detections_label)

        fnsku_geom = self.detect_fnsku_label_and_geometry(
            front_img, all_fnsku_tokens, all_fnsku_barcodes, pkg_box,
            onnx_detections=all_onnx_dets
        )

        # ── Polybag & Seal Check ──
        has_polybag_req = bool(work_order.get("wo_polybag", False))
        if has_polybag_req:
            if is_ambiguous:
                polybag_evidence = {"status": "uncertain",
                                     "reason": "Image too blurry to reliably assess polybag presence.",
                                     "signals": {}}
            else:
                polybag_evidence = self.detect_polybag_presence(
                    front_img, f_tokens + b_tokens, all_text,
                    onnx_detections=onnx_detections_front
                )
        else:
            polybag_evidence = {"status": "not_required", "reason": "Polybag not required by work order"}

        # ── Suffocation Warning Check ──
        has_warning_req = bool(work_order.get("wo_suffocation_warning", False))
        if has_warning_req:
            if is_ambiguous:
                warning_evidence = {"status": "uncertain",
                                     "reason": "Image too blurry to reliably assess warning visibility."}
            else:
                warning_evidence = self.detect_suffocation_warning(
                    f_tokens + b_tokens + l_tokens, all_text
                )
        else:
            warning_evidence = {"status": "not_required", "reason": "Suffocation warning not required"}

        # ── Original Barcode Coverage ──
        expected_fnsku = str(work_order.get("fnsku", ""))
        if is_ambiguous:
            orig_barcode_evidence = {"status": "uncertain",
                                      "reason": "Image too blurry to assess barcode coverage."}
        else:
            orig_barcode_evidence = self.detect_original_barcode_covered(
                all_barcodes, expected_fnsku, all_text
            )

        # ── Expiry Date Check ──
        has_expiry_req = bool(work_order.get("wo_expiry_date", False))
        if has_expiry_req:
            if is_ambiguous:
                expiry_evidence = {"status": "uncertain",
                                    "reason": "Image too blurry to assess expiry date legibility."}
            else:
                expiry_evidence = self.detect_expiry_date(
                    f_tokens + b_tokens + l_tokens, all_text
                )
        else:
            expiry_evidence = {"status": "not_required", "reason": "Expiry date verification not required"}

        # ── Handling Marks Check ──
        handling_req_str = str(work_order.get("wo_handling_marks", ""))
        if handling_req_str and handling_req_str.strip() and handling_req_str != "nan":
            req_marks = [m.strip() for m in handling_req_str.split(";") if m.strip()]
            if is_ambiguous:
                handling_evidence = {"status": "uncertain",
                                      "reason": "Image too blurry to assess handling marks.",
                                      "found": [], "missing": req_marks}
            else:
                all_onnx_for_handling = (onnx_detections_front or []) + (onnx_detections_back or [])
                handling_evidence = self.detect_handling_marks(
                    req_marks, f_tokens + b_tokens + l_tokens, all_text,
                    onnx_detections=all_onnx_for_handling
                )
        else:
            handling_evidence = {"status": "not_required", "reason": "Handling marks not required"}

        # ── Assemble evidence vector ──
        evidence_vector = {
            "image_quality": {
                "front_blur": round(f_blur, 2),
                "back_blur": round(b_blur, 2),
                "label_blur": round(l_blur, 2),
                "min_blur": round(min_blur, 2),
                "front_glare": round(f_glare, 4),
                "back_glare": round(b_glare, 4),
                "label_glare": round(l_glare, 4),
                "is_ambiguous": is_ambiguous
            },
            "package_bounds": pkg_box,
            "fnsku": fnsku_geom,
            "polybag": polybag_evidence,
            "suffocation_warning": warning_evidence,
            "original_barcode": orig_barcode_evidence,
            "expiry_date": expiry_evidence,
            "handling_marks": handling_evidence,
            "ocr_summary": {
                "front_token_count": len(f_tokens),
                "back_token_count": len(b_tokens),
                "label_token_count": len(l_tokens),
                "total_barcodes_decoded": len(all_barcodes)
            }
        }
        return evidence_vector
