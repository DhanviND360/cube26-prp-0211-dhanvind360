"""
Export Compliance Records for All Units (CUBE Prep Manager).
Generates:
- Individual unit JSON evidence records: submissions/DhanviND360/records/units/UNIT-XXXX.json
- Combined JSON record: submissions/DhanviND360/records/compliance_records.json
- Standardized CSV: submissions/DhanviND360/records/compliance_records.csv
- Root data sync: data/compliance_records.csv
"""

import os
import sys
sys.path.insert(0, os.path.abspath("."))
import cv2
import json
import time
import pandas as pd
from agent.prep_agent import PrepManagerAgent

def export_all_records(csv_path="cube_prep_dataset/cube_prep_dataset.csv",
                       output_dir="submissions/DhanviND360/records"):
    print("=" * 65)
    print(" EXPORTING OFFICIAL COMPLIANCE RECORDS")
    print("=" * 65)
    
    df = pd.read_csv(csv_path)
    agent = PrepManagerAgent()
    
    units_dir = os.path.join(output_dir, "units")
    os.makedirs(units_dir, exist_ok=True)
    os.makedirs("data", exist_ok=True)
    
    all_json_records = []
    csv_rows = []
    
    print(f"Processing all {len(df)} units across org_demo_alpha and org_demo_bravo...")
    t_start = time.time()
    
    for idx, row in df.iterrows():
        uid = row["unit_id"]
        f_p = os.path.join("cube_prep_dataset", f"images/{uid}_front.jpg")
        b_p = os.path.join("cube_prep_dataset", f"images/{uid}_back.jpg")
        l_p = os.path.join("cube_prep_dataset", f"images/{uid}_label.jpg")
        
        f_img = cv2.imread(f_p)
        b_img = cv2.imread(b_p)
        l_img = cv2.imread(l_p)
        
        rec = agent.inspect_unit(uid, f_img, b_img, l_img, row.to_dict(), org_id=row["org_id"])
        
        # Save individual unit JSON
        unit_json_path = os.path.join(units_dir, f"{uid}.json")
        with open(unit_json_path, "w") as f:
            json.dump(rec, f, indent=2)
            
        all_json_records.append(rec)
        
        # Flatten for CSV export
        checks = rec.get("checks", {})
        csv_rows.append({
            "record_id": rec["record_id"],
            "unit_id": rec["unit_id"],
            "org_id": rec["org_id"],
            "work_order_id": rec["work_order_id"],
            "fba_shipment_id": rec["fba_shipment_id"],
            "sku": rec["sku"],
            "asin": rec["asin"],
            "fnsku": rec["fnsku"],
            "overall_status": rec["overall_status"],
            "workflow_state": rec["workflow_state"],
            "polybag_check": checks.get("polybag_present_sealed", {}).get("verdict", "N/A"),
            "warning_check": checks.get("suffocation_warning", {}).get("verdict", "N/A"),
            "fnsku_check": checks.get("fnsku_label_placement", {}).get("verdict", "N/A"),
            "barcode_check": checks.get("original_barcode_covered", {}).get("verdict", "N/A"),
            "expiry_check": checks.get("expiry_date", {}).get("verdict", "N/A"),
            "handling_check": checks.get("handling_marks", {}).get("verdict", "N/A"),
            "issue_explanation": rec["issue_explanation"],
            "latency_ms": rec["performance"]["latency_ms"],
            "cost_usd": rec["performance"]["estimated_compute_cost_usd"],
            "is_calibrated": rec["calibration"]["is_calibrated"],
            "operator_id": rec["operator_id"],
            "captured_at": rec["captured_at"]
        })
        
        if (idx + 1) % 20 == 0:
            print(f"  Processed {idx + 1} / {len(df)} units ({time.time() - t_start:.1f}s elapsed)...")
            
    # Save combined JSON
    combined_json_path = os.path.join(output_dir, "compliance_records.json")
    with open(combined_json_path, "w") as f:
        json.dump(all_json_records, f, indent=2)
        
    # Save CSV
    export_df = pd.DataFrame(csv_rows)
    combined_csv_path = os.path.join(output_dir, "compliance_records.csv")
    export_df.to_csv(combined_csv_path, index=False)
    
    # Also save to data/ for repository reference
    export_df.to_csv("data/compliance_records.csv", index=False)
    with open("data/compliance_records.json", "w") as f:
        json.dump(all_json_records, f, indent=2)
        
    print(f"\nSuccessfully generated:")
    print(f"  - {len(all_json_records)} unit records in {units_dir}")
    print(f"  - Combined JSON: {combined_json_path}")
    print(f"  - Combined CSV : {combined_csv_path}")
    print(f"  - Synchronized root data: data/compliance_records.csv")

if __name__ == "__main__":
    export_all_records()
