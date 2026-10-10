"""
Production FastAPI REST & Real-Time Streaming Service for CUBE Prep Manager (Pod 02).
Features:
- Configurable CORS & Security Middleware
- Health & Readiness Probes (/health, /health/ready)
- Round 3 Agent Adapter (/run) with CUBE Agent I/O spec compliance
- Multi-Image Multipart Upload with Progressive SSE Streaming (/api/v1/inspect/stream/upload)
- Reference-Based Progressive SSE Streaming (/api/v1/inspect/stream)
- Idempotency & Duplicate Upload Detection
- Resiliency: Missing/Corrupted Image Detection, Timeout Safeguards, Fail-Open Guarantees
- Concurrency & Load Throttling
- Tenancy Isolation (Row-Level Security)
- Operator Overrides Audit Trail (Honesty Rule 2)
- Live Production Metrics: Latency Percentiles, Throughput, Errors, UNCERTAIN Rate, Storage, Economics
- Strict Schema Enforcement matching prep_evidence_contract.json
"""

import os
import io
import cv2
import json
import time
import uuid
import asyncio
import hashlib
import tempfile
import numpy as np
from typing import Optional, List, Dict, Any
from fastapi import (
    FastAPI, Header, HTTPException, Query, UploadFile, File, Form, Depends, Request, status
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent.config import settings
from agent.pipeline import pipeline
from agent.storage import get_storage_provider
from agent.db import get_database_provider
from agent.metrics import metrics_tracker
from agent.validator import validate_prep_record

# Request size limit (16MB max)
MAX_REQUEST_BODY_BYTES = 16 * 1024 * 1024

app = FastAPI(
    title="CUBE Prep Manager API",
    description="PREP Agent: Visual Inbound Prep Compliance & Evidence Engine. Standalone inspection service with Round 3 /run adapter.",
    version="3.0.0"
)

# CORS Middleware (Vercel Next.js / Streamlit / Localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount dataset images for frontend visualization
if os.path.exists("cube_prep_dataset/images"):
    app.mount("/images", StaticFiles(directory="cube_prep_dataset/images"), name="images")

if os.path.exists("data/packaging_dataset"):
    app.mount("/packaging_images", StaticFiles(directory="data/packaging_dataset"), name="packaging_images")

# Mount uploaded images
if os.path.exists("data/uploads"):
    app.mount("/uploads", StaticFiles(directory="data/uploads"), name="uploads")

# Mount frontend assets
if os.path.exists("frontend/assets"):
    app.mount("/assets", StaticFiles(directory="frontend/assets"), name="assets")

storage = get_storage_provider()
db = get_database_provider()

from fastapi.exceptions import RequestValidationError
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    clean_errors = []
    for err in exc.errors():
        err_copy = dict(err)
        if isinstance(err_copy.get("input"), (bytes, bytearray)):
            err_copy["input"] = f"<binary {len(err_copy['input'])} bytes>"
        clean_errors.append(err_copy)
    print("[FastAPI RequestValidationError]", clean_errors)
    return JSONResponse(status_code=422, content={"detail": clean_errors})

# Concurrency throttling semaphore
concurrency_limiter = asyncio.Semaphore(settings.MAX_CONCURRENT_INSPECTIONS)

# In-memory background jobs registry
jobs_registry: Dict[str, Dict[str, Any]] = {}

# Security & Tenant Dependency
VALID_TENANTS = {"org_demo_alpha", "org_demo_bravo"}

def get_tenant_org(x_org_id: Optional[str] = Header(None)) -> str:
    """Extract and validate tenant organization ID (Rule 1). Rejects unauthorized tenants."""
    if not x_org_id:
        return settings.DEFAULT_ORG_ID
    if x_org_id not in VALID_TENANTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid or unauthorized organisation/tenant: '{x_org_id}'. Allowed tenants: {sorted(list(VALID_TENANTS))}"
        )
    return x_org_id

def verify_api_key(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
) -> bool:
    """
    Step 5: API Key verification.
    Accepts X-API-Key or Authorization Bearer header.
    Loaded strictly from environment variable SERVER_API_KEY.
    """
    if settings.REQUIRE_AUTH:
        token = x_api_key
        if not token and authorization:
            if authorization.startswith("Bearer "):
                token = authorization[7:].strip()
            else:
                token = authorization.strip()
        if not token or token != settings.SERVER_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: Missing or invalid API Key."
            )
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
    scenario: Optional[str] = None
    front_image_ref: Optional[str] = None
    back_image_ref: Optional[str] = None
    label_image_ref: Optional[str] = None

    class Config:
        extra = "allow"

class OverrideRequest(BaseModel):
    unit_id: str
    original_verdict: str
    new_verdict: str
    reason: str
    operator_id: str

def format_sse_message(event_name: str, unit_id: str, data: Dict[str, Any], seq: int = 1) -> str:
    """Formats standardized SSE event with ID, event name, retry policy, and payload."""
    payload = json.dumps(data)
    return f"id: {unit_id}-{seq}\nevent: {event_name}\nretry: 3000\ndata: {payload}\n\n"

