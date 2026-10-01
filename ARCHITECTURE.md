# CUBE Prep Manager: System Architecture & Technical Specifications

**Pod:** 02 Prep Manager (Commerce Context Stream · Round 2)  
**Lead Engineer:** Dhanvi N. D. (`DhanviND360`)  
**Repository:** `cube26-prp-0211-dhanvind360`  

---

## 1. System Context & Commerce Chain Topology

Prep Manager functions as **Step 2 of the 5-step decentralized commerce chain**:

```text
 01 Receiving         02 Prep Compliance         03 Pack             04 Returns          05 Recovery
 ┌──────────────┐    ┌──────────────────────┐   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
 │ Physical     │───▶│ Photographic Proof   │──▶│ Package Seal │───▶│ Customer     │───▶│ Reads all    │
 │ Inbound      │    │ & Amazon Defect Gating│   │ & Box Label  │    │ Return Check │    │ 4 Records    │
 └──────────────┘    └──────────┬───────────┘   └──────────────┘    └──────────────┘    └──────▲───────┘
                                │                                                              │
                                └──────────────── Evidence Contract JSON ──────────────────────┘
```

When an inbound shipment arrives at an Amazon Fulfillment Center weeks later, Amazon frequently levies defect chargebacks (e.g. FNSKU label on seam, unsealed polybag, missing warning). Prep Manager produces an immutable, machine-readable evidence record captured at dispatch to power automated dispute resolution in Step 5.

---

## 2. End-to-End Pipeline Architecture

```text
               Physical Prepped Unit at Bench
                            │
                            ▼
          [1. Tri-View High-Speed Image Stream]
             ├── View 1: Front (Packaging & Placement)
             ├── View 2: Back (Cover & Handling Marks)
             └── View 3: Label Close-Up (FNSKU Barcode & Text)
                            │
                            ▼
         [2. Calibration & Quality Gating Engine]
             ├── Laplacian Blur Variance (Threshold >= 25.0)
             ├── Specular Glare Saturated Ratio (<= 35%)
             └── Resolution Check (>= 500x400)
                            │
                 ┌──────────┴──────────┐
                 │ Is Image Ambiguous? │
                 └──────────┬──────────┘
             YES            │            NO
     ┌──────────────────────┘            └──────────────────────┐
     ▼                                                          ▼
[Abstention]                                            [Batched Feature Engine]
Emit UNCERTAIN                                         (Rule 2: Single Unit Call)
Gating Signal                                           ├── YOLO Nano ONNX Detector
                                                        │   (31ms 640px Inference)
                                                        ├── EasyOCR / PaddleOCR Text
                                                        └── Deterministic OpenCV Spatial
                                                            ├── Edge Distance Min Margin
                                                            ├── Hough Seam Intersection
                                                            ├── Polynomial Curvature Fit
                                                            └── Seal Boundary Gradient
                                                                        │
                                                                        ▼
                                                       [Authoritative Rule Engine]
                                                       Evaluates Amazon Inbound Standards:
                                                        1. Polybag Sealed?
                                                        2. Warning Legible & Unfolded?
                                                        3. FNSKU Flat (No seam/edge/curve)?
                                                        4. Original UPC Barcode Covered?
                                                        5. Expiry Date Legible Post-Wrap?
                                                        6. Required Handling Marks Present?
                                                                        │
                                                                        ▼
                                                       [Standardized Evidence Record]
                                                        ├── Overall Status: PASS/FAIL/UNCERTAIN
                                                        ├── Exact Itemized Failure Reasons
                                                        ├── Machine-Readable Evidence Bounding Boxes
                                                        └── Performance & Cost Signature
                                                                        │
                                           ┌────────────────────────────┴────────────────────────────┐
                                           ▼                                                         ▼
                             [Step 05 Recovery Manager]                                  [Warehouse Operator Portal]
                             (Automated Dispute Filing)                                  (Live Inspection & Overrides)
```

---

## 3. Core Architectural Modules

### 3.1. Calibration & Quality Gating (`agent/calibration.py`)
- **Engineering Rule 4:** `UNCERTAIN` is a first-class verdict, never a low-confidence guess.
- Computes Laplacian variance $\sigma^2 = \text{Var}(\nabla^2 I)$.
- Images with $\sigma^2 < 25.0$ (e.g. defocus/motion blur) automatically trigger calibrated abstention.
- Images with glare ratio $> 35\%$ saturated pixels trigger optical abstention.

