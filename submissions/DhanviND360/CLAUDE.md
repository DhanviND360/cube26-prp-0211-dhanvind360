# Engineering & Operational Constraints (CLAUDE.md)

**System:** CUBE Prep Manager (Step 2 of 5)  
**Lead:** Dhanvi N. D. (`DhanviND360`)  
**Scope:** Inbound Amazon Prep Compliance & Evidence Engine  

---

## 1. Durable Engineering Constraints (Non-Negotiable)

1. **Tenancy Isolation Before Any Feature (Rule 1):**
   - Every database query, record fetch, image resolution, and API response MUST be strictly scoped to `org_id` (`org_demo_alpha` or `org_demo_bravo`).
   - If an unauthorized tenant requests a foreign `unit_id`, return HTTP 404 (do NOT reveal record existence).
   - Test key-guessing attacks in automated CI (`scripts/test_tenancy_isolation.py`).

2. **Batch Model Calls (Rule 2):**
   - Make **one single call per unit** carrying all checks across all views (`front`, `back`, `label`).
   - Never execute separate neural network inferences per check. At warehouse scale, per-check calls destroy margins.

3. **Fail Open (Rule 3):**
   - If any exception, timeout, unreadable image, or camera crash occurs, the pipeline MUST catch the error, save the captured image stream, and emit a record marked `workflow_state: pending_review` with verdict `UNCERTAIN`.
   - **Never block the conveyor line or make warehouse workers wait.**

4. **UNCERTAIN is a First-Class Verdict (Rule 4):**
   - `UNCERTAIN` is NOT a low-confidence PASS.
   - If image quality (Laplacian blur $< 25.0$, specular glare $> 35\%$) or geometric ambiguity prevents a definitive call, abstain with `UNCERTAIN`.
   - Never guess or invent compliance.

5. **Look Authoritative Rules Up (Rule 5):**
   - Do NOT guess Amazon prep requirements from sample CSV columns or model memory.
   - Code decisions must strictly reflect Amazon's published Seller Central prep standards.

---

## 2. Hard Economic Constraints

- **Unit Economics Bound:** Prep center fees range from **$0.40 to $1.10** per unit.
- **Maximum Allowable Compute Cost:** Cannot exceed **$0.04** per unit (10% of minimum prep price).
- **Current System Performance:** **$0.00015** per unit (0.02% of prep price). Preserve this margin.

---

## 3. Honesty Rules

- **Overrides are Data:** Every time an operator changes an agent verdict in the UI or API, log the original verdict, new verdict, reason, and operator ID to `reports/audit_overrides.jsonl`. Never discard override rows.
- **No Hallucinated Claims:** Do NOT call a content hash an "immutable blockchain anchor" unless cryptographically implemented. Say what was built.
- **Report Exact Numbers:** Do not use vague terms like "it works well". Report precision, recall, F1, FP, and FN separately.

---

## 4. Forbidden Language & Marketing Traps

The following terms and concepts are strictly forbidden in internal documentation, commit messages, and customer interfaces:
- ❌ *"AI-Powered Magic"* or *"Autonomous Omniscient Judgments"*
- ❌ *"100% Guaranteed Zero Defect Proof"*
- ❌ *"LLM-Driven Compliance Verification"* (LLMs do not make deterministic spatial decisions)
- ❌ *"Proprietary Black Box Deep Learning"*
- ❌ Silent discarding of operator overrides or edge case errors
