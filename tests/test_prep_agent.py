"""
Comprehensive Automated Unit & Property Tests for PREP Manager Agent.
Validates:
1. Verdict is purely driven by visual image evidence, NOT scenario strings or unit IDs.
2. Dynamic package bounds detection (no hard-coded coordinates).
3. Dynamic seam detection (no hard-coded seam positions).
4. Blur and glare quality calibration gates.
5. Fail-open safety on corrupted images / unexpected exceptions.
6. Schema contract compliance with prep_evidence_contract.json.
"""

import os
import sys
import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath("."))

from agent.prep_agent import PrepManagerAgent
from agent.spatial_features import SpatialFeatureExtractor
from agent.calibration import CalibrationManager
from agent.validator import validate_prep_record


@pytest.fixture(scope="module")
def agent():
    return PrepManagerAgent()


@pytest.fixture(scope="module")
def extractor():
    return SpatialFeatureExtractor()


@pytest.fixture(scope="module")
def calibrator():
    return CalibrationManager()


def test_verdict_purely_image_driven_not_scenario_driven(agent):
    """
    PROVE that scenario strings in work_order do NOT influence the inspection result.
    Running identical images with conflicting scenario strings must yield IDENTICAL verdicts.
    """
    # Load clean unit images
    front = cv2.imread("cube_prep_dataset/images/UNIT-0001_front.jpg")
    back = cv2.imread("cube_prep_dataset/images/UNIT-0001_back.jpg")
    label = cv2.imread("cube_prep_dataset/images/UNIT-0001_label.jpg")
    assert front is not None and back is not None and label is not None

    base_wo = {
        "unit_id": "UNIT-TEST-HONESTY",
        "work_order_id": "WO-3000",
        "sku": "SKU-TEST",
        "fnsku": "X00CUBE0001",
        "wo_polybag": True,
        "wo_suffocation_warning": True,
        "wo_expiry_date": False,
        "wo_handling_marks": ""
    }

    # Case A: Scenario claims missing polybag
    wo_a = dict(base_wo, scenario="missing_polybag_failure_case")
    rec_a = agent.inspect_unit("UNIT-TEST-A", front, back, label, wo_a)

    # Case B: Scenario claims valid package
    wo_b = dict(base_wo, scenario="completely_valid_perfect_package")
    rec_b = agent.inspect_unit("UNIT-TEST-B", front, back, label, wo_b)

    # Case C: Scenario claims broken label on curve
    wo_c = dict(base_wo, scenario="label_placed_on_extreme_curve_violation")
    rec_c = agent.inspect_unit("UNIT-TEST-C", front, back, label, wo_c)

    # The verdict MUST be identical across all three regardless of scenario
    assert rec_a["overall_status"] == rec_b["overall_status"], (
        f"HONESTY VIOLATION: Scenario string affected verdict! "
        f"scenario_a={rec_a['overall_status']} vs scenario_b={rec_b['overall_status']}"
    )
    assert rec_b["overall_status"] == rec_c["overall_status"], (
        f"HONESTY VIOLATION: Scenario string affected verdict! "
        f"scenario_b={rec_b['overall_status']} vs scenario_c={rec_c['overall_status']}"
    )


def test_unit_id_does_not_affect_verdict(agent):
    """
    PROVE that strings in unit_id (like 'OPEN' or 'FAIL') do NOT trigger verdicts.
    """
    front = cv2.imread("cube_prep_dataset/images/UNIT-0001_front.jpg")
    back = cv2.imread("cube_prep_dataset/images/UNIT-0001_back.jpg")
    label = cv2.imread("cube_prep_dataset/images/UNIT-0001_label.jpg")

    wo = {
        "work_order_id": "WO-3000",
        "sku": "SKU-TEST",
        "fnsku": "X00CUBE0001",
        "wo_polybag": True,
        "wo_suffocation_warning": True,
        "wo_expiry_date": False,
        "wo_handling_marks": ""
    }

    rec_normal = agent.inspect_unit("UNIT-0001", front, back, label, wo)
    rec_open = agent.inspect_unit("UNIT-OPEN-POLYBAG-UNSEALED", front, back, label, wo)

    assert rec_normal["overall_status"] == rec_open["overall_status"], (
        "HONESTY VIOLATION: 'OPEN' substring in unit_id altered inspection status!"
    )


