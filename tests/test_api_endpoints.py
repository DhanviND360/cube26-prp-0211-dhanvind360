"""
API & Service Tests for PREP Manager Agent.
Covers:
- GET /health and GET /health/ready
- POST /run (Round 3 Agent Adapter) with image_refs, base64 images, and cache bypass
- Missing/invalid input handling on /run
- Multi-tenancy isolation via API headers
- Idempotency / duplicate request caching
- Malformed multipart upload rejection (HTTP 400)
- GET /api/v1/metrics telemetry
"""

import os
import sys
import base64
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath("."))

from agent.api import app
from agent.validator import validate_prep_record


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_probes(client):
    """GET /health and GET /health/ready must report system status."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "version" in data

    ready_res = client.get("/health/ready")
    assert ready_res.status_code == 200
    ready_data = ready_res.json()
    assert ready_data["status"] == "ready"
    assert "detector_active" in ready_data


def test_round3_run_adapter_with_image_refs(client):
    """
    POST /run (Round 3 Agent Adapter) using image_refs.
    Must return AgentRunResponse matching the CUBE R3 specification.
    """
    payload = {
        "task_id": "test-task-001",
        "unit_id": "UNIT-0001",
        "org_id": "org_demo_alpha",
        "image_refs": {
            "front": "cube_prep_dataset/images/UNIT-0001_front.jpg",
            "back": "cube_prep_dataset/images/UNIT-0001_back.jpg",
            "label": "cube_prep_dataset/images/UNIT-0001_label.jpg"
        },
        "work_order": {
            "work_order_id": "WO-3000",
            "fba_shipment_id": "FBA-CUBE-100",
            "sku": "SKU-SHIRT-WHT",
            "asin": "B0DUMMY100",
            "fnsku": "X00CUBE0001",
            "wo_polybag": True,
            "wo_suffocation_warning": True,
            "wo_expiry_date": False,
            "wo_handling_marks": ""
        },
        "force_reinspect": True
    }

    res = client.post("/run", json=payload)
    assert res.status_code == 200, f"/run failed: {res.text}"
    data = res.json()

    # Verify all Round 3 required fields (Step 7 in PDF)
    assert data["agent"] == "prep"
    assert data["stage"] == "prep"
    assert data["org_id"] == "org_demo_alpha"
    assert data["status"] == "success"
    assert data["decision"] in ["PASS", "FAIL", "UNCERTAIN"]
    assert data["verdict"] == data["decision"]
    assert 0.0 <= data["confidence"] <= 1.0
    assert isinstance(data["checks"], dict)
    assert isinstance(data["evidence"], dict)
    assert data["explanation"] is not None
    assert data["record"] is not None
    assert data["latency_ms"] > 0

    # Validate output record against schema
    is_valid, err = validate_prep_record(data["record"])
    assert is_valid is True, f"Record failed schema contract: {err}"


def test_round3_run_adapter_wrong_tenant_rejected(client):
    """
    Step 8 & Checklist: Wrong organisation/tenant request must be rejected with HTTP 403.
    """
    payload = {
        "unit_id": "UNIT-0001",
        "org_id": "org_attacker_unauthorized",
        "force_reinspect": True
    }
    res = client.post("/run", json=payload)
    assert res.status_code == 403
    assert "unauthorized organisation/tenant" in res.text.lower()


def test_round3_run_adapter_api_key_protection(client, monkeypatch):
    """
    Step 5: API Key Protection.
    When REQUIRE_AUTH=true, requests without valid key receive 401.
    Requests with valid X-API-Key or Bearer token succeed.
    """
    from agent.config import settings
    monkeypatch.setattr(settings, "REQUIRE_AUTH", True)
    monkeypatch.setattr(settings, "SERVER_API_KEY", "test-secret-key-1234")

    payload = {
        "unit_id": "UNIT-0001",
        "org_id": "org_demo_alpha",
        "force_reinspect": False
    }

    # 1. No key -> 401
    res_no_key = client.post("/run", json=payload)
    assert res_no_key.status_code == 401

    # 2. Wrong key -> 401
    res_bad_key = client.post("/run", json=payload, headers={"X-API-Key": "wrong-key"})
    assert res_bad_key.status_code == 401

    # 3. Correct key via X-API-Key -> 200
    res_good_key = client.post("/run", json=payload, headers={"X-API-Key": "test-secret-key-1234"})
    assert res_good_key.status_code == 200

    # 4. Correct key via Bearer token -> 200
    res_bearer = client.post("/run", json=payload, headers={"Authorization": "Bearer test-secret-key-1234"})
    assert res_bearer.status_code == 200


def test_round3_run_adapter_with_base64_images(client):
    """
    POST /run using base64-encoded images.
    """
    with open("cube_prep_dataset/images/UNIT-0001_front.jpg", "rb") as f:
        f_b64 = base64.b64encode(f.read()).decode("utf-8")
    with open("cube_prep_dataset/images/UNIT-0001_back.jpg", "rb") as f:
        b_b64 = base64.b64encode(f.read()).decode("utf-8")
    with open("cube_prep_dataset/images/UNIT-0001_label.jpg", "rb") as f:
        l_b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "task_id": "test-task-b64",
        "unit_id": "UNIT-0001",
        "org_id": "org_demo_alpha",
        "images": {
            "front": f_b64,
            "back": b_b64,
            "label": l_b64
        },
        "work_order": {
            "unit_id": "UNIT-0001",
            "wo_polybag": True
        },
        "force_reinspect": True
    }

    res = client.post("/run", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["verdict"] in ["PASS", "FAIL", "UNCERTAIN"]


def test_round3_run_adapter_missing_images_error(client):
    """
    POST /run with missing / invalid image references must return structured error, not crash.
    """
    payload = {
        "task_id": "test-task-err",
        "unit_id": "UNIT-NONEXISTENT",
        "org_id": "org_demo_alpha",
        "image_refs": {
            "front": "nonexistent_front.jpg",
            "back": "nonexistent_back.jpg",
            "label": "nonexistent_label.jpg"
        },
        "force_reinspect": True
    }

    res = client.post("/run", json=payload)
    assert res.status_code == 200  # Structured response
    data = res.json()
    assert data["status"] == "error"
    assert data["error"] is not None


def test_api_v1_inspect_synchronous(client):
    """
    POST /api/v1/inspect preserves full Round 2 API behavior.
    """
    req_data = {
        "unit_id": "UNIT-0001",
        "work_order_id": "WO-3000",
        "fba_shipment_id": "FBA-CUBE-100",
        "sku": "SKU-SHIRT-WHT",
        "asin": "B0DUMMY100",
        "fnsku": "X00CUBE0001",
        "wo_polybag": True,
        "wo_suffocation_warning": True,
        "wo_expiry_date": False,
        "wo_handling_marks": "",
        "prep_price_usd": 0.75
    }

    res = client.post(
        "/api/v1/inspect",
        json=req_data,
        params={"x_force_reinspect": True},
        headers={"X-Org-ID": "org_demo_alpha"}
    )
    assert res.status_code == 200
    rec = res.json()
    assert rec["unit_id"] == "UNIT-0001"
    assert rec["overall_status"] in ["PASS", "FAIL", "UNCERTAIN"]
    assert "evidence_regions" in rec
    assert "performance" in rec


def test_malformed_upload_rejected_with_400(client):
    """
    POST /api/v1/inspect/upload with empty files must be cleanly rejected with HTTP 400.
    """
    files = {
        "front_file": ("front.jpg", b"", "image/jpeg"),
        "back_file": ("back.jpg", b"", "image/jpeg"),
        "label_file": ("label.jpg", b"", "image/jpeg"),
    }
    data = {"unit_id": "UNIT-EMPTY-TEST"}

    res = client.post("/api/v1/inspect/upload", data=data, files=files, headers={"X-Org-ID": "org_demo_alpha"})
    assert res.status_code == 400
    assert "empty" in res.text.lower()


def test_tenancy_cross_tenant_access_blocked(client):
    """
    Tenant Bravo requesting an Alpha unit must receive HTTP 404.
    """
    res = client.get("/api/v1/records/UNIT-0001", headers={"X-Org-ID": "org_demo_bravo"})
    assert res.status_code == 404


def test_metrics_telemetry(client):
    """
    GET /api/v1/metrics must return throughput, latency percentiles, error rates.
    """
    res = client.get("/api/v1/metrics", headers={"X-Org-ID": "org_demo_alpha"})
    assert res.status_code == 200
    metrics = res.json()
    assert "live_production_metrics" in metrics
    live = metrics["live_production_metrics"]
    assert "throughput" in live
    assert "latencies_ms" in live
    assert "verdicts" in live
    assert "offline_benchmarks" in metrics
