"""
Rule-Based Decision Engine for CUBE Prep Manager.
Amazon FBA Inbound Prep Compliance Rules Engine.
Produces:
- Individual check status: PASS / FAIL / UNCERTAIN / NOT_REQUIRED
- Overall status: PASS / FAIL / UNCERTAIN
- Machine-readable evidence regions
- Exact itemized failure reasons
"""

class PrepRuleEngine:
    def __init__(self):
        pass

    def evaluate(self, work_order, evidence_vector):
        """
        Evaluate compliance checks based on work order and deterministic evidence vector.
        """
        checks = {}
        failure_reasons = []
        uncertain_reasons = []
        evidence_regions = []

        is_ambiguous = evidence_vector.get("image_quality", {}).get("is_ambiguous", False)

        # -------------------------------------------------------------
        # 1. Polybag Check
        # -------------------------------------------------------------
        wo_poly = bool(work_order.get("wo_polybag", False))
        if not wo_poly:
            checks["polybag_present_sealed"] = {
                "verdict": "PASS",
                "applicable": False,
                "detail": "Polybag not required by work order."
            }
        else:
            poly_info = evidence_vector.get("polybag", {})
            st = poly_info.get("status", "uncertain")
            if st == "yes":
                checks["polybag_present_sealed"] = {
                    "verdict": "PASS",
                    "applicable": True,
                    "detail": "Polybag is present and verified correctly sealed."
                }
            elif st == "not_sealed":
                checks["polybag_present_sealed"] = {
                    "verdict": "FAIL",
                    "applicable": True,
                    "detail": "Polybag is present but closure/seal is open or improper."
                }
                failure_reasons.append("Polybag is present but the closure/seal is not correctly closed.")
            elif st == "missing":
                checks["polybag_present_sealed"] = {
                    "verdict": "FAIL",
                    "applicable": True,
                    "detail": "Polybag is required by work order but no polybag is visible."
                }
                failure_reasons.append("Polybag is required but no polybag is visible.")
            else:
                checks["polybag_present_sealed"] = {
                    "verdict": "UNCERTAIN",
                    "applicable": True,
                    "detail": poly_info.get("reason", "Imagery does not reliably establish polybag presence or closure.")
                }
                uncertain_reasons.append("Imagery does not reliably establish polybag presence or closure.")

        # -------------------------------------------------------------
        # 2. Suffocation Warning Check
        # -------------------------------------------------------------
        wo_warn = bool(work_order.get("wo_suffocation_warning", False))
        if not wo_warn:
            checks["suffocation_warning"] = {
                "verdict": "PASS",
                "applicable": False,
                "detail": "Suffocation warning not required by work order."
            }
        else:
            warn_info = evidence_vector.get("suffocation_warning", {})
            st = warn_info.get("status", "uncertain")
            if st == "legible":
                checks["suffocation_warning"] = {
                    "verdict": "PASS",
                    "applicable": True,
                    "detail": "Suffocation warning is present, unobstructed and fully legible."
                }
            elif st == "obscured_by_fold":
                checks["suffocation_warning"] = {
                    "verdict": "FAIL",
                    "applicable": True,
                    "detail": "Suffocation warning is present but obscured by a fold."
                }
                failure_reasons.append("Suffocation warning is present but obscured by a fold.")
            elif st == "missing":
                checks["suffocation_warning"] = {
                    "verdict": "FAIL",
                    "applicable": True,
                    "detail": "Suffocation warning is required but missing from polybag."
                }
                failure_reasons.append("Suffocation warning is required but missing from polybag.")
            else:
                checks["suffocation_warning"] = {
                    "verdict": "UNCERTAIN",
                    "applicable": True,
                    "detail": warn_info.get("reason", "Imagery does not reliably establish warning visibility or legibility.")
                }
                uncertain_reasons.append("Imagery does not reliably establish warning visibility or legibility.")

        # -------------------------------------------------------------
        # 3. FNSKU Label Placement Check
        # -------------------------------------------------------------
        fnsku_info = evidence_vector.get("fnsku", {})
        placement = fnsku_info.get("placement", "uncertain")
        fnsku_box = fnsku_info.get("box")
        if fnsku_box:
            evidence_regions.append({
                "view": "front",
                "label": "fnsku_label",
                "bbox": fnsku_box,
                "measurement": {
                    "edge_distance_px": fnsku_info.get("edge_distance_px", 0),
                    "seam_overlap_iou": fnsku_info.get("seam_overlap_iou", 0.0),
                    "curvature": fnsku_info.get("curvature_metric", 0.0)
                }
            })

        if placement == "flat":
            checks["fnsku_label_placement"] = {
                "verdict": "PASS",
                "applicable": True,
                "detail": "FNSKU label is flat, properly centered away from edges, curves, and seams."
            }
        elif placement == "on_seam":
            checks["fnsku_label_placement"] = {
                "verdict": "FAIL",
                "applicable": True,
                "detail": "FNSKU label overlaps a package seam."
            }
            failure_reasons.append("FNSKU label overlaps a package seam.")
        elif placement == "on_edge":
            checks["fnsku_label_placement"] = {
                "verdict": "FAIL",
                "applicable": True,
                "detail": "FNSKU label is placed across/too close to a package edge."
            }
            failure_reasons.append("FNSKU label is placed across/too close to a package edge.")
        elif placement == "on_curve":
            checks["fnsku_label_placement"] = {
                "verdict": "FAIL",
                "applicable": True,
                "detail": "FNSKU label is placed across a curved or cylindrical surface."
            }
            failure_reasons.append("FNSKU label is placed across a curved or cylindrical surface.")
        elif placement == "missing":
            checks["fnsku_label_placement"] = {
                "verdict": "FAIL",
                "applicable": True,
                "detail": "FNSKU label is missing from prepped unit."
            }
            failure_reasons.append("FNSKU label is missing from prepped unit.")
        else:
            checks["fnsku_label_placement"] = {
                "verdict": "UNCERTAIN",
                "applicable": True,
                "detail": fnsku_info.get("reason", "Imagery does not reliably establish FNSKU placement.")
            }
            uncertain_reasons.append("Imagery does not reliably establish FNSKU placement.")

        # -------------------------------------------------------------
        # 4. Original Barcode Covered Check
        # -------------------------------------------------------------
        barcode_info = evidence_vector.get("original_barcode", {})
        bc_st = barcode_info.get("status", "uncertain")
        if bc_st == "yes":
            checks["original_barcode_covered"] = {
                "verdict": "PASS",
                "applicable": True,
                "detail": "Original manufacturer barcode is fully covered or not exposed."
            }
        elif bc_st == "no":
            checks["original_barcode_covered"] = {
                "verdict": "FAIL",
                "applicable": True,
                "detail": "Original manufacturer barcode remains visible."
            }
            failure_reasons.append("Original manufacturer barcode remains visible.")
        else:
            checks["original_barcode_covered"] = {
                "verdict": "UNCERTAIN",
                "applicable": True,
                "detail": barcode_info.get("reason", "Imagery does not reliably establish whether the original barcode is covered.")
            }
            uncertain_reasons.append("Imagery does not reliably establish whether the original barcode is covered.")

        # -------------------------------------------------------------
        # 5. Expiry Date Check
        # -------------------------------------------------------------
        wo_exp = bool(work_order.get("wo_expiry_date", False))
        if not wo_exp:
            checks["expiry_date"] = {
                "verdict": "PASS",
                "applicable": False,
                "detail": "Expiry date verification not required by work order."
            }
        else:
            exp_info = evidence_vector.get("expiry_date", {})
            exp_st = exp_info.get("status", "uncertain")
            if exp_st == "legible":
                checks["expiry_date"] = {
                    "verdict": "PASS",
                    "applicable": True,
                    "detail": "Expiry date is visible and legible after wrapping."
                }
            elif exp_st == "illegible_after_wrap":
                checks["expiry_date"] = {
                    "verdict": "FAIL",
                    "applicable": True,
                    "detail": "Expiry information is not legible after wrapping."
                }
                failure_reasons.append("Expiry information is not legible after wrapping.")
            else:
                checks["expiry_date"] = {
                    "verdict": "UNCERTAIN",
                    "applicable": True,
                    "detail": exp_info.get("reason", "Imagery does not reliably establish expiry date legibility.")
                }
                uncertain_reasons.append("Imagery does not reliably establish expiry date legibility.")

        # -------------------------------------------------------------
        # 6. Handling Marks Check
        # -------------------------------------------------------------
        handling_req_str = str(work_order.get("wo_handling_marks", ""))
        wo_handling = bool(handling_req_str and handling_req_str != "nan" and handling_req_str.strip())
        if not wo_handling:
            checks["handling_marks"] = {
                "verdict": "PASS",
                "applicable": False,
                "detail": "Handling marks not required by work order."
            }
        else:
            hand_info = evidence_vector.get("handling_marks", {})
            hand_st = hand_info.get("status", "uncertain")
            if hand_st == "all_present":
                checks["handling_marks"] = {
                    "verdict": "PASS",
                    "applicable": True,
                    "detail": "All required handling marks are present."
                }
            elif hand_st == "some_missing":
                checks["handling_marks"] = {
                    "verdict": "FAIL",
                    "applicable": True,
                    "detail": "One or more required handling marks are missing."
                }
                failure_reasons.append("One or more required handling marks are missing.")
            else:
                checks["handling_marks"] = {
                    "verdict": "UNCERTAIN",
                    "applicable": True,
                    "detail": hand_info.get("reason", "Imagery does not reliably establish handling marks presence.")
                }
                uncertain_reasons.append("Imagery does not reliably establish handling marks presence.")

        # -------------------------------------------------------------
        # Overall Verdict Determination
        # -------------------------------------------------------------
        if failure_reasons:
            overall_status = "FAIL"
            explanation = " ".join(failure_reasons)
            confidence = 0.92
        elif uncertain_reasons or is_ambiguous:
            overall_status = "UNCERTAIN"
            explanation = " ".join(uncertain_reasons) if uncertain_reasons else "Imagery quality does not reliably establish compliance."
            confidence = 0.40
        else:
            overall_status = "PASS"
            explanation = "All applicable visual preparation checks are supported by the available evidence."
            confidence = 0.96

        return {
            "overall_status": overall_status,
            "explanation": explanation,
            "confidence": confidence,
            "checks": checks,
            "failure_reasons": failure_reasons,
            "uncertain_reasons": uncertain_reasons,
            "evidence_regions": evidence_regions
        }
