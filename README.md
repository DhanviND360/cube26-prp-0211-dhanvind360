# CUBE Buildathon · Pod 02: Prep Manager

**Commerce Context Stream · Round 2 Individual Build**  
**Participant:** Dhanvi N. D. (`DhanviND360`)  
**Repository:** `cube26-prp-0211-dhanvind360`  
**Submission Package:** [`submissions/DhanviND360/`](submissions/DhanviND360/README.md)  
**Architecture Specification:** [`ARCHITECTURE.md`](ARCHITECTURE.md)  
**Evidence Contract:** [`contract/prep_evidence_contract.json`](contract/prep_evidence_contract.json)  

---

## 1. Problem Understanding

### 1.1 Context in the Commerce Chain
Prep Manager operates as **Step 2 in the 5-step decentralized commerce chain**:

```text
 01 Receiving         02 Prep Compliance         03 Pack             04 Returns          05 Recovery
 ┌──────────────┐    ┌──────────────────────┐   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
 │ Physical     │───▶│ Photographic Proof   │──▶│ Package Seal │───▶│ Customer     │───▶│ Reads all    │
 │ Inbound      │    │ & Amazon Defect Gating│   │ & Box Label  │    │ Return Check │    │ 4 Records    │
 └──────────────┘    └──────────┬───────────┘   └──────────────┘    └──────────────┘    └──────▲───────┘
                                │                                                              │
                                └──────────────── Evidence Contract JSON ──────────────────────┘
```

A physical unit arrives at an Amazon prep center or 3PL warehouse. Human warehouse operators prep the unit for Amazon Fulfillment Center (FC) inbound shipment. 

### 1.2 The Core Problem: Unplanned Prep Penalties & Chargebacks
If prep execution violates Amazon's strict inbound specifications, Amazon levies **unplanned prep defect fees ($1.85 to $4.20 per unit)**. These fines arrive 4 to 8 weeks later, attached to inbound shipments that warehouse operators no longer remember. Without immutable photographic and spatial proof recorded at dispatch, sellers and prep centers have no defense against Amazon chargebacks or inbound inventory discrepancies.

### 1.3 The 6 Mandated Amazon FBA Visual Compliance Checks
1. **Polybag Sealed:** Polybag present and correctly sealed (impulse heat seal or suffocation-warning tape).
2. **Suffocation Warning:** Mandatory on bags with opening $\ge 5$ inches; must be unobstructed by folds, clearly legible, and printed in required font size.
3. **FNSKU Label Placement:** FNSKU barcode must be flat, centered, and NOT placed across package edges ($<20\text{px}$ margin), curves, or center packaging seams ($>10\%$ IoU).
4. **Original Barcode Covered:** Manufacturer UPC/EAN barcode must be fully obscured to prevent Amazon receiving scanners from scanning the wrong barcode.
5. **Expiry Date Legibility:** Food, topical, and consumable expiration dates must remain legible post-wrapping.
6. **Handling Marks:** Mandated orientation and safety marks (`FRAGILE`, `LIQUID`, `THIS WAY UP`) must be affixed and unobstructed.

### 1.4 The Economic Constraint
Prep centers operate on thin margins (**$0.40 to $1.10 gross revenue per unit**). Every single unit must be inspected. The inspection cost must live strictly under $0.075/unit (10% of revenue). Our solution achieves **$0.00015/unit** (500x below budget).

---

## 2. Solution Overview

Prep Manager is an enterprise-grade, high-speed visual inbound compliance engine powered by **Gemini 3.6 Flash multimodal AI visual reasoning, lightweight optical calibration gating, and standardized evidence persistence**.

```text
       Physical Capture (Front / Back / Label)
                         │
                         ▼
       [Optical Quality Calibration Gating]
       (Laplacian Blur Variance >= 25.0, Glare Ratio <= 0.35)
                         │
        ┌────────────────┴────────────────┐
        │ Pass Quality?                   │
        ├─────────────────┬───────────────┤
       YES                │              NO
        ▼                 │               ▼
 [Gemini 3.6 Flash Agent] │        [Abstention Gate]
 (Multimodal Visual Reasoning)     Emit UNCERTAIN Verdict
        │                 │        Triage to Supervisor Bench
        ▼                 │
 [6 FBA Compliance Checks]│
 (Seal, Warn, FNSKU, UPC, │
  Expiry, Handling Marks) │
        │                 │
        └─────────────────┼───────────────┐
                          ▼               ▼
             [Standardized Evidence Record JSON]
             (PASS / FAIL / UNCERTAIN Gating)
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
 [Conveyor Sorter / UI]       [Recovery Manager Handoff]
 (Pass Chute vs Rework Queue)  (Dispute Claim Filing)
```

