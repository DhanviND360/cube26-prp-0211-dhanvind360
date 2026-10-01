"""
Production-Ready FastAPI REST & Streaming API for CUBE Prep Manager (Pod 02).
Features:
- Configurable CORS & Security Middleware
- Health & Readiness Probes (/health, /health/ready)
- Streaming Server-Sent Events (SSE) for Real-Time Progressive Per-Image Inspection
- Multipart File Upload & Ingestion (/api/v1/inspect/upload)
- Tenancy Isolation (Row-Level Security)
- Operator Overrides Audit Trail (Honesty Rule 2)
- Unit Economics & Defect Prevention Analytics
"""

import os
import cv2
import json
import time
import asyncio
import numpy as np
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Header, HTTPException, Query, UploadFile, File, Form, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from agent.config import settings
from agent.pipeline import pipeline
from agent.storage import get_storage_provider
from agent.db import get_database_provider

app = FastAPI(
    title="CUBE Prep Manager API",
    description="Step 2 of Commerce Context Chain: Visual Inbound Prep Compliance & Evidence Engine",
    version="2.1.0"
)

# CORS Middleware (Vercel Next.js / Localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage = get_storage_provider()
db = get_database_provider()

# In-memory background jobs registry
jobs_registry: Dict[str, Dict[str, Any]] = {}

# Security & Tenant Dependency
def get_tenant_org(x_org_id: Optional[str] = Header(None)) -> str:
    """Extract and validate tenant organization ID (Rule 1)."""
    org = x_org_id or settings.DEFAULT_ORG_ID
    if org not in ["org_demo_alpha", "org_demo_bravo"]:
        # In demo context, restrict to valid tenant IDs
        return settings.DEFAULT_ORG_ID
    return org