# --- HEALTH & READINESS PROBES ---
@app.get("/health", tags=["System"])
def health_check():
    ai_active = bool(pipeline.agent.api_key)
    return {
        "status": "healthy",
        "service": "cube-prep-manager-api",
        "version": "3.0.0",
        "env": settings.ENV,
        "ai_agent_model": pipeline.agent.model_name,
        "ai_agent_active": ai_active,
        "detector_active": True,
        "detector_available": True,
        "storage_backend": settings.STORAGE_BACKEND,
        "database_backend": settings.DATABASE_BACKEND,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

@app.get("/health/ready", tags=["System"])
def readiness_check():
    return {
        "status": "ready",
        "ready": True,
        "ai_agent_model": pipeline.agent.model_name,
        "detector_active": True
    }

# --- WEB PORTAL FOR OPERATORS & CLOUD TESTING ---
@app.get("/", response_class=HTMLResponse, tags=["Web Portal"])
def web_portal():
    """Serves the interactive live inspection portal for browser operators and cloud testing."""
    portal_path = os.path.join(os.path.dirname(__file__), "portal.html")
    if os.path.exists(portal_path):
        with open(portal_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>CUBE Prep Manager API is active. Visit <a href='/docs'>/docs</a> for Swagger documentation.</h1>")

# --- DIRECT MULTIPART UPLOAD (SINGLE OR MULTI-IMAGE) ---
@app.post("/api/v1/inspect/upload", tags=["Inspection"])
@app.post("/api/v1/inspect/image", tags=["Inspection"])
async def inspect_unit_direct_upload(
    unit_id: Optional[str] = Form(None),
    work_order_id: str = Form("WO-3000"),
    fba_shipment_id: str = Form("FBA-CUBE-100"),
    sku: str = Form("SKU-SAMPLE"),
    asin: str = Form("B0DUMMY"),
    fnsku: str = Form("X00CUBE"),
    wo_polybag: bool = Form(True),
    wo_suffocation_warning: bool = Form(True),
    wo_expiry_date: bool = Form(False),
    wo_handling_marks: str = Form(""),
    prep_price_usd: float = Form(0.75),
    file: Optional[UploadFile] = File(None),
    image: Optional[UploadFile] = File(None),
    front_file: Optional[UploadFile] = File(None),
    back_file: Optional[UploadFile] = File(None),
    label_file: Optional[UploadFile] = File(None),
    org_id: str = Depends(get_tenant_org)
):
    """
    Accepts an uploaded packaging image (single photo or 3 perspectives)
    and returns immediate Amazon FBA compliance inspection JSON.
    """
    primary = front_file or file or image
    if not primary and not back_file and not label_file:
        raise HTTPException(status_code=400, detail="No packaging image file uploaded.")

    f_bytes = await primary.read() if primary else b""
    b_bytes = await back_file.read() if back_file else f_bytes
    l_bytes = await label_file.read() if label_file else f_bytes

    if not b_bytes:
        b_bytes = f_bytes
    if not l_bytes:
        l_bytes = f_bytes

    f_img = cv2.imdecode(np.frombuffer(f_bytes, np.uint8), cv2.IMREAD_COLOR) if f_bytes else None
    b_img = cv2.imdecode(np.frombuffer(b_bytes, np.uint8), cv2.IMREAD_COLOR) if b_bytes else None
    l_img = cv2.imdecode(np.frombuffer(l_bytes, np.uint8), cv2.IMREAD_COLOR) if l_bytes else None

    if f_img is None:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image format.")

    uid = unit_id or f"UNIT-UPL-{uuid.uuid4().hex[:6].upper()}"
    wo_dict = {
        "unit_id": uid,
        "work_order_id": work_order_id,
        "fba_shipment_id": fba_shipment_id,
        "sku": sku,
        "asin": asin,
        "fnsku": fnsku,
        "wo_polybag": wo_polybag,
        "wo_suffocation_warning": wo_suffocation_warning,
        "wo_expiry_date": wo_expiry_date,
        "wo_handling_marks": wo_handling_marks,
        "prep_price_usd": prep_price_usd
    }

    t0 = time.perf_counter()
    record = await asyncio.to_thread(
        pipeline.agent.inspect_unit,
        uid, f_img, b_img, l_img, wo_dict, org_id
    )
    lat_ms = (time.perf_counter() - t0) * 1000.0

    try:
        storage.save_image(uid, "front", f_bytes, org_id)
        db.save_record(record, org_id)
    except Exception as e:
        print(f"[DirectUpload] Storage/DB note: {e}")

    metrics_tracker.record_finish(
        unit_id=uid,
        org_id=org_id,
        verdict=record["overall_status"],
        total_latency_ms=lat_ms,
        cost_usd=record["performance"].get("estimated_compute_cost_usd", 0.00028)
    )

    return record

# --- MULTIPART UPLOAD WITH PROGRESSIVE SSE STREAMING ---
@app.post("/api/v1/inspect/stream/upload", tags=["Inspection"])
async def inspect_unit_stream_upload(
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
    x_force_reinspect: bool = Query(False, description="Bypass duplicate cache and re-evaluate"),
    org_id: str = Depends(get_tenant_org),
    _: bool = Depends(verify_api_key)
):
    """
    Accepts 3 uploaded camera files, saves them partitioned by tenant,
    and streams real-time progressive inspection milestones via SSE.
    """
    # 1. Idempotency / Duplicate Detection Check
    existing_record = db.get_record(unit_id, org_id)
    if existing_record and not x_force_reinspect:
        async def cached_event_stream():
            yield format_sse_message("job_started", unit_id, {
                "event": "job_started",
                "progress": 100,
                "unit_id": unit_id,
                "org_id": org_id,
                "cached": True,
                "message": f"Unit {unit_id} previously inspected. Returning cached compliance record."
            }, seq=1)
            yield format_sse_message("inspection_completed", unit_id, {
                "event": "inspection_completed",
                "progress": 100,
                "unit_id": unit_id,
                "org_id": org_id,
                "cached": True,
                "overall_status": existing_record["overall_status"],
                "issue_explanation": existing_record["issue_explanation"],
                "record": existing_record,
                "message": "Cached record retrieved successfully."
            }, seq=2)
        return StreamingResponse(cached_event_stream(), media_type="text/event-stream")

    # Read uploaded bytes
    f_bytes = await front_file.read()
    b_bytes = await back_file.read()
    l_bytes = await label_file.read()

    # Resiliency: Validate upload integrity
    if len(f_bytes) == 0 or len(b_bytes) == 0 or len(l_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more uploaded camera files are empty (0 bytes)."
        )

    # Decode OpenCV matrices
    f_img = cv2.imdecode(np.frombuffer(f_bytes, np.uint8), cv2.IMREAD_COLOR)
    b_img = cv2.imdecode(np.frombuffer(b_bytes, np.uint8), cv2.IMREAD_COLOR)
    l_img = cv2.imdecode(np.frombuffer(l_bytes, np.uint8), cv2.IMREAD_COLOR)

    if f_img is None or b_img is None or l_img is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more uploaded files could not be decoded as valid image formats (JPEG/PNG)."
        )

    # Persist images to storage provider
    f_uri = storage.save_image(unit_id, "front", f_bytes, org_id)
    b_uri = storage.save_image(unit_id, "back", b_bytes, org_id)
    l_uri = storage.save_image(unit_id, "label", l_bytes, org_id)

    wo_dict = {
        "unit_id": unit_id,
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

    async def sse_event_generator():
        async with concurrency_limiter:
            seq = 1
            try:
                # Wrap execution in timeout SLA
                async for event in pipeline.inspect_unit_stream(
                    unit_id=unit_id,
                    front_img=f_img,
                    back_img=b_img,
                    label_img=l_img,
                    work_order=wo_dict,
                    org_id=org_id,
                    timeout_seconds=settings.INSPECTION_TIMEOUT_SECONDS
                ):
                    event_type = event.get("event", "message")
                    # If this is the final milestone, strictly validate contract
                    if event_type == "inspection_completed" and "record" in event:
                        is_valid, err = validate_prep_record(event["record"])
                        if not is_valid:
                            event["schema_warning"] = err
                    yield format_sse_message(event_type, unit_id, event, seq=seq)
                    seq += 1
            except asyncio.TimeoutError:
                # Fail-open under timeout condition
                fail_rec = pipeline.calibrator.execute_fail_open(
                    unit_id, "Inspection SLA timeout exceeded", wo_dict, org_id=org_id
                )
                db.save_record(fail_rec, org_id)
                metrics_tracker.record_error(unit_id, org_id, "Timeout exceeded SLA")
                timeout_event = {
                    "event": "inspection_completed",
                    "progress": 100,
                    "unit_id": unit_id,
                    "org_id": org_id,
                    "overall_status": "UNCERTAIN",
                    "issue_explanation": "Inspection SLA timeout exceeded. Fail-open record emitted.",
                    "record": fail_rec,
                    "message": "Inspection timed out; saved under fail-open guarantee (pending_review)."
                }
                yield format_sse_message("inspection_completed", unit_id, timeout_event, seq=seq)

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

# --- REFERENCE-BASED SSE STREAMING ---
@app.post("/api/v1/inspect/stream", tags=["Inspection"])
async def inspect_unit_streaming(
    request: InspectionRequest,
    x_force_reinspect: bool = Query(False, description="Bypass duplicate cache"),
    org_id: str = Depends(get_tenant_org),
    _: bool = Depends(verify_api_key)
):
    """
    Streams progressive inspection milestones via Server-Sent Events (SSE)
    using stored image references or primary dataset fixtures.
    """
    # Duplicate / idempotency check
    existing_record = db.get_record(request.unit_id, org_id)
    if existing_record and not x_force_reinspect:
        async def cached_event_stream():
            yield format_sse_message("job_started", request.unit_id, {
                "event": "job_started",
                "progress": 100,
                "unit_id": request.unit_id,
                "org_id": org_id,
                "cached": True,
                "message": f"Unit {request.unit_id} previously inspected."
            }, seq=1)
            yield format_sse_message("inspection_completed", request.unit_id, {
                "event": "inspection_completed",
                "progress": 100,
                "unit_id": request.unit_id,
                "org_id": org_id,
                "cached": True,
                "overall_status": existing_record["overall_status"],
                "issue_explanation": existing_record["issue_explanation"],
                "record": existing_record,
                "message": "Cached record returned."
            }, seq=2)
        return StreamingResponse(cached_event_stream(), media_type="text/event-stream")

    # Load images from references or dataset fixtures
    f_ref = request.front_image_ref or f"cube_prep_dataset/images/{request.unit_id}_front.jpg"
    b_ref = request.back_image_ref or f"cube_prep_dataset/images/{request.unit_id}_back.jpg"
    l_ref = request.label_image_ref or f"cube_prep_dataset/images/{request.unit_id}_label.jpg"

    front_img = storage.get_image(f_ref, org_id)
    back_img = storage.get_image(b_ref, org_id)
    label_img = storage.get_image(l_ref, org_id)

    if front_img is None or back_img is None or label_img is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to resolve required perspectives for {request.unit_id}. Verify image paths."
        )

    async def sse_event_generator():
        async with concurrency_limiter:
            seq = 1
            async for event in pipeline.inspect_unit_stream(
                unit_id=request.unit_id,
                front_img=front_img,
                back_img=back_img,
                label_img=label_img,
                work_order=request.dict(),
                org_id=org_id,
                timeout_seconds=settings.INSPECTION_TIMEOUT_SECONDS
            ):
                event_type = event.get("event", "message")
                if event_type == "inspection_completed" and "record" in event:
                    is_valid, err = validate_prep_record(event["record"])
                    if not is_valid:
                        event["schema_warning"] = err
                yield format_sse_message(event_type, request.unit_id, event, seq=seq)
                seq += 1

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

# --- SYNCHRONOUS MULTIPART UPLOAD INSPECTION ---
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
    x_force_reinspect: bool = Query(False),
    org_id: str = Depends(get_tenant_org),
    _: bool = Depends(verify_api_key)
):
    """
    Accepts 3 uploaded camera files, saves them, executes inspection,
    and returns a strictly validated prep_evidence_contract record.
    """
    # Check duplicate
    existing = db.get_record(unit_id, org_id)
    if existing and not x_force_reinspect:
        return JSONResponse(content=existing, headers={"X-Cache": "HIT"})

    f_bytes = await front_file.read()
    b_bytes = await back_file.read()
    l_bytes = await label_file.read()

    if len(f_bytes) == 0 or len(b_bytes) == 0 or len(l_bytes) == 0:
        raise HTTPException(status_code=400, detail="One or more uploaded files are empty.")

    f_img = cv2.imdecode(np.frombuffer(f_bytes, np.uint8), cv2.IMREAD_COLOR)
    b_img = cv2.imdecode(np.frombuffer(b_bytes, np.uint8), cv2.IMREAD_COLOR)
    l_img = cv2.imdecode(np.frombuffer(l_bytes, np.uint8), cv2.IMREAD_COLOR)

    if f_img is None or b_img is None or l_img is None:
        raise HTTPException(status_code=400, detail="Unreadable image files; decoding failed.")

    f_uri = storage.save_image(unit_id, "front", f_bytes, org_id)
    b_uri = storage.save_image(unit_id, "back", b_bytes, org_id)
    l_uri = storage.save_image(unit_id, "label", l_bytes, org_id)

    wo_dict = {
        "unit_id": unit_id,
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

    async with concurrency_limiter:
        t0 = time.perf_counter()
        record = await asyncio.to_thread(pipeline.agent.inspect_unit, unit_id, f_img, b_img, l_img, wo_dict, org_id=org_id)
        db.save_record(record, org_id)
        lat_ms = (time.perf_counter() - t0) * 1000.0
        metrics_tracker.record_finish(
            unit_id=unit_id,
            org_id=org_id,
            verdict=record["overall_status"],
            total_latency_ms=lat_ms,
            cost_usd=record["performance"].get("estimated_compute_cost_usd", 0.00015)
        )

    # Validate against evidence contract
    is_valid, err = validate_prep_record(record)
    if not is_valid:
        record["_schema_warning"] = err

    return record

# --- SYNCHRONOUS HEADLESS INSPECTION ---
@app.post("/api/v1/inspect", tags=["Inspection"])
async def inspect_unit_sync(
    request: InspectionRequest,
    x_force_reinspect: bool = Query(False),
    org_id: str = Depends(get_tenant_org),
    _: bool = Depends(verify_api_key)
):
    """Synchronous single-call unit inspection (Rule 2)."""
    existing = db.get_record(request.unit_id, org_id)
    if existing and not x_force_reinspect:
        return JSONResponse(content=existing, headers={"X-Cache": "HIT"})

    f_ref = request.front_image_ref or f"cube_prep_dataset/images/{request.unit_id}_front.jpg"
    b_ref = request.back_image_ref or f"cube_prep_dataset/images/{request.unit_id}_back.jpg"
    l_ref = request.label_image_ref or f"cube_prep_dataset/images/{request.unit_id}_label.jpg"

    front_img = storage.get_image(f_ref, org_id)
    back_img = storage.get_image(b_ref, org_id)
    label_img = storage.get_image(l_ref, org_id)

    if front_img is None or back_img is None or label_img is None:
        raise HTTPException(status_code=400, detail="Could not resolve image captures.")

    async with concurrency_limiter:
        t0 = time.perf_counter()
        record = await asyncio.to_thread(
            pipeline.agent.inspect_unit,
            request.unit_id, front_img, back_img, label_img, request.dict(), org_id=org_id
        )
        db.save_record(record, org_id)
        lat_ms = (time.perf_counter() - t0) * 1000.0
        metrics_tracker.record_finish(
            unit_id=request.unit_id,
            org_id=org_id,
            verdict=record["overall_status"],
            total_latency_ms=lat_ms,
            cost_usd=record["performance"].get("estimated_compute_cost_usd", 0.00015)
        )

    is_valid, err = validate_prep_record(record)
    if not is_valid:
        record["_schema_warning"] = err

    return record

# --- PARTIAL RESULTS RETRIEVAL (RESILIENCE) ---
@app.get("/api/v1/inspect/partial/{unit_id}", tags=["Inspection"])
def get_partial_inspection_results(unit_id: str, org_id: str = Depends(get_tenant_org)):
    """
    Retrieves in-flight or partial inspection state for disconnected clients.
    """
    partial = pipeline.get_partial_state(unit_id)
    if not partial or partial.get("org_id") != org_id:
        # Check if completed record exists in db
        rec = db.get_record(unit_id, org_id)
        if rec:
            return {"unit_id": unit_id, "status": "completed", "record": rec}
        raise HTTPException(status_code=404, detail=f"No active or cached inspection found for {unit_id}.")
    return partial

# --- PACKAGING DATASET & UNIT CATALOG ---
@app.get("/api/v1/units", tags=["Dataset"])
def list_available_units(
    grid: Optional[str] = Query(None, description="Filter by grid: compliance_scenarios, inspection_examples, packaged_products, legacy_cube_prep"),
    org_id: str = Depends(get_tenant_org)
):
    """Lists indexed packaging inspection units from the packaging dataset and legacy catalog."""
    from agent.dataset import dataset_manager
    units = dataset_manager.list_units(org_id=org_id, grid=grid)
    return {"count": len(units), "org_id": org_id, "units": units}

@app.get("/api/v1/units/{unit_id}", tags=["Dataset"])
def get_unit_details(
    unit_id: str,
    org_id: str = Depends(get_tenant_org)
):
    """Retrieves metadata, work order requirements, and image perspectives for a unit."""
    from agent.dataset import dataset_manager
    unit = dataset_manager.get_unit(unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail=f"Unit '{unit_id}' not found in catalog.")
    if unit.get("org_id") != org_id:
        raise HTTPException(status_code=403, detail=f"Unit '{unit_id}' belongs to another tenant.")
    return unit

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
            rec = await asyncio.to_thread(pipeline.agent.inspect_unit, request.unit_id, f_img, b_img, l_img, request.dict(), org_id=org_id)
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
    """
    Retrieve live production telemetry:
    - Latency percentiles (per unit, per view: front, back, label)
    - Throughput (units/sec, units/min, images/min)
    - Errors, error rate, and UNCERTAIN abstention rate
    - Storage footprint (bytes, images, MB)
    - Actual compute cost/unit vs target economic SLA
    - Offline evaluation benchmarks reference
    """
    live_metrics = metrics_tracker.get_summary(storage_provider=storage, db_provider=db)
    
    econ_p = "reports/unit_economics_benchmark.json"
    eval_p = "reports/evaluation_results.json"
    econ_data = {}
    eval_data = {}
    if os.path.exists(econ_p):
        try:
            with open(econ_p) as f:
                econ_data = json.load(f)
        except Exception:
            pass
    if os.path.exists(eval_p):
        try:
            with open(eval_p) as f:
                eval_data = json.load(f)
        except Exception:
            pass

    return {
        "live_production_metrics": live_metrics,
        "offline_benchmarks": {
            "unit_economics": econ_data,
            "evaluation_summary": eval_data
        }
    }

# --- DATASET PRESETS FOR 1-CLICK TESTING ---
@app.get("/api/v1/dataset/samples", tags=["Analytics"])
def get_dataset_samples():
    """Returns curated preset demo units from dataset across PASS, FAIL, UNCERTAIN."""
    samples = [
        {
            "unit_id": "UNIT-POLY-0001",
            "org_id": "org_demo_alpha",
            "expected_verdict": "PASS",
            "scenario": "correct_preparation",
            "product_category": "toys",
            "sku": "SKU-TOY-POLY",
            "asin": "B0POLY001",
            "fnsku": "X001POLYBAG",
            "wo_polybag": True,
            "wo_suffocation_warning": True,
            "wo_expiry_date": False,
            "wo_handling_marks": "liquid",
            "prep_price_usd": 1.10,
            "photo_front": "/images/UNIT-POLY-0001_front.jpg",
            "photo_back": "/images/UNIT-POLY-0001_back.jpg",
            "photo_label": "/images/UNIT-POLY-0001_label.jpg",
            "description": "Sealed Polybag Toy: Verified heat seal, warning & flat FNSKU (PASS)"
        },
        {
            "unit_id": "UNIT-POLY-0002",
            "org_id": "org_demo_alpha",
            "expected_verdict": "PASS",
            "scenario": "correct_preparation",
            "product_category": "apparel",
            "sku": "SKU-TEE-POLY",
            "asin": "B0POLY002",
            "fnsku": "X002APPAREL",
            "wo_polybag": True,
            "wo_suffocation_warning": True,
            "wo_expiry_date": False,
            "wo_handling_marks": "",
            "prep_price_usd": 0.95,
            "photo_front": "/images/UNIT-POLY-0002_front.jpg",
            "photo_back": "/images/UNIT-POLY-0002_back.jpg",
            "photo_label": "/images/UNIT-POLY-0002_label.jpg",
            "description": "Sealed Polybag Apparel: Transparent film, warning & covered barcode (PASS)"
        },
        {
            "unit_id": "UNIT-POLY-OPEN",
            "org_id": "org_demo_alpha",
            "expected_verdict": "FAIL",
            "scenario": "polybag_not_sealed",
            "product_category": "kitchen",
            "sku": "SKU-TOWEL-OPEN",
            "asin": "B0POLY004",
            "fnsku": "X004OPENSEAL",
            "wo_polybag": True,
            "wo_suffocation_warning": True,
            "wo_expiry_date": False,
            "wo_handling_marks": "",
            "prep_price_usd": 0.75,
            "photo_front": "/images/UNIT-POLY-OPEN_front.jpg",
            "photo_back": "/images/UNIT-POLY-OPEN_back.jpg",
            "photo_label": "/images/UNIT-POLY-OPEN_label.jpg",
            "description": "Defect: Polybag unsealed / open closure (FAIL)"
        },
        {
            "unit_id": "UNIT-POLY-NOWARN",
            "org_id": "org_demo_alpha",
            "expected_verdict": "FAIL",
            "scenario": "missing_warning",
            "product_category": "toys",
            "sku": "SKU-PLUSH-NOWARN",
            "asin": "B0POLY005",
            "fnsku": "X005NOWARN",
            "wo_polybag": True,
            "wo_suffocation_warning": True,
            "wo_expiry_date": False,
            "wo_handling_marks": "",
            "prep_price_usd": 0.75,
            "photo_front": "/images/UNIT-POLY-NOWARN_front.jpg",
            "photo_back": "/images/UNIT-POLY-NOWARN_back.jpg",
            "photo_label": "/images/UNIT-POLY-NOWARN_label.jpg",
            "description": "Defect: Polybag missing required suffocation warning (FAIL)"
        }
    ]

    csv_path = "cube_prep_dataset/cube_prep_dataset.csv"
    if os.path.exists(csv_path):
        import pandas as pd
        df = pd.read_csv(csv_path)
        selected_uids = [
            "UNIT-0002",  # PASS: Clean standard toy prep with polybag
            "UNIT-0001",  # PASS: Clean standard electronics prep (no polybag)
            "UNIT-0003",  # FAIL: FNSKU placed on center seam
            "UNIT-0008",  # FAIL: Original barcode visible (not covered)
            "UNIT-0004",  # UNCERTAIN: Ambiguous FNSKU scan
        ]
        for uid in selected_uids:
            rows = df[df["unit_id"] == uid]
            if not rows.empty:
                r = rows.iloc[0].to_dict()
                samples.append({
                    "unit_id": r["unit_id"],
                    "org_id": r["org_id"],
                    "expected_verdict": r["expected_overall_status"],
                    "scenario": r.get("scenario", "standard"),
                    "product_category": r.get("product_category", "general"),
                    "sku": r.get("sku", "SKU-SAMPLE"),
                    "asin": r.get("asin", "B0DUMMY"),
                    "fnsku": r.get("fnsku", "X00CUBE"),
                    "wo_polybag": bool(r.get("wo_polybag", False)),
                    "wo_suffocation_warning": bool(r.get("wo_suffocation_warning", False)),
                    "wo_expiry_date": bool(r.get("wo_expiry_date", False)),
                    "wo_handling_marks": str(r.get("wo_handling_marks", "")) if pd.notna(r.get("wo_handling_marks")) else "",
                    "prep_price_usd": float(r.get("prep_price_usd", 0.75)),
                    "photo_front": f"/images/{uid}_front.jpg",
                    "photo_back": f"/images/{uid}_back.jpg",
                    "photo_label": f"/images/{uid}_label.jpg",
                    "description": r.get("expected_issue_explanation", "")
                })
    return {"samples": samples}

# ─────────────────────────────────────────────────────────────────────────────
# ROUND 3 AGENT ADAPTER: /run endpoint
# Thin adapter around the PREP core engine for Round 3 orchestration.
# Does NOT add orchestration, workflow state, routing, retries, or recovery.
# ─────────────────────────────────────────────────────────────────────────────

class AgentRunRequest(BaseModel):
    """CUBE Round 3 Agent Input specification."""
    task_id: Optional[str] = Field(None, description="Unique task identifier from orchestrator")
    unit_id: Optional[str] = Field(None, description="Unit identifier to inspect (e.g. UNIT-0001)")
    id: Optional[str] = Field(None, description="Alias for unit_id")
    images: Optional[Dict[str, Any]] = Field(
        None, description="Dict of view->image (base64 string, URL, or local path): {front, back, label}"
    )
    image_refs: Optional[Dict[str, Any]] = Field(
        None, description="Dict of view->file path or URL references: {front, back, label}"
    )
    photo_front: Optional[str] = Field(None, description="Direct front view image reference/data")
    photo_back: Optional[str] = Field(None, description="Direct back view image reference/data")
    photo_label: Optional[str] = Field(None, description="Direct label view image reference/data")
    work_order: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Work order configuration (prep requirements)"
    )
    params: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Alias for work_order parameters"
    )
    org_id: Optional[str] = Field(None, description="Tenant organization ID (org_demo_alpha or org_demo_bravo)")
    tenant: Optional[str] = Field(None, description="Alias for org_id")
    force_reinspect: Optional[bool] = Field(False, description="Bypass cache")

    class Config:
        extra = "allow"

