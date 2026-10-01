"""
FastAPI REST API Service for CUBE Prep Manager (Pod 02).
Provides:
- POST /inspect: Process 3 views + work order into evidence record
- GET /records: Fetch records scoped to tenant org_id
- GET /records/{unit_id}: Retrieve single evidence record
- POST /override: Record human operator override with audit trail
- GET /health: Health check and status
- GET /metrics: Cost and throughput statistics
"""

import os
import json
import time
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Header, HTTPException, Query, Body
from pydantic import BaseModel

from agent.prep_agent import PrepManagerAgent

app = FastAPI(
    title="CUBE Prep Manager API",
    description="Step 2 of Commerce Context Chain: Visual Inbound Prep Compliance & Evidence Engine",
    version="2.0.0"
)

agent = PrepManagerAgent()

OVERRIDE_LOG_FILE = "reports/audit_overrides.jsonl"
RECORDS_CSV = "data/compliance_records.csv"
RECORDS_JSON = "submissions/DhanviND360/records/compliance_records.json"

class WorkOrderRequest(BaseModel):
    unit_id: str
    work_order_id: Optional[str] = "WO-3000"
    fba_shipment_id: Optional[str] = "FBA-CUBE-100"
    sku: Optional[str] = "SKU-SAMPLE"
    asin: Optional[str] = "B0DUMMY"
    fnsku: Optional[str] = "X00CUBE"
    wo_polybag: Optional[bool] = False
    wo_suffocation_warning: Optional[bool] = False
    wo_expiry_date: Optional[bool] = False
    wo_handling_marks: Optional[str] = ""
    prep_price_usd: Optional[float] = 0.75

class OverrideRequest(BaseModel):
    unit_id: str
    original_verdict: str
    new_verdict: str
    reason: str
    operator_id: str

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "stage": "02_prep_manager",
        "detector_loaded": agent.onnx_session is not None,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

@app.get("/records")
def get_records(x_org_id: str = Header("org_demo_alpha")):
    """Engineering Rule 1: Scoped to tenant org_id."""
    if not os.path.exists(RECORDS_JSON):
        raise HTTPException(status_code=404, detail="Records not yet generated.")
    with open(RECORDS_JSON, "r") as f:
        records = json.load(f)
    # Row-level security filter
    scoped_records = [r for r in records if r.get("org_id") == x_org_id]
    return {
        "org_id": x_org_id,
        "count": len(scoped_records),
        "records": scoped_records
    }

@app.get("/records/{unit_id}")
def get_unit_record(unit_id: str, x_org_id: str = Header("org_demo_alpha")):
    """Retrieve single unit record with strict tenancy enforcement."""
    unit_path = f"submissions/DhanviND360/records/units/{unit_id}.json"
    if not os.path.exists(unit_path):
        raise HTTPException(status_code=404, detail=f"Unit {unit_id} not found.")
    with open(unit_path, "r") as f:
        rec = json.load(f)
    if rec.get("org_id") != x_org_id:
        # Rule 1: Zero leak, return 404 rather than disclosing existence
        raise HTTPException(status_code=404, detail=f"Unit {unit_id} not found.")
    return rec

@app.post("/override")
def record_override(req: OverrideRequest, x_org_id: str = Header("org_demo_alpha")):
    """
    Honesty Rule: Overrides are data.
    Captures original verdict, new verdict, and reason. Never silently discards rows.
    """
    audit_entry = {
        "unit_id": req.unit_id,
        "org_id": x_org_id,
        "original_verdict": req.original_verdict,
        "new_verdict": req.new_verdict,
        "reason": req.reason,
        "operator_id": req.operator_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    os.makedirs(os.path.dirname(OVERRIDE_LOG_FILE), exist_ok=True)
    with open(OVERRIDE_LOG_FILE, "a") as f:
        f.write(json.dumps(audit_entry) + "\n")
    return {"status": "recorded", "audit_entry": audit_entry}

@app.get("/metrics")
def get_metrics():
    """Return latest benchmark economics, throughput, and latency."""
    economics_path = "reports/unit_economics_benchmark.json"
    eval_path = "reports/evaluation_results.json"
    
    econ_data = {}
    eval_data = {}
    if os.path.exists(economics_path):
        with open(economics_path) as f:
            econ_data = json.load(f)
    if os.path.exists(eval_path):
        with open(eval_path) as f:
            eval_data = json.load(f)
            
    return {
        "unit_economics": econ_data,
        "evaluation_summary": eval_data
    }