def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Optional API key verification for production."""
    if settings.REQUIRE_AUTH:
        if not x_api_key or x_api_key != settings.SERVER_API_KEY:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key.")
    return True

# --- SCHEMAS ---
class InspectionRequest(BaseModel):
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
    # Optional existing image path references if already stored
    front_image_ref: Optional[str] = None
    back_image_ref: Optional[str] = None
    label_image_ref: Optional[str] = None

class OverrideRequest(BaseModel):
    unit_id: str
    original_verdict: str
    new_verdict: str
    reason: str
    operator_id: str

# --- HEALTH & READINESS PROBES ---
@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "service": "cube-prep-manager-api",
        "version": "2.1.0",
        "env": settings.ENV,
        "detector_available": pipeline.agent.onnx_session is not None,
        "storage_backend": settings.STORAGE_BACKEND,
        "database_backend": settings.DATABASE_BACKEND,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

@app.get("/health/ready", tags=["System"])
def readiness_check():
    # Verify model is ready
    if pipeline.agent.onnx_session is None and not os.path.exists(settings.ONNX_MODEL_PATH):
        raise HTTPException(status_code=503, detail="Detector model weights not loaded")
    return {"status": "ready", "ready": True}

# --- REAL-TIME PROGRESSIVE STREAMING INSPECTION (SSE) ---
@app.post("/api/v1/inspect/stream", tags=["Inspection"])
async def inspect_unit_streaming(
    request: InspectionRequest,
    org_id: str = Depends(get_tenant_org),
    _: bool = Depends(verify_api_key)
):
    """
    Streams progressive inspection milestones via Server-Sent Events (SSE).
    Emits per-image metrics as Front, Back, and Label views complete.
    """
    # Load images from provided references or dataset fixtures
    f_ref = request.front_image_ref or f"cube_prep_dataset/images/{request.unit_id}_front.jpg"
    b_ref = request.back_image_ref or f"cube_prep_dataset/images/{request.unit_id}_back.jpg"
    l_ref = request.label_image_ref or f"cube_prep_dataset/images/{request.unit_id}_label.jpg"
    
    front_img = storage.get_image(f_ref, org_id)
    back_img = storage.get_image(b_ref, org_id)
    label_img = storage.get_image(l_ref, org_id)
    
    if front_img is None or back_img is None or label_img is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to resolve 3 required perspectives for {request.unit_id}. Verify image paths or uploads."
        )

    async def sse_event_generator():
        async for event in pipeline.inspect_unit_stream(
            unit_id=request.unit_id,
            front_img=front_img,
            back_img=back_img,
            label_img=label_img,
            work_order=request.dict(),
            org_id=org_id
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")

# --- MULTIPART UPLOAD INSPECTION ---
@app.post("/api/v1/inspect/upload", tags=["Inspection"])
async def inspect_unit_upload(
    unit_id: str = Form(...),
    work_order_id: str = Form("WO-3000"),
    fba_shipment_id: str = Form("FBA-CUBE-100"),
    sku: str = Form("SKU-SAMPLE"),
    asin: str = Form("B0DUMMY"),
    fnsku: str = Form("X00CUBE"),
    wo_polybag: bool = Form(False),
    wo_suffocation_warning: bool = Form(False),
    wo_expiry_date: bool = Form(False),
    wo_handling_marks: str = Form(""),
    prep_price_usd: float = Form(0.75),
    front_file: UploadFile = File(...),
    back_file: UploadFile = File(...),
    label_file: UploadFile = File(...),
    org_id: str = Depends(get_tenant_org),
    _: bool = Depends(verify_api_key)
):
    """
    Accepts 3 uploaded physical camera image files, stores them via the Storage Provider,
    and returns a standardized compliance evidence record.
    """
    f_bytes = await front_file.read()
    b_bytes = await back_file.read()
    l_bytes = await label_file.read()

    # Save to storage provider (partitioned by org_id)
    f_uri = storage.save_image(unit_id, "front", f_bytes, org_id)
    b_uri = storage.save_image(unit_id, "back", b_bytes, org_id)
    l_uri = storage.save_image(unit_id, "label", l_bytes, org_id)

    # Decode OpenCV matrices
    f_img = cv2.imdecode(np.frombuffer(f_bytes, np.uint8), cv2.IMREAD_COLOR)
    b_img = cv2.imdecode(np.frombuffer(b_bytes, np.uint8), cv2.IMREAD_COLOR)
    l_img = cv2.imdecode(np.frombuffer(l_bytes, np.uint8), cv2.IMREAD_COLOR)

    wo_dict = {
        "work_order_id": work_order_id,
        "fba_shipment_id": fba_shipment_id,
        "sku": sku,
        "asin": asin,
        "fnsku": fnsku,
        "wo_polybag": wo_polybag,
        "wo_suffocation_warning": wo_suffocation_warning,
        "wo_expiry_date": wo_expiry_date,
        "wo_handling_marks": wo_handling_marks,
        "prep_price_usd": prep_price_usd,
        "photo_refs": f"{f_uri};{b_uri};{l_uri}"
    }

    record = pipeline.agent.inspect_unit(unit_id, f_img, b_img, l_img, wo_dict, org_id=org_id)
    db.save_record(record, org_id)
    return record

# --- SYNCHRONOUS HEADLESS INSPECTION ---
@app.post("/api/v1/inspect", tags=["Inspection"])
def inspect_unit_sync(
    request: InspectionRequest,
    org_id: str = Depends(get_tenant_org),
    _: bool = Depends(verify_api_key)
):
    """Synchronous single-call unit inspection (Rule 2)."""
    f_ref = request.front_image_ref or f"cube_prep_dataset/images/{request.unit_id}_front.jpg"
    b_ref = request.back_image_ref or f"cube_prep_dataset/images/{request.unit_id}_back.jpg"
    l_ref = request.label_image_ref or f"cube_prep_dataset/images/{request.unit_id}_label.jpg"

    front_img = storage.get_image(f_ref, org_id)
    back_img = storage.get_image(b_ref, org_id)
    label_img = storage.get_image(l_ref, org_id)

    if front_img is None or back_img is None or label_img is None:
        raise HTTPException(status_code=400, detail="Could not resolve image captures.")

    record = pipeline.agent.inspect_unit(request.unit_id, front_img, back_img, label_img, request.dict(), org_id=org_id)
    db.save_record(record, org_id)
    return record

# --- ASYNC BACKGROUND JOBS ---
@app.post("/api/v1/jobs", tags=["Jobs"])
async def create_background_job(
    request: InspectionRequest,
    org_id: str = Depends(get_tenant_org),
    _: bool = Depends(verify_api_key)
):
    """Creates a background processing job for high-throughput batching."""
    import uuid
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    jobs_registry[job_id] = {
        "job_id": job_id,
        "unit_id": request.unit_id,
        "org_id": org_id,
        "status": "queued",
        "created_at": time.time(),
        "record": None
    }

    async def run_async_job():
        jobs_registry[job_id]["status"] = "processing"
        f_ref = request.front_image_ref or f"cube_prep_dataset/images/{request.unit_id}_front.jpg"
        b_ref = request.back_image_ref or f"cube_prep_dataset/images/{request.unit_id}_back.jpg"
        l_ref = request.label_image_ref or f"cube_prep_dataset/images/{request.unit_id}_label.jpg"
        f_img = storage.get_image(f_ref, org_id)
        b_img = storage.get_image(b_ref, org_id)
        l_img = storage.get_image(l_ref, org_id)
        if f_img is not None and b_img is not None and l_img is not None:
            rec = pipeline.agent.inspect_unit(request.unit_id, f_img, b_img, l_img, request.dict(), org_id=org_id)
            db.save_record(rec, org_id)
            jobs_registry[job_id]["status"] = "completed"
            jobs_registry[job_id]["record"] = rec
        else:
            jobs_registry[job_id]["status"] = "failed"
            jobs_registry[job_id]["error"] = "Images unresolvable"

    asyncio.create_task(run_async_job())
    return {"job_id": job_id, "status": "queued", "unit_id": request.unit_id}

@app.get("/api/v1/jobs/{job_id}", tags=["Jobs"])
def get_job_status(job_id: str, org_id: str = Depends(get_tenant_org)):
    """Poll status of background inspection job with tenant isolation."""
    job = jobs_registry.get(job_id)
    if not job or job.get("org_id") != org_id:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job

# --- RECORDS & AUDIT OVERRIDES ---
@app.get("/api/v1/records", tags=["Records"])
def list_records(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    org_id: str = Depends(get_tenant_org)
):
    """Retrieve compliance records scoped strictly to tenant (Rule 1)."""
    records = db.list_records(org_id=org_id, limit=limit, offset=offset)
    return {
        "org_id": org_id,
        "count": len(records),
        "limit": limit,
        "offset": offset,
        "records": records
    }

@app.get("/api/v1/records/{unit_id}", tags=["Records"])
def get_record(unit_id: str, org_id: str = Depends(get_tenant_org)):
    """Retrieve a single unit evidence record with row-level security."""
    rec = db.get_record(unit_id=unit_id, org_id=org_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Unit {unit_id} not found.")
    return rec

@app.post("/api/v1/override", tags=["Audit"])
def record_override(req: OverrideRequest, org_id: str = Depends(get_tenant_org)):
    """
    Honesty Rule 2: Overrides are data.
    Captures original verdict, new human verdict, and justification permanently.
    """
    entry = {
        "unit_id": req.unit_id,
        "org_id": org_id,
        "original_verdict": req.original_verdict,
        "new_verdict": req.new_verdict,
        "reason": req.reason,
        "operator_id": req.operator_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    db.record_override(entry)
    return {"status": "override_recorded", "entry": entry}

@app.get("/api/v1/metrics", tags=["Analytics"])
def get_metrics():
    """Retrieve benchmark economics, throughput, and validation statistics."""
    econ_p = "reports/unit_economics_benchmark.json"
    eval_p = "reports/evaluation_results.json"
    econ_data = {}
    eval_data = {}
    if os.path.exists(econ_p):
        with open(econ_p) as f:
            econ_data = json.load(f)
    if os.path.exists(eval_p):
        with open(eval_p) as f:
            eval_data = json.load(f)
    return {"unit_economics": econ_data, "evaluation_summary": eval_data}