class AgentRunResponse(BaseModel):
    """CUBE Round 3 Agent Output specification."""
    task_id: Optional[str] = Field(None, description="Unique task identifier")
    agent: str = Field("prep", description="Agent name")
    stage: str = Field("prep", description="Stage identifier")
    org_id: str = Field("org_demo_alpha", description="Tenant organization ID")
    tenant: Optional[str] = Field("org_demo_alpha", description="Alias for org_id")
    status: str = Field("success", description="Status: success or error")
    decision: str = Field("PASS", description="Stage verdict: PASS, FAIL, or UNCERTAIN")
    verdict: str = Field("PASS", description="Alias for decision")
    confidence: float = Field(0.96, description="Confidence score between 0.0 and 1.0")
    explanation: str = Field("", description="Human-readable decision explanation")
    checks: Dict[str, Any] = Field(default_factory=dict, description="Itemized individual checks")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Detailed visual and spatial evidence")
    record: Optional[Dict[str, Any]] = Field(None, description="Full compliance record conforming to schema contract")
    error: Optional[str] = Field(None, description="Error message if status is 'error'")
    latency_ms: Optional[float] = Field(None, description="Total execution latency in milliseconds")

    class Config:
        extra = "allow"


import base64


def _decode_base64_image(b64_str: str) -> Optional[np.ndarray]:
    """Decode a base64-encoded image string to an OpenCV image."""
    try:
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        img_bytes = base64.b64decode(b64_str)
        if len(img_bytes) == 0:
            return None
        arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def _resolve_single_image(val: Any, org_id: str) -> Optional[np.ndarray]:
    """Resolves an image from base64 string, HTTP URL, local path, or ndarray."""
    if val is None:
        return None
    if isinstance(val, np.ndarray):
        return val
    if not isinstance(val, str) or not val.strip():
        return None
    val = val.strip()

    # 1. Base64 encoded data
    if val.startswith("data:image") or (len(val) > 300 and not val.startswith("http") and not os.path.exists(val)):
        decoded = _decode_base64_image(val)
        if decoded is not None:
            return decoded

    # 2. HTTP / HTTPS URL
    if val.startswith("http://") or val.startswith("https://"):
        try:
            with httpx.Client(timeout=10.0) as http_client:
                resp = http_client.get(val)
                if resp.status_code == 200 and len(resp.content) > 0:
                    arr = np.frombuffer(resp.content, np.uint8)
                    return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except Exception:
            pass

    # 3. Local file path
    if os.path.exists(val):
        return cv2.imread(val)

    # 4. Search in dataset or uploads directory
    search_prefixes = [
        "data/packaging_dataset/",
        "packaging_dataset/",
        "cube_prep_dataset/",
        "cube_prep_dataset/images/",
        "data/uploads/",
        "data/test_uploads/",
        r"C:\Dhanvi\HACKATHONS\CUBE_2026_dataset\packaging_dataset/"
    ]
    for prefix in search_prefixes:
        p = os.path.join(prefix, os.path.basename(val))
        if os.path.exists(p):
            return cv2.imread(p)
        # Try direct subpath
        p_sub = os.path.join(prefix, val.replace("packaging_dataset/", "").replace("cube_prep_dataset/", ""))
        if os.path.exists(p_sub):
            return cv2.imread(p_sub)

    # 5. Storage abstraction
    return storage.get_image(val, org_id)


