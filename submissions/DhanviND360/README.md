# DhanviND360 · CUBE Prep Manager (Pod 02)

**Commerce Context Stream · Round 2 · Individual Build**  
**Participant:** Dhanvi N. D. · GitHub: [`DhanviND360`](https://github.com/DhanviND360)  
**Repository:** [`cube26-prp-0211-dhanvind360`](https://github.com/DhanviND360/cube26-prp-0211-dhanvind360)  

> *"Five agents, one unit, one record that follows it. You build the agent that makes one of those judgments, and leaves proof."*

---

## Deliverables & Repository Layout

```text
submissions/DhanviND360/
├── README.md               ← This file: Index, status, and summary
├── 01-customer-letter.md   ← Customer letter to warehouse prep center owners
├── 02-prfaq.md             ← PR/FAQ including hard internal questions
├── 03-one-pager.md         ← Metrics table + single-line kill condition
├── CLAUDE.md               ← Durable constraints, economic bounds, forbidden language
├── build-brief.md          ← Problem statement, design decisions, deliverables
├── build-log.md            ← Engineering diary tracking every step
├── eval-report.md          ← Quantitative metrics, confusion matrices, failure modes
├── contract/
│   ├── prep_evidence_contract.json  ← Cross-pod evidence record JSON Schema
│   └── README.md                    ← Contract documentation & Recovery Manager integration
├── agent/
│   ├── prep_agent.py       ← Unified single-call inference pipeline (Rule 2)
│   ├── spatial_features.py ← Deterministic OpenCV spatial feature extractor
│   ├── rule_engine.py      ← Authoritative Amazon FBA rule evaluation engine
│   ├── calibration.py      ← Quality gating, abstention, and fail-open manager (Rule 3)
│   ├── api.py              ← FastAPI REST service with tenancy isolation (Rule 1)
│   └── ui.py               ← Streamlit warehouse operator portal
└── records/
    ├── compliance_records.csv       ← Standardized CSV export of all 100 units
    ├── compliance_records.json      ← Combined JSON evidence records
    └── units/                       ← Individual unit JSON files (UNIT-0001.json ... UNIT-0100.json)
```

---

## Status Table

| Face | Deliverable | Status | Evidence Link |
|---|---|---|---|
| **1** | Customer letter, PR/FAQ, one-pager | ☑ **Completed** | [`01-customer-letter.md`](01-customer-letter.md) · [`02-prfaq.md`](02-prfaq.md) · [`03-one-pager.md`](03-one-pager.md) |
| **2** | CLAUDE.md (Durable constraints) | ☑ **Completed** | [`CLAUDE.md`](CLAUDE.md) |
| **3** | Headless agent on fixtures | ☑ **Completed** | [`agent/prep_agent.py`](agent/prep_agent.py) |
| **4** | Eval report (Heldout test & failure modes) | ☑ **Completed** | [`eval-report.md`](eval-report.md) |
| **5** | Evidence record page & UI | ☑ **Completed** | [`../../app.py`](../../app.py) & [`records/`](records/) |
| **6** | Cross-pod contract | ☑ **Completed** | [`contract/prep_evidence_contract.json`](contract/prep_evidence_contract.json) |

---

## Kill Condition

> **If the average cost per unit exceeds $0.05 (more than 7% of average prep fee) OR if the false-negative rate on Amazon defect chargebacks exceeds 15% on heldout real-world fixtures, the automated decision engine MUST be halted and reverted to human operator assisted review.**

*Status:* Operating at **$0.00015** per unit (0.02% of fee) and **13.3%** heldout failure rate.

---

## Quick Start & Verification

### 1. Run Interactive Operator Dashboard
```bash
streamlit run app.py
```
*Provides real-time inspection, 3-view photo canvas, OpenCV bounding box & seam overlays, human override audit logging, and tenancy switcher.*

### 2. Run Headless Single-Unit Inspection
```bash
python -c "
import cv2, json, pandas as pd
from agent.prep_agent import PrepManagerAgent
agent = PrepManagerAgent()
df = pd.read_csv('cube_prep_dataset/cube_prep_dataset.csv')
row = df.iloc[0]
rec = agent.inspect_unit('UNIT-0001', cv2.imread('cube_prep_dataset/images/UNIT-0001_front.jpg'), cv2.imread('cube_prep_dataset/images/UNIT-0001_back.jpg'), cv2.imread('cube_prep_dataset/images/UNIT-0001_label.jpg'), row.to_dict())
print('Verdict:', rec['overall_status'], '| Latency:', rec['performance']['latency_ms'], 'ms')
"
```

### 3. Verify Tenancy Isolation (Rule 1)
```bash
python scripts/test_tenancy_isolation.py
```

### 4. Run Full Evaluation Suite (Rule 4)
```bash
python scripts/evaluate_models.py
```

### 5. Benchmark Unit Economics & Margins
```bash
python scripts/benchmark_economics.py
```
