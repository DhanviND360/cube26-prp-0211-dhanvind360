# Press Release & Frequently Asked Questions (PR/FAQ)

**FOR IMMEDIATE RELEASE**  
**Date:** 1 October 2026  
**Product:** CUBE Prep Manager  
**Contact:** Dhanvi N. D. · GitHub: [DhanviND360](https://github.com/DhanviND360)

---

## PRESS RELEASE

### CUBE Launches Autonomous Prep Compliance Agent for Amazon Inbound Shipments: Delivering 31ms Photographic Proof to Defend Against Millions in Defect Chargebacks

**BENGALURU, INDIA** — Today, the CUBE Commerce Context initiative unveiled **Prep Manager**, an edge-optimized AI compliance agent designed to sit at Step 2 of the 5-step commerce chain. By combining ultra-lightweight YOLO nano neural detectors, deterministic OpenCV spatial feature extractors, and an authoritative Amazon FBA rule engine, Prep Manager verifies 100% of outbound prepped units in real time and leaves behind machine-readable proof for automated recovery.

Amazon third-party sellers and prep centers process hundreds of millions of units annually, with prep service fees ranging between $0.40 and $1.10 per unit. Inbound defect fees—penalties levied weeks after receipt for unsealed polybags, unscannable FNSKU labels, or uncovered manufacturer barcodes—erode up to 25% of a prep center's net margin. Previously, sellers had no mechanism to disprove Amazon's automated claims.

Prep Manager changes this paradigm by capturing three standardized photographic perspectives (Front, Back, Label Close-Up) and evaluating six critical Amazon compliance checks:
1. Polybag presence and closure seal integrity.
2. Suffocation warning presence, legibility, and fold avoidance.
3. FNSKU label flatness and exclusion from seams, curves, and edges.
4. Complete coverage of original manufacturer UPC barcodes.
5. Post-wrapping expiration date legibility.
6. Required handling markings (Fragile, Liquid, This Way Up).

"A generic large language model cannot reliably measure whether a barcode is 4 millimeters away from a cardboard box seam," said Dhanvi N. D., Lead Engineer of Prep Manager. "We built an engine grounded in mathematical geometry: Hough transform seam line overlaps, edge margin ratios, contour polynomial curvature metrics, and calibrated blur gating. The total cost to verify a unit is **$0.00015**—a microscopic fraction of prep revenue—ensuring complete financial viability at scale."

Every decision is permanently recorded in a standardized JSON/CSV format directly consumable by Step 5 (Recovery Manager) to automate dispute filings and reverse chargebacks.

---

## FREQUENTLY ASKED QUESTIONS (FAQ)

### External Customer Questions

#### Q1: Does installing cameras slow down my warehouse packers?
**No.** Prep Manager follows **Engineering Rule 3: Fail Open**. The camera triggers automatically when a unit is scanned or placed on the packing surface. In ordinary operation, neural inference and spatial calculations complete in milliseconds. If an image is degraded or an anomalous camera error occurs, the unit is saved with a `pending_review` tag and **the conveyor line never stops**. Warehouse lines cannot wait, and Prep Manager never blocks an operator.

#### Q2: What happens if an image is blurred or poorly lit? Does the model guess?
**No.** Under **Engineering Rule 4**, `UNCERTAIN` is treated as a first-class verdict, not a low-confidence guess. Using Laplacian variance and illumination thresholds, the system flags insufficient quality as `UNCERTAIN` and highlights the specific quality defect (e.g. "Defocus blur score 2.6 < threshold 25.0"). Operations teams find calibrated abstention far more credible than confident hallucinated passes.

#### Q3: How does Recovery Manager use this data?
Prep Manager writes to the cross-pod evidence contract shared across all five buildathon stages using the shared `unit_id`. When Amazon flags defect fee code `PREP-04` (FNSKU on seam), Recovery Manager queries the Prep record, pulls the high-resolution front crop with the OpenCV seam overlay showing 0% IoU, and attaches the cryptographic record to an automated dispute case.

---

### Internal Hard Questions (The Questions We'd Rather Not Answer)

#### Q4: Why didn't you just use a multimodal LLM like GPT-4o or Gemini 1.5 Pro to inspect the photos with a single prompt?
**Because it fails the two most critical warehouse constraints: economics and defensibility.**
1. **Economics:** At $0.40–$1.10 gross prep price per unit, spending $0.02 to $0.05 per API call on an LLM would consume 5% to 12% of the prep center's entire top-line revenue! Our nano ONNX model and OpenCV pipeline cost **$0.00015 per check**, which is over **200x cheaper**.
2. **Defensibility:** In a disputed prep fee arbitration with Amazon Seller Support, "an LLM said it looked compliant" is worthless. Amazon requires exact proof. We provide exact pixel bounding boxes, Hough seam coordinates, edge margin millimeters, and OCR string matches.

#### Q5: What if the warehouse operator disagrees with the agent's verdict?
Under **Honesty Rule 2**, "Overrides are data." We built an interactive override mechanism in both the UI and REST API. Operators can override any verdict, but they are required to input a justification. The original verdict, the human override, the timestamp, and the operator ID are preserved in an append-only audit trail (`audit_overrides.jsonl`). These override logs form the hard negative training set for future model calibration.

#### Q6: How do you prevent multi-tenant data leaks between competing prep centers?
Per **Engineering Rule 1**, multi-tenancy isolation is enforced at the database query layer before any feature execution. Every table and search query requires a verified `org_id` (e.g. `org_demo_alpha` vs `org_demo_bravo`). Our automated test suite (`scripts/test_tenancy_isolation.py`) executes cross-tenant key-guessing attacks to guarantee that Tenant Alpha receives zero records and zero images belonging to Tenant Bravo.

#### Q7: Where does the system struggle (Known Failure Modes)?
1. **Severe specular glare on glossy polybags:** When direct overhead LED lighting reflects off high-gloss polyethylene, OCR character extraction confidence drops. Our calibration engine detects saturated pixel ratios (>35%) and abstains with `UNCERTAIN` rather than guessing.
2. **Cylindrical package labels with high curvature:** While flat packages and vertical seams achieve near-perfect classification, small diameter bottles require multi-angle rotational stitching. We conservatively flag severe aspect ratio distortions as `on_curve`.
