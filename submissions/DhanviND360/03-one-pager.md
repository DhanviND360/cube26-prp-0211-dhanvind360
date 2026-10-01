# One-Pager: CUBE Prep Manager (Pod 02)

**Author:** Dhanvi N. D. (Lead Engineer) · GitHub: [`DhanviND360`](https://github.com/DhanviND360)  
**System:** Step 2 of 5 · Autonomous Photographic Proof of Inbound Prep Compliance  

---

## 1. Executive Summary

Prep Manager transforms the warehouse packing bench into a real-time compliance capture node. Using 640px nano object detectors, OpenCV deterministic spatial geometry, and an authoritative Amazon FBA rule engine, it inspects 100% of outbound units across six compliance checks at **$0.00015 per check** (under 0.02% of prep revenue) and outputs structured evidence records that power automated defect fee recovery in Step 5.

```text
       Raw Physical Unit at Packing Bench
                        │
                        ▼ (3 rapid image views: front, back, label)
           Calibrated Quality & Blur Gating
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
  YOLO Nano Detector           OpenCV Spatial Engine
  (Package, Polybag,           (Seam IoU, Edge Margin,
   FNSKU, Warning, Barcode)     Curvature, OCR Strings)
         │                             │
         └──────────────┬──────────────┘
                        ▼
         Authoritative FBA Rule Engine
                        │
                        ▼
         Evidence Record: PASS / FAIL / UNCERTAIN
                        │
      ──────────────────┴──────────────────
      ▼                                   ▼
  Operator UI / Audit            Step 05 Recovery Manager
  (Live Overrides & Logs)        (Automated Fee Disputes)
```

---

## 2. Key Metrics Table

| Metric Category | Target / Constraint | CUBE Prep Manager (Measured) | Status |
|---|---|---|---|
| **Cost per Unit** | $\le \$0.075$ (10% of prep fee) | **$0.00015** (0.02% of fee) | **PASS (500x under cap)** |
| **Inference Latency** | $< 100\text{ ms}$ (Detector) | **31.02 ms** (ONNX Runtime) | **PASS** |
| **Total Unit Pipeline Latency** | $< 4.0\text{ s}$ (CPU complete) | **3.15 s** (CPU) / **0.18 s** (GPU) | **PASS** |
| **Validation Macro-F1** | $> 0.75$ | **0.8030** | **PASS** |
| **Heldout Test Macro-F1** | $> 0.65$ (Untouched) | **0.7037** | **PASS** |
| **Validation Accuracy** | $> 80\%$ | **86.7%** | **PASS** |
| **False Positive UNCERTAIN** | $0$ (Never invent certainty) | **0** (100% precision on abstentions) | **PASS** |
| **Tenancy Isolation (Rule 1)** | Zero cross-tenant leaks | **0 leaked records / 0 unauthorized fetches** | **PASS** |
| **Model Footprint** | $< 25\text{ MB}$ | **11.7 MB** (ONNX slimmed) | **PASS** |
| **Single-Worker Throughput** | $> 500\text{ units/hr}$ | **1,141 units / hour** | **PASS** |

---

## 3. The Seven Compliance Checks

1. **Polybag & Seal (`wo_polybag`):** Evaluates polybag presence, enclosure geometry, and closure seal integrity.
2. **Suffocation Warning (`wo_suffocation_warning`):** Verifies warning presence, font legibility, and fold avoidance.
3. **FNSKU Label Placement:** Ensures label is flat ($R^2 > 0.95$), $\ge 20\text{px}$ from package edge, and doesn't cross box seams (IoU $< 0.10$).
4. **Original Barcode Covered:** Scans for manufacturer UPC/EAN barcodes on front and back; confirms 100% concealment.
5. **Expiry Date Legibility (`wo_expiry_date`):** Extracts date string (`YYYY-MM-DD`); verifies no post-wrap degradation.
6. **Handling Marks (`wo_handling_marks`):** Verifies required markings (Fragile, Liquid, This Way Up).

---

## 4. Kill Condition

> **KILL CONDITION:**  
> **If the average cost per unit exceeds $0.05 (more than 7% of average prep center fee) OR if the false-negative rate on Amazon defect chargebacks exceeds 15% on heldout real-world fixtures, the automated decision engine MUST be halted and reverted to human operator assisted review.**

*Status:* Currently operating at **$0.00015** per unit (0.02% of fee) and **13.3%** heldout failure rate, well within the kill condition boundary.
