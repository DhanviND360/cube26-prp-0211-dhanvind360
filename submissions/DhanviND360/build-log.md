# Build Log: CUBE Prep Manager (Pod 02)

**Engineer:** Dhanvi N. D. (`DhanviND360`)  
**Repository:** `cube26-prp-0211-dhanvind360`  

---

### Step 1: Repository Exploration & Environment Preparation
- Cloned repository `cube26-prp-0211-dhanvind360`.
- Located `cube_prep_dataset` (100 synthetic units × 3 views = 300 images) and integrated it into the submission codebase.
- Verified Python 3.11 environment. Confirmed CPU host execution.
- Installed required computer vision, detection, and OCR dependencies: `ultralytics`, `opencv-contrib-python`, `onnx`, `onnxruntime`, `onnxslim`, `pyzbar`, `paddleocr`, `paddlepaddle`, `easyocr`, `pytesseract`.

### Step 2: Dataset Validation & Zero-Leakage Split Verification
- Executed `scripts/validate_dataset.py`.
- Verified 300/300 image paths exist and load cleanly.
- Verified unit grouping: 70 train / 15 validation / 15 heldout test units.
- Confirmed zero unit-level leakage across train, val, and test splits ($0$ overlaps).
- Confirmed 20 distinct failure and compliance scenarios represented across 50 Alpha and 50 Bravo tenant units.

### Step 3: YOLO Detector Training & ONNX Export
- Generated bounding box dataset annotations (`scripts/generate_yolo_annotations.py`) across 7 classes (`package`, `polybag`, `fnsku`, `warning`, `barcode`, `expiry`, `handling_mark`).
- Conducted controlled model training experiments across YOLOv8n and YOLO11n architectures with seeds 42 and 101, frozen-backbone warmup, and early stopping.
- Selected top checkpoint based on validation macro-F1.
- Exported model to ONNX format with ONNX Slim optimization (`models/best_detector.onnx`, 11.7 MB).
- Benchmarked ONNX Runtime execution: **31.02 ms average latency**, **32.2 inferences/sec throughput**.

### Step 4: Deterministic OpenCV Spatial Features & Rule Engine
- Built `agent/spatial_features.py`:
  - Laplacian blur variance metric ($< 25.0$ threshold)
  - Distance from FNSKU label to package boundary
  - Hough line transform center seam intersection (IoU)
  - Curved surface aspect distortion metric
  - Specular glare ratio computation
- Built `agent/rule_engine.py`:
  - Authoritative Amazon FBA rule evaluation for Polybag, Warning, FNSKU, Barcode, Expiry, and Handling Marks.
  - Generates itemized failure reasons, exact measurement evidence regions, and calibrated abstention reasons.

### Step 5: Unified Single-Call Pipeline (Rule 2) & Fail-Open Safety (Rule 3)
- Built `agent/prep_agent.py` carrying all 6 checks across 3 views in a single unit call.
- Integrated `agent/calibration.py` to guarantee fail-open safety (saving captures and marking `pending_review` upon any unexpected fault).

### Step 6: Full Split Evaluation & Failure Mode Analysis
- Ran `scripts/evaluate_models.py` keeping the heldout test set strictly untouched until final evaluation:
  - **Validation:** 86.7% accuracy, 0.8030 Macro-F1, 13.3% UNCERTAIN rate.
  - **Heldout Test:** 73.3% accuracy, 0.7037 Macro-F1, 20.0% UNCERTAIN rate.
  - Zero false positives on UNCERTAIN abstentions.

### Step 7: Unit Economics Benchmarking
- Executed `scripts/benchmark_economics.py`:
  - Total compute and storage cost: **$0.00015 per unit**.
  - Compared against prep center price of **$0.75**: consumes **0.020%** of fee.
  - Preserves **99.98% gross margin**.

### Step 8: Multi-Tenancy Verification & Contract Export
- Executed `scripts/test_tenancy_isolation.py`:
  - Verified row-level security for `org_demo_alpha` and `org_demo_bravo`.
  - Blocked cross-tenant key-guessing attacks with 0 data leaks.
- Generated cross-pod contract `prep_evidence_contract.json` and exported all 100 unit JSON/CSV records.
- Built interactive Streamlit application (`app.py`) with visual evidence overlays, override audit logs, and tenancy switching.

### Step 9: Production Architecture & Real-Time Streaming Preparation
- Decoupled cloud architecture: Vercel (Next.js frontend) + Render/Fly.io (FastAPI ML backend) + Supabase (PostgreSQL with RLS, S3-compatible storage, Realtime).
- Created cloud storage abstraction (`agent/storage.py`) supporting local filesystem and Supabase Storage without vendor lock-in.
- Created database abstraction (`agent/db.py`) supporting local SQLite/JSON and Supabase PostgreSQL with RLS policies.
- Implemented real-time progressive streaming pipeline (`agent/pipeline.py`) emitting Server-Sent Events (SSE) as each perspective completes analysis (`front_completed` -> `back_completed` -> `label_completed` -> `inspection_completed`).
- Built production deployment assets:
  - `Dockerfile` (multi-stage Python 3.11 with OpenCV & ZBar)
  - `render.yaml` (Render Blueprint for one-click backend deploy)
  - `fly.toml` (Fly.io container config)
  - `vercel.json` (Vercel edge rewrites & security headers)
  - `supabase/migrations/20261001000000_init_prep_manager.sql` (PostgreSQL tables, RLS policies, and storage bucket security)
  - `frontend/types/prep-evidence.ts` & `frontend/lib/api-client.ts` (TypeScript client contract for future Next.js dashboard)
  - `DEPLOYMENT.md` (Step-by-step production runbook)
- Executed production test suite (`scripts/test_production_pipeline.py`): 100% tests passed. All ML models, contracts, and verdicts preserved with zero drift.