### Key Technical Pillars
* **Multimodal AI Agent (`gemini-3.6-flash`):** Evaluates all 3 packaging perspectives against work orders and Amazon FBA packaging rules using advanced visual perception.
* **New Comprehensive Packaging Dataset (`C:\Dhanvi\HACKATHONS\CUBE_2026_dataset\packaging_dataset`):** 324 annotated photographic captures spanning 4 operational grids (`compliance_scenarios`, `inspection_reference`, `inspection_examples`, `packaged_products`).
* **Ultra-Low Memory Footprint (<80MB RAM):** Removed bulky PyTorch/EasyOCR dependencies to guarantee 100% stability on Render's 512MB free-tier container without Out-Of-Memory (OOM) errors.
* **Six Mandated Amazon Compliance Checks:** Evaluates polybag presence & seal, suffocation warning, FNSKU margins & flatness, original barcode coverage, expiration date legibility, and handling markings.
* **First-Class `UNCERTAIN` Handling:** Evidence-driven decisions; insufficient visual evidence results in `UNCERTAIN` rather than guessing.
* **Fail-Open Architecture (Rule 3):** Preserves compliance records and marks status as `pending_review` in case of unhandled exceptions, keeping warehouse lines running smoothly.
* **Tenancy Isolation (Rule 1):** Scoped by organization ID (`org_demo_alpha`, `org_demo_bravo`) with tenant-isolated evidence storage.
* **Dual-Tier UI & Deployment:**
  1. **Next.js App Router Frontend:** Pure CSS vector industrial interface matching factory floor designs (Blast Door Home, Vault Upload, Animated Conveyor Belt with Double-Click 3-Box Evidence Modal, and 5-Tab Executive Operations Dashboard).
  2. **Self-Contained Client-Side ML Engine (`frontend/src/lib/prep-pipeline.ts`):** 10 curated test samples executing entirely in TypeScript, ready for instant, zero-backend deployment on **Vercel**.
  3. **FastAPI Production Backend (`agent/api.py`):** High-throughput microservice supporting SSE streaming, batch processing, and Supabase integration.

---

## 3. Setup & Installation

### 3.1 Prerequisites
* **Python:** 3.10 or 3.11
* **Node.js:** 18.x or 20.x
* **OS:** Windows, Linux, or macOS

### 3.2 Backend Setup (FastAPI + ONNX Runtime)
```bash
# Clone the repository
git clone https://github.com/DhanviND360/cube26-prp-0211-dhanvind360.git
cd cube26-prp-0211-dhanvind360

# Create and activate Python virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI ML microservice on port 8000
python -m uvicorn agent.api:app --host 127.0.0.1 --port 8000
```

### 3.3 Frontend Setup (Next.js 14)
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Option A: Run development server
npm run dev

# Option B: Run optimized production build
npm run build
npm start
```
The application will be accessible at `http://localhost:3000`.

### 3.4 Instant Vercel Deployment (Demo Ready)
The frontend contains an embedded, zero-dependency client-side ML pipeline preloaded with 10 test samples.
1. Push repository to GitHub.
2. In Vercel, click **Add New Project** &rarr; Import `cube26-prp-0211-dhanvind360`.
3. Set **Root Directory** to `frontend`.
4. Click **Deploy**. Vercel will build and host the interactive demo instantly.

---

## 4. Usage & Workflows

### 4.1 Interactive Factory Floor Inspection Flow
1. **Screen 1 (Blast Door Homepage):** Click **START ▶** to enter the inbound preparation portal.
2. **Screen 2 (Choose Files Vault):**
   * Drag & drop product camera files, or click **Choose Files**.
   * Or click any of the **10 quick verified test unit chips** (e.g. `UNIT-POLY-0001` for sealed polybag PASS, `UNIT-POLY-OPEN` for unsealed defect, `UNIT-0003` for seam defect).
   * Click **RUN INBOUND INSPECTION ▶**.
3. **Screen 3 (Factory Conveyor Sorting):**
   * Real-time progress bar streams inspection milestones.
   * A 3D cardboard box appears on the conveyor belt and automatically routes to the **green `PASSED` chute** (PASS) or the **red `FAILED` chute** (FAIL).
   * **Double-click the cardboard box** to open the **3-Box Inspection Evidence Modal**:
     * **Box 1:** Original physical capture with Front, Back, and Label macro view tabs.
     * **Box 2:** What ML inferred (Interactive Canvas with Package bounds, Polybag seal, FNSKU bounding box, and deterministic spatial measurements).
     * **Box 3:** Complete ML output conforming to `prep_evidence_contract.json` (verdict, defect reasons, Amazon FBA rule breakdown, latency, compute economics, and JSON export).

### 4.2 Executive Operations & Compliance Dashboard
Switch to the **"📊 Operations & Intelligence Dashboard"** tab in the top navigation to view 5 real-time operational views:
* **Operations Overview:** Processed unit volume, first-pass yield rate, processing throughput (1,420 units/hr), latency, and real-time inbound warehouse queue.
* **Compliance Intelligence:** Per-check accuracy, defect rates, and root cause failure mode statistics for Polybag, Warning, FNSKU, Barcode, Expiry, and Handling Marks.
* **Evidence & Traceability:** Audit image viewer, raw JSON contract vectors, and deterministic rule logs for any selected unit.
* **Economics & Margin:** Cost per image/unit ($0.00015), Amazon penalty savings ($1.85–$4.20/unit prevented), and preserved net operating margin.
* **Downstream Handoff:** Stage 2 handoff contracts for **Pod 05 Recovery Manager** (`FBA_CONVEYOR_PASSED` vs `REWORK_DISPOSITION_QUEUE` vs `MANUAL_SUPERVISOR_BENCH`), including remedy instructions and dispute payloads.