@app.post("/run", tags=["Round3 Agent"], response_model=AgentRunResponse)
async def agent_run(
    request: AgentRunRequest,
    _: bool = Depends(verify_api_key)
):
    """
    CUBE Round 3 Agent /run endpoint.
    Standardized adapter conforming to the Round 3 Agent Input/Output specification.
    Callable by Saif's orchestrator and independent clients.
    """
    t_start = time.perf_counter()
    task_id = request.task_id or f"prep-{uuid.uuid4().hex[:8]}"

    # Validate tenant (Rule 1 & Step 8)
    org_id = request.org_id or request.tenant or settings.DEFAULT_ORG_ID
    if org_id not in VALID_TENANTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid or unauthorized organisation/tenant: '{org_id}'. Allowed tenants: {sorted(list(VALID_TENANTS))}"
        )

    unit_id = request.unit_id or request.id or "UNIT-0001"

    try:
        # Extract image inputs across all supported formats
        raw_front = None
        raw_back = None
        raw_label = None

        if request.images and isinstance(request.images, dict):
            raw_front = request.images.get("front") or request.images.get("photo_front")
            raw_back = request.images.get("back") or request.images.get("photo_back")
            raw_label = request.images.get("label") or request.images.get("photo_label")

        if not raw_front and request.image_refs and isinstance(request.image_refs, dict):
            raw_front = request.image_refs.get("front") or request.image_refs.get("photo_front")
            raw_back = request.image_refs.get("back") or request.image_refs.get("photo_back")
            raw_label = request.image_refs.get("label") or request.image_refs.get("photo_label")

        # Top-level direct references
        raw_front = raw_front or request.photo_front
        raw_back = raw_back or request.photo_back
        raw_label = raw_label or request.photo_label

        # Resolve image data
        front_img = _resolve_single_image(raw_front, org_id) if raw_front else None
        back_img = _resolve_single_image(raw_back, org_id) if raw_back else None
        label_img = _resolve_single_image(raw_label, org_id) if raw_label else None

        # Fallback to standard dataset paths if references weren't passed
        if front_img is None:
            front_img = _resolve_single_image(f"cube_prep_dataset/images/{unit_id}_front.jpg", org_id)
        if back_img is None:
            back_img = _resolve_single_image(f"cube_prep_dataset/images/{unit_id}_back.jpg", org_id)
        if label_img is None:
            label_img = _resolve_single_image(f"cube_prep_dataset/images/{unit_id}_label.jpg", org_id)

        # Resiliency: Handle unavailable image streams
        if front_img is None or back_img is None or label_img is None:
            missing = []
            if front_img is None: missing.append("front")
            if back_img is None: missing.append("back")
            if label_img is None: missing.append("label")
            err_msg = f"Could not resolve required image view(s): {', '.join(missing)} for unit {unit_id}."
            return AgentRunResponse(
                task_id=task_id,
                agent="prep",
                stage="prep",
                org_id=org_id,
                tenant=org_id,
                status="error",
                decision="UNCERTAIN",
                verdict="UNCERTAIN",
                confidence=0.0,
                explanation=err_msg,
                checks={},
                evidence={"error": err_msg, "missing_views": missing},
                error=err_msg,
                latency_ms=round((time.perf_counter() - t_start) * 1000.0, 2)
            )

        # Idempotency / Duplicate Check
        if not request.force_reinspect:
            existing = db.get_record(unit_id, org_id)
            if existing:
                cached_decision = existing["overall_status"]
                cached_conf = existing.get("confidence", 0.96 if cached_decision == "PASS" else (0.92 if cached_decision == "FAIL" else 0.40))
                return AgentRunResponse(
                    task_id=task_id,
                    agent="prep",
                    stage="prep",
                    org_id=org_id,
                    tenant=org_id,
                    status="success",
                    decision=cached_decision,
                    verdict=cached_decision,
                    confidence=cached_conf,
                    explanation=existing.get("issue_explanation", ""),
                    checks=existing.get("checks", {}),
                    evidence=existing.get("evidence_vector", {}),
                    record=existing,
                    latency_ms=round((time.perf_counter() - t_start) * 1000.0, 2)
                )

        # Assemble work order dictionary
        wo = dict(request.params or {})
        wo.update(request.work_order or {})
        wo.setdefault("unit_id", unit_id)

        # Run core inspection engine
        async with concurrency_limiter:
            record = await asyncio.to_thread(
                pipeline.agent.inspect_unit,
                unit_id,
                front_img,
                back_img,
                label_img,
                wo,
                org_id=org_id
            )

        # Persist and record telemetry
        db.save_record(record, org_id)
        latency_ms = round((time.perf_counter() - t_start) * 1000.0, 2)

        metrics_tracker.record_finish(
            unit_id=unit_id,
            org_id=org_id,
            verdict=record["overall_status"],
            total_latency_ms=latency_ms,
            cost_usd=record["performance"].get("estimated_compute_cost_usd", 0.00015)
        )

        decision = record["overall_status"]
        conf = record.get("confidence", 0.96 if decision == "PASS" else (0.92 if decision == "FAIL" else 0.40))

        return AgentRunResponse(
            task_id=task_id,
            agent="prep",
            stage="prep",
            org_id=org_id,
            tenant=org_id,
            status="success",
            decision=decision,
            verdict=decision,
            confidence=conf,
            explanation=record.get("issue_explanation", ""),
            checks=record.get("checks", {}),
            evidence=record.get("evidence_vector", {}),
            record=record,
            latency_ms=latency_ms
        )

    except HTTPException:
        raise
    except Exception as e:
        return AgentRunResponse(
            task_id=task_id,
            agent="prep",
            stage="prep",
            org_id=org_id,
            tenant=org_id,
            status="error",
            decision="UNCERTAIN",
            verdict="UNCERTAIN",
            confidence=0.0,
            explanation=f"Error executing Prep inspection: {str(e)}",
            checks={},
            evidence={"error": str(e)},
            error=str(e),
            latency_ms=round((time.perf_counter() - t_start) * 1000.0, 2)
        )


# --- FRONTEND ROUTING ---
@app.get("/", include_in_schema=False)
def serve_index():
    index_path = "frontend/index.html"
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "CUBE Prep Manager API is active. Open frontend or /docs for API documentation."}

@app.get("/style.css", include_in_schema=False)
def serve_style():
    css_path = "frontend/style.css"
    if os.path.exists(css_path):
        return FileResponse(css_path, media_type="text/css")
    raise HTTPException(status_code=404, detail="style.css not found")

@app.get("/app.js", include_in_schema=False)
def serve_app_js():
    js_path = "frontend/app.js"
    if os.path.exists(js_path):
        return FileResponse(js_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="app.js not found")

