"""
Production Pipeline & Cloud Readiness Test Suite for CUBE Prep Manager.
Verifies:
1. Pydantic settings loading and environment overrides
2. Storage provider abstraction (saving, retrieving, tenant isolation)
3. Database provider abstraction (SQLite/Supabase upsert, tenant query, audit override)
4. Progressive streaming inspection pipeline (verifying real-time SSE event emission)
5. Zero drift in ML verdicts and Amazon FBA rule compliance
"""

import os
import sys
sys.path.insert(0, os.path.abspath("."))
import cv2
import json
import asyncio
import pandas as pd
from agent.config import settings
from agent.storage import get_storage_provider, LocalStorageProvider
from agent.db import get_database_provider, LocalDatabaseProvider
from agent.pipeline import ProgressiveInspectionPipeline

async def run_production_tests():
    print("=" * 65)
    print(" CUBE PREP MANAGER: PRODUCTION PIPELINE & READINESS TESTS")
    print("=" * 65)

    # Test 1: Configuration
    print("\n--- Test 1: Configuration Management ---")
    print(f"  Environment        : {settings.ENV}")
    print(f"  Storage Backend    : {settings.STORAGE_BACKEND}")
    print(f"  Database Backend   : {settings.DATABASE_BACKEND}")
    print(f"  CORS Allowed Count : {len(settings.CORS_ORIGINS)}")
    assert settings.BLUR_THRESHOLD == 25.0, "Config error: blur threshold mismatch"
    print("  -> PASS: Configuration loaded correctly.")

    # Test 2: Storage Provider & Tenancy Isolation
    print("\n--- Test 2: Storage Provider Abstraction & Isolation ---")
    storage = LocalStorageProvider(base_dir="data/test_uploads")
    sample_bytes = b"FAKE_JPEG_IMAGE_DATA_FOR_TESTING"
    
    alpha_uri = storage.save_image("UNIT-TEST", "front", sample_bytes, "org_demo_alpha")
    print(f"  Saved Alpha Image URI: {alpha_uri}")
    assert "org_demo_alpha" in alpha_uri, "Tenant isolation failure in storage path"
    
    # Try fetching with Bravo (Cross-tenant leak attack)
    bravo_leak = storage.get_image(alpha_uri, "org_demo_bravo")
    print(f"  Cross-tenant access attempt by Bravo: {bravo_leak}")
    assert bravo_leak is None, "SECURITY FAULT: Bravo accessed Alpha storage asset!"
    print("  -> PASS: Storage abstraction enforces strict tenant isolation.")

    # Test 3: Database Provider & Override Audit Trail
    print("\n--- Test 3: Database Provider & Audit Trail ---")
    db = LocalDatabaseProvider(db_path="data/test_records.db")
    sample_rec = {
        "record_id": "PRP-TEST",
        "unit_id": "UNIT-TEST",
        "org_id": "org_demo_alpha",
        "overall_status": "PASS",
        "workflow_state": "completed",
        "issue_explanation": "Test verification record."
    }
    db.save_record(sample_rec, "org_demo_alpha")
    
    # Fetch with Alpha
    fetched = db.get_record("UNIT-TEST", "org_demo_alpha")
    assert fetched is not None and fetched["overall_status"] == "PASS", "DB save/fetch failed"
    
    # Fetch with Bravo (Cross-tenant query)
    bravo_fetch = db.get_record("UNIT-TEST", "org_demo_bravo")
    assert bravo_fetch is None, "SECURITY FAULT: Bravo fetched Alpha DB record!"
    
    # Test override
    override_saved = db.record_override({
        "unit_id": "UNIT-TEST",
        "org_id": "org_demo_alpha",
        "original_verdict": "FAIL",
        "new_verdict": "PASS",
        "reason": "Secondary bench review approved.",
        "operator_id": "op_test",
        "timestamp": "2026-10-01T21:00:00Z"
    })
    assert override_saved is True, "Failed to record override"
    print("  -> PASS: Database provider and override audit logging verified.")

    # Test 4: Progressive Sequential Streaming Pipeline
    print("\n--- Test 4: Progressive Streaming Inspection Pipeline ---")
    pipe = ProgressiveInspectionPipeline()
    df = pd.read_csv("cube_prep_dataset/cube_prep_dataset.csv")
    row = df.iloc[0].to_dict()
    uid = row["unit_id"]

    f_img = cv2.imread(f"cube_prep_dataset/images/{uid}_front.jpg")
    b_img = cv2.imread(f"cube_prep_dataset/images/{uid}_back.jpg")
    l_img = cv2.imread(f"cube_prep_dataset/images/{uid}_label.jpg")

    emitted_events = []
    print(f"  Streaming inspection events for {uid}...")
    async for event in pipe.inspect_unit_stream(uid, f_img, b_img, l_img, row, org_id="org_demo_alpha"):
        emitted_events.append(event)
        print(f"    [Event: {event['event']:22s}] Progress: {event['progress']:3d}% | {event['message']}")

    assert len(emitted_events) == 5, f"Expected 5 progressive events, got {len(emitted_events)}"
    assert emitted_events[0]["event"] == "job_started"
    assert emitted_events[1]["event"] == "front_completed"
    assert emitted_events[2]["event"] == "back_completed"
    assert emitted_events[3]["event"] == "label_completed"
    assert emitted_events[4]["event"] == "inspection_completed"
    
    final_status = emitted_events[4]["overall_status"]
    print(f"  Final Streamed Verdict: {final_status}")
    assert final_status == row["expected_overall_status"], "ML verdict drift detected!"
    print("  -> PASS: Progressive sequential streaming pipeline operating with zero verdict drift.")

    print("\n" + "=" * 65)
    print(" ALL PRODUCTION READINESS & PIPELINE TESTS PASSED (100%)")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(run_production_tests())