### 3.2. Lightweight YOLO Nano Detector (`models/best_detector.onnx`)
- Trained across 7 classes: `package`, `polybag`, `fnsku`, `warning`, `barcode`, `expiry`, `handling_mark`.
- Exported to ONNX with graph simplification and FP32/FP16 opset 19 (`11.7 MB`).
- Benchmarked via **ONNX Runtime (CPU Execution Provider)**:
  - Average latency: **31.02 ms**
  - P95 latency: **35.48 ms**
  - Throughput: **32.2 inferences / second**

### 3.3. Deterministic OpenCV Spatial Geometry (`agent/spatial_features.py`)
Rather than delegating geometric judgment to an LLM, Prep Manager executes mathematical feature extraction:
1. **Label-to-Edge Distance:** Calculates minimum Euclidean pixel clearance $d = \min(x_{label} - x_{pkg}, (x_{pkg}+w_{pkg}) - (x_{label}+w_{label}))$. Margin $< 20\text{px}$ triggers `on_edge`.
2. **Seam Overlap IoU:** Hough line transform detects vertical package seams ($x \approx 384\text{px}$). Overlap ratio $\frac{\text{Intersection}}{\text{Label Width}} > 0.10$ triggers `on_seam`.
3. **Curvature / Flatness Metric:** Evaluates text baseline linearity and contour aspect distortion. Deviation triggers `on_curve`.

### 3.4. Authoritative Amazon Rule Engine (`agent/rule_engine.py`)
Evaluates Amazon Seller Central prep requirements against work orders:
- Produces individual check statuses: `PASS`, `FAIL`, `UNCERTAIN`, `NOT_REQUIRED`.
- Overall status: `FAIL` if any applicable check fails; `UNCERTAIN` if any is ambiguous and none fail; `PASS` only when all conditions are supported by proof.
- Generates exact itemized defect strings for automated arbitration.

### 3.5. Tenancy Isolation Layer (Engineering Rule 1)
- Implemented in `scripts/test_tenancy_isolation.py` and `agent/api.py`.
- Row-Level Security partitions all records and assets by `org_id` (`org_demo_alpha` vs `org_demo_bravo`).
- Direct unit lookups require matching tenant keys. Cross-tenant queries return zero records and block key-guessing attempts.

### 3.6. Fail-Open Architecture (Engineering Rule 3)
- An unhandled camera exception, network drop, or runtime timeout triggers the fail-open fallback.
- The image buffer is preserved to disk and a compliance record is generated with `workflow_state: pending_review` and `overall_status: UNCERTAIN`.
- **The warehouse conveyor never halts.**

---

## 4. Economic Viability & Cost per Unit

A prep center earns **$0.40 to $1.10** per unit. The cost of inspection must live inside that fee.

$$\text{Cost per Unit} = \frac{\text{Model Compute} + \text{OCR / Spatial Compute} + \text{Storage} + \text{API}}{\text{Units Processed}}$$

| Component | Execution Time / Size | Cost per Unit (USD) |
|---|---|---|
| **YOLO Nano Detector (3 views)** | 93 ms total CPU | **$0.000004** |
| **OCR & Spatial Geometry** | 3,061 ms total CPU | **$0.000145** |
| **Evidence Storage (3 photos, ~60KB)** | S3 Standard / Month | **$0.000001** |
| **Deterministic Rule Engine** | 0.4 ms CPU | **$0.000000** |
| **External LLM Calls** | Zero (Not in loop) | **$0.000000** |
| **TOTAL COST PER UNIT** | **3.15 s CPU complete** | **$0.000150** |

At an average prep fee of **$0.75**, inspection cost represents **0.020%** of revenue, preserving **99.98% gross margin**.

---

## 5. Downstream Integration (Recovery Manager)

The generated evidence record conforms to `submissions/DhanviND360/contract/prep_evidence_contract.json`. 

When Recovery Manager encounters an Amazon defect chargeback on `UNIT-0003`, it extracts:
1. `record_id`: `PRP-0003`
2. `overall_status`: `FAIL`
3. `failure_reasons`: `["FNSKU label overlaps a package seam."]`
4. `evidence_regions`: Pixel bounding boxes with seam overlap IoU = 22.4%.
Recovery Manager compares this against the prep work order and inbound carrier logs to determine whether the defect existed at departure or occurred during Amazon receiving handling.