### 4.3 Automated Verification Scripts
```bash
# 1. Run Headless Single-Unit Inspection
python -c "
import cv2, pandas as pd
from agent.prep_agent import PrepManagerAgent
agent = PrepManagerAgent()
df = pd.read_csv('cube_prep_dataset/cube_prep_dataset.csv')
row = df.iloc[0]
rec = agent.inspect_unit('UNIT-0001', cv2.imread('cube_prep_dataset/images/UNIT-0001_front.jpg'), cv2.imread('cube_prep_dataset/images/UNIT-0001_back.jpg'), cv2.imread('cube_prep_dataset/images/UNIT-0001_label.jpg'), row.to_dict())
print('Status:', rec['overall_status'], '| Latency:', rec['performance']['latency_ms'], 'ms')
"

# 2. Test Multi-Tenancy Isolation (Rule 1)
python scripts/test_tenancy_isolation.py

# 3. Evaluate Offline Splits (Validation & Test Sets)
python scripts/evaluate_models.py

# 4. Benchmark Unit Economics & Hardware Throughput
python scripts/benchmark_economics.py

# 5. Run Full End-to-End Production API Smoke Tests
python scripts/test_end_to_end_production.py
```

---

## 5. Assumptions and Limitations

### 5.1 System Assumptions
* **Camera Setup:** Assumes 3 synchronized physical perspectives per unit: Front view (primary packaging and placement), Back view (reverse packaging and barcode coverage), and Macro Label view (high-resolution close-up of FNSKU barcode and text).
* **Optical Environment:** Assumes standard warehouse bench illumination ($>300\text{ lux}$) and camera resolution of at least $640\times 480\text{ pixels}$.
* **Label Format:** Assumes standard Amazon FBA FNSKU barcodes (Code 128 / PDF417) and human-readable alphanumeric text beginning with `X00`.
* **Multi-Tenancy:** Assumes requests supply an `X-Org-ID` header partitioning database records, storage files, and metrics. Defaults to `org_demo_alpha` if omitted.

### 5.2 Known Limitations & Edge Cases
* **Severe Specular Glare:** Highly reflective, crinkled polybags under direct spotlighting can cause localized saturation. The agent correctly abstains with `UNCERTAIN` (glare ratio $>0.35$) rather than hallucinating barcode digits.
* **Transparent Packaging Seams:** Ultra-clear polybag heat seals on clear products can have low edge contrast; our system uses combined HSV color masking, reflection sheen, and suffocation warning presence to establish polybag presence.
* **Language Support:** Suffocation warning OCR is optimized for English, Spanish, and French (standard Amazon North America prep requirements). Other languages are supported via EasyOCR fallback.
* **Batch Single-Call Bound:** Units are processed as single atomic units carrying all 3 views simultaneously (Rule 2). Sequential multi-unit queues are limited to 10 concurrent in-flight units per node under the default concurrency limiter.

---

## 6. Evaluation Results Summary

| Metric | Validation Set (15 Units) | Held-Out Test Set (15 Units) | Target Threshold |
| :--- | :---: | :---: | :---: |
| **Accuracy** | **86.7%** | **73.3%** | $\ge 70.0\%$ |
| **Macro-F1 Score** | **0.8030** | **0.7037** | $\ge 0.650$ |
| **Abstention Rate (`UNCERTAIN`)** | **13.3%** | **20.0%** | $\le 25.0\%$ |
| **Average Inference Latency** | **31.02 ms** | **28.45 ms** | $< 100.0\text{ ms}$ |
| **Throughput (Single Node)** | **32.2 units/sec** | **35.1 units/sec** | $> 10\text{ units/sec}$ |
| **Compute Cost per Unit** | **$0.00015** | **$0.00015** | $\le \$0.075$ |
| **Tenancy Isolation Leakage** | **0.00% (0 / 100)** | **0.00% (0 / 100)** | $0.00\%$ |
| **False Positive Abstentions** | **0** | **0** | $0$ |

---

## 7. Downstream Contract & Recovery Manager Interoperability

Prep Manager output conforms strictly to `prep_evidence_contract.json`. The output record generated for each unit contains:
* Complete unit, work order, and tenant identifiers (`record_id`, `unit_id`, `org_id`, `work_order_id`, `sku`, `asin`, `fnsku`).
* Overall compliance verdict (`PASS`, `FAIL`, or `UNCERTAIN`).
* Itemized check breakdown for all 6 Amazon prep rules.
* Exact failure reasons and plain-English explanations.
* Normalized spatial evidence bounding boxes for packaging, polybag, and FNSKU label.
* Downstream handoff object directing Step 05 Recovery Manager on whether to accept the unit for inbound shipment, route it to the rework station, or assemble an automated dispute claim against Amazon chargebacks.

---

*CUBE Buildathon · Commerce Context Stream · Pod 02: Prep Manager*
