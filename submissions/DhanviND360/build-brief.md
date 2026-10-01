# Build Brief: CUBE Prep Manager (Pod 02)

**Author:** Dhanvi N. D. (`DhanviND360`)  
**Round:** Round 2 Individual Build · CUBE Buildathon 2026  
**Problem Statement:** Inbound Amazon Prep Compliance & Defect Fee Evidence Engine  

---

## 1. Problem Context & Workflow

Step 2 of the 5-step commerce chain sits between Receiving (Step 1) and Pack (Step 3).

```text
  [01 Receiving] ──▶ [02 Prep Manager] ──▶ [03 Pack] ──▶ [04 Returns] ──▶ [05 Recovery]
  Inbound parcel      Visual compliance     Box sealed    Disposition      Claims & fees
```

When units are prepped for Amazon FBA inbound shipments, prep centers charge $0.40–$1.10. Weeks later, Amazon issues defect fees for alleged prep errors. The prep center has only a work order and no defensive proof.

### The Agent's Visual Scope
From 3 photographs (Front, Back, Label Close-Up):
1. Polybag presence and seal closure
2. Suffocation warning presence, font legibility, and fold avoidance
3. FNSKU label flatness and exclusion from seams, curves, and edges
4. Complete coverage of original manufacturer barcode
5. Post-wrapping expiration date legibility
6. Required handling marks (Fragile, Liquid, This Way Up)

---

## 2. Architecture & Design Principles

1. **Deterministic Grounding:** Avoid LLM hallucinations by computing mathematical OpenCV spatial metrics (Hough seam intersection, label-to-edge pixel margins, polynomial baseline curvature).
2. **Nano Detection + OCR:** Ultra-lightweight YOLOv8n / YOLO11n exported to ONNX Runtime (31ms inference, 11.7MB) combined with PaddleOCR / EasyOCR and PyZBar.
3. **Calibrated Abstention:** Low-quality imagery (blur score $< 25.0$) automatically yields `UNCERTAIN` rather than guessing.
4. **Tenancy Isolation:** Row-level security scoped strictly to `org_id` (Alpha vs Bravo).
5. **Fail-Open Operational Safety:** Pipeline errors generate `pending_review` records and never halt conveyor lines.

---

## 3. Deliverables Checklist

- [x] Unified Prep Agent pipeline (`agent/prep_agent.py`)
- [x] Deterministic OpenCV spatial feature extractor (`agent/spatial_features.py`)
- [x] Authoritative Amazon FBA rule engine (`agent/rule_engine.py`)
- [x] Calibration and fail-open manager (`agent/calibration.py`)
- [x] ONNX Runtime nano detector model (`models/best_detector.onnx`)
- [x] Cross-pod JSON evidence schema (`contract/prep_evidence_contract.json`)
- [x] Exported compliance records for all 100 units (`records/compliance_records.csv`)
- [x] Tenancy isolation test suite (`scripts/test_tenancy_isolation.py`)
- [x] Full evaluation & failure mode report (`eval-report.md`)
- [x] Interactive Streamlit Operator Portal & REST API (`app.py` & `agent/api.py`)
