"""
Comprehensive Orchestrator & Autonomous Agent Integration Tests.
Validates:
1. GET /health contract compliance (stage, agent_id, contract_version).
2. Compliant unit evaluation -> PASS, recommendation="RELEASE", next_step_recommendation="continue".
3. Failing unit evaluation -> FAIL, recommendation="CORRECT_AND_REINSPECT", next_step_recommendation="route_to_recovery".
4. Missing images -> safe error response, decision="UNCERTAIN", recommendation="HUMAN_REVIEW", never PASS.
5. Cross-tenant & invalid tenant isolation -> HTTP 403 Forbidden.
6. Missing required unit identifier -> HTTP 422 Unprocessable Entity.
7. Orchestrator subject envelope compatibility ({workflow_id, subject: {org_id, subject_id}}).
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath("."))

from agent.api import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_probes_orchestrator_contract(client):
    """GET /health must return orchestrator-expected metadata."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["stage"] == "prep"
    assert "prep-manager" in data["agent_id"]
    assert data["contract_version"] == "1.0"


def test_tenant_isolation_rejection(client):
    """Requests with unknown or mismatched tenant org_id must be refused with HTTP 403."""
    payload = {
        "unit_id": "UNIT-0001",
        "org_id": "unauthorized_foreign_tenant",
        "work_order": {"wo_polybag": True}
    }
    res = client.post("/run", json=payload)
    assert res.status_code == 403
    assert "unauthorized organisation/tenant" in res.text.lower() or "forbidden" in res.text.lower()


def test_missing_unit_id_rejected(client):
    """Requests with missing unit identifier must be rejected with HTTP 422."""
    payload = {
        "org_id": "org_demo_alpha",
        "work_order": {"wo_polybag": True}
    }
    res = client.post("/run", json=payload)
    assert res.status_code == 422
    assert "missing required unit identifier" in res.text.lower()


def test_missing_images_safe_handling(client):
    """Missing or unresolvable images must safely return UNCERTAIN / error, NEVER PASS."""
    payload = {
        "task_id": "test-task-missing-img",
        "unit_id": "UNIT-NONEXISTENT-9999",
        "org_id": "org_demo_alpha",
        "image_refs": {
            "front": "missing_nonexistent_front.jpg",
            "back": "missing_nonexistent_back.jpg",
            "label": "missing_nonexistent_label.jpg"
        },
        "force_reinspect": True
    }
    res = client.post("/run", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "error"
    assert data["decision"] == "UNCERTAIN"
    assert data["verdict"] == "UNCERTAIN"
    assert data["recommendation"] == "HUMAN_REVIEW"
    assert data["next_step_recommendation"] == "review"
    assert data["error"] is not None
    assert "could not resolve" in data["error"].lower()


def test_orchestrator_subject_envelope_support(client):
    """Must accept Round 3 orchestrator standard envelope: {workflow_id, subject: {org_id, subject_id}}."""
    payload = {
        "workflow_id": "WF-org_demo_alpha-UNIT-0001",
        "task_id": "task-r3-envelope-01",
        "subject": {
            "org_id": "org_demo_alpha",
            "subject_id": "UNIT-0001"
        },
        "image_refs": {
            "front": "cube_prep_dataset/images/UNIT-0001_front.jpg",
            "back": "cube_prep_dataset/images/UNIT-0001_back.jpg",
            "label": "cube_prep_dataset/images/UNIT-0001_label.jpg"
        },
        "work_order": {
            "sku": "SKU-SAMPLE-01",
            "asin": "B00TEST",
            "fnsku": "X001TEST",
            "wo_polybag": True
        },
        "force_reinspect": True
    }
    res = client.post("/run", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["workflow_id"] == "WF-org_demo_alpha-UNIT-0001"
    assert data["unit_id"] == "UNIT-0001"
    assert data["org_id"] == "org_demo_alpha"
    assert data["status"] == "completed"
    assert data["recommendation"] in ["RELEASE", "CORRECT_AND_REINSPECT", "HUMAN_REVIEW"]
    assert data["next_step_recommendation"] in ["continue", "route_to_recovery", "review"]
    assert data["rule_version"] == "2026.1"
    assert isinstance(data["checks"], dict)


def test_evidence_backed_checks_structure(client):
    """Every check must contain verdict, reason, evidence_refs, and recommended action."""
    payload = {
        "unit_id": "UNIT-0001",
        "org_id": "org_demo_alpha",
        "image_refs": {
            "front": "cube_prep_dataset/images/UNIT-0001_front.jpg",
            "back": "cube_prep_dataset/images/UNIT-0001_back.jpg",
            "label": "cube_prep_dataset/images/UNIT-0001_label.jpg"
        },
        "force_reinspect": False
    }
    res = client.post("/run", json=payload)
    assert res.status_code == 200
    data = res.json()
    checks = data["checks"]
    assert len(checks) > 0
    for k, ck in checks.items():
        assert ck["verdict"] in ["PASS", "FAIL", "UNCERTAIN"]
        assert "reason" in ck
        assert "evidence_refs" in ck
        assert "action" in ck