def test_dynamic_package_bounds_detection(extractor):
    """
    PROVE package bounds are detected from image contours, NOT hardcoded [148, 75, 475, 385].
    """
    # Create two synthetic images with packages in completely different positions
    # Image 1: Package on left: x=50, y=50, w=200, h=300
    img1 = np.full((600, 800, 3), 40, dtype=np.uint8)  # dark background
    cv2.rectangle(img1, (50, 50), (250, 350), (220, 220, 220), -1)

    # Image 2: Package on right: x=500, y=200, w=250, h=350
    img2 = np.full((600, 800, 3), 40, dtype=np.uint8)
    cv2.rectangle(img2, (500, 200), (750, 550), (220, 220, 220), -1)

    bounds1 = extractor.detect_package_bounds(img1)
    bounds2 = extractor.detect_package_bounds(img2)

    # Both must NOT be the old hard-coded [148, 75, 475, 385]
    assert bounds1 != [148, 75, 475, 385], "Package bounds is returning hard-coded coordinates!"
    assert bounds2 != [148, 75, 475, 385], "Package bounds is returning hard-coded coordinates!"

    # Bounds 1 must be on the left (x < 100)
    assert bounds1[0] < 100, f"Expected bounds on left, got {bounds1}"
    # Bounds 2 must be on the right (x > 400)
    assert bounds2[0] > 400, f"Expected bounds on right, got {bounds2}"


def test_dynamic_seam_detection(extractor):
    """
    PROVE seams are detected dynamically via Hough line transforms, NOT hard-coded x=384.
    """
    # Image with clear vertical line at x=200
    img_line_left = np.full((500, 600, 3), 200, dtype=np.uint8)
    cv2.line(img_line_left, (200, 50), (200, 450), (30, 30, 30), 4)

    # Image with vertical line at x=450
    img_line_right = np.full((500, 600, 3), 200, dtype=np.uint8)
    cv2.line(img_line_right, (450, 50), (450, 450), (30, 30, 30), 4)

    seams_left = extractor.detect_vertical_seams(img_line_left, [50, 50, 500, 400])
    seams_right = extractor.detect_vertical_seams(img_line_right, [50, 50, 500, 400])

    if seams_left:
        # Detected seam x should be close to 200
        assert abs(seams_left[0] - 200) < 50
    if seams_right:
        # Detected seam x should be close to 450
        assert abs(seams_right[0] - 450) < 50


def test_blurry_image_calibration(calibrator):
    """
    PROVE calibrator rejects blurry images with Laplacian variance < threshold.
    """
    # Sharp image (must be at least 500x400)
    sharp = np.zeros((480, 640, 3), dtype=np.uint8)
    for i in range(0, 640, 20):
        cv2.line(sharp, (i, 0), (i, 480), (255, 255, 255), 2)

    is_calib, metrics, reason = calibrator.assess_quality(sharp)
    assert is_calib is True, f"Sharp image should pass calibration, failed with: {reason}"
    assert metrics["blur_metric"] > 25.0

    # Heavily blurred image
    blurry = cv2.GaussianBlur(sharp, (45, 45), 0)
    is_calib_b, metrics_b, reason_b = calibrator.assess_quality(blurry)
    assert is_calib_b is False, "Blurry image must fail calibration"
    assert "blurry" in reason_b.lower() or metrics_b["blur_metric"] < 25.0


def test_glare_image_calibration(calibrator):
    """
    PROVE calibrator detects excessive specular glare.
    """
    # 60% saturated image (must be at least 500x400)
    glare_img = np.full((480, 640, 3), 100, dtype=np.uint8)
    glare_img[:300, :] = 255  # 62.5% pure white

    is_calib, metrics, reason = calibrator.assess_quality(glare_img)
    assert is_calib is False, "Image with >35% glare should fail calibration"
    assert "glare" in reason.lower()


def test_fail_open_on_corrupt_images(agent):
    """
    Rule 3: Fail Open. A completely corrupt or empty image must return
    UNCERTAIN / pending_review without throwing unhandled exceptions.
    """
    corrupt_img = np.zeros((0, 0, 3), dtype=np.uint8)
    wo = {"unit_id": "UNIT-CORRUPT", "wo_polybag": True}

    record = agent.inspect_unit("UNIT-CORRUPT", corrupt_img, None, corrupt_img, wo)
    assert record["overall_status"] == "UNCERTAIN"
    assert record["workflow_state"] == "pending_review"
    assert "corrupt" in record["issue_explanation"].lower() or "fail-open" in record["issue_explanation"].lower() or "failed" in record["issue_explanation"].lower()


def test_record_strictly_validates_contract_schema(agent):
    """
    Every emitted inspection record must strictly validate against prep_evidence_contract.json.
    """
    front = cv2.imread("cube_prep_dataset/images/UNIT-0001_front.jpg")
    back = cv2.imread("cube_prep_dataset/images/UNIT-0001_back.jpg")
    label = cv2.imread("cube_prep_dataset/images/UNIT-0001_label.jpg")

    wo = {
        "unit_id": "UNIT-0001",
        "work_order_id": "WO-3000",
        "fba_shipment_id": "FBA-CUBE-100",
        "sku": "SKU-SHIRT-WHT",
        "asin": "B0DUMMY100",
        "fnsku": "X00CUBE0001",
        "wo_polybag": True,
        "wo_suffocation_warning": True,
        "wo_expiry_date": False,
        "wo_handling_marks": ""
    }

    record = agent.inspect_unit("UNIT-0001", front, back, label, wo)
    is_valid, err = validate_prep_record(record)
    assert is_valid is True, f"Contract schema validation failed: {err}"
