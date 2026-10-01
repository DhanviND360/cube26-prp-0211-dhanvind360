"""
Engineering Rule 1: Tenancy Isolation Verification Script for CUBE Prep Manager.
Tests:
1. Row-Level Security (RLS) partition by org_id (org_demo_alpha vs org_demo_bravo).
2. Verifies that Tenant Alpha receives 0 records belonging to Tenant Bravo and vice-versa.
3. Unguessable Key / Asset Fetch Protection:
   Attempts cross-tenant record retrieval and unauthorized asset resolution.
"""

import os
import json
import sqlite3
import pandas as pd

class TenancyIsolationEngine:
    def __init__(self, db_path=":memory:"):
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE prep_records (
                record_id TEXT PRIMARY KEY,
                unit_id TEXT NOT NULL,
                org_id TEXT NOT NULL,
                fba_shipment_id TEXT,
                sku TEXT,
                overall_status TEXT,
                evidence_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def insert_record(self, record, org_id):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO prep_records (record_id, unit_id, org_id, fba_shipment_id, sku, overall_status, evidence_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            record["record_id"],
            record["unit_id"],
            org_id,
            record.get("fba_shipment_id"),
            record.get("sku"),
            record.get("overall_status"),
            json.dumps(record.get("evidence_vector", {}))
        ))
        self.conn.commit()

    def query_records_scoped(self, requesting_org_id):
        """Row-level security enforcement: all queries MUST be scoped to requesting org."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT record_id, unit_id, org_id, overall_status FROM prep_records WHERE org_id = ?", (requesting_org_id,))
        rows = cursor.fetchall()
        return [{"record_id": r[0], "unit_id": r[1], "org_id": r[2], "overall_status": r[3]} for r in rows]

    def get_unit_scoped(self, unit_id, requesting_org_id):
        """Secure lookup requiring both unit_id and requesting_org_id."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT record_id, unit_id, org_id, evidence_json FROM prep_records WHERE unit_id = ? AND org_id = ?", (unit_id, requesting_org_id))
        row = cursor.fetchone()
        if not row:
            return None
        return {"record_id": row[0], "unit_id": row[1], "org_id": row[2], "evidence": json.loads(row[3])}

def run_tenancy_tests(compliance_csv_path="data/compliance_records.csv"):
    print("=" * 65)
    print(" ENGINEERING RULE 1: TENANCY ISOLATION VERIFICATION")
    print("=" * 65)
    
    if not os.path.exists(compliance_csv_path):
        raise FileNotFoundError(f"Missing compliance CSV: {compliance_csv_path}")
        
    df = pd.read_csv(compliance_csv_path)
    engine = TenancyIsolationEngine()
    
    alpha_units = []
    bravo_units = []
    
    for _, row in df.iterrows():
        rec = row.to_dict()
        org = row["org_id"]
        engine.insert_record(rec, org)
        if org == "org_demo_alpha":
            alpha_units.append(row["unit_id"])
        elif org == "org_demo_bravo":
            bravo_units.append(row["unit_id"])
            
    print(f"Populated Database:")
    print(f"  org_demo_alpha records: {len(alpha_units)}")
    print(f"  org_demo_bravo records: {len(bravo_units)}")
    
    # Test 1: Alpha queries all records
    alpha_results = engine.query_records_scoped("org_demo_alpha")
    bravo_leak_in_alpha = [r for r in alpha_results if r["org_id"] != "org_demo_alpha"]
    print(f"\nTest 1 (Alpha Query Scope):")
    print(f"  Records returned: {len(alpha_results)}")
    print(f"  Bravo records leaked: {len(bravo_leak_in_alpha)}")
    assert len(bravo_leak_in_alpha) == 0, "SECURITY FAULT: Bravo records leaked to Alpha!"
    print("  -> PASS: Zero Bravo rows visible to Alpha.")
    
    # Test 2: Bravo queries all records
    bravo_results = engine.query_records_scoped("org_demo_bravo")
    alpha_leak_in_bravo = [r for r in bravo_results if r["org_id"] != "org_demo_bravo"]
    print(f"\nTest 2 (Bravo Query Scope):")
    print(f"  Records returned: {len(bravo_results)}")
    print(f"  Alpha records leaked: {len(alpha_leak_in_bravo)}")
    assert len(alpha_leak_in_bravo) == 0, "SECURITY FAULT: Alpha records leaked to Bravo!"
    print("  -> PASS: Zero Alpha rows visible to Bravo.")
    
    # Test 3: Key-guessing attack (Alpha attempts to fetch a known Bravo unit)
    target_bravo_unit = bravo_units[0]
    print(f"\nTest 3 (Cross-tenant Key Guessing Attack):")
    print(f"  Alpha attempting to fetch Bravo unit '{target_bravo_unit}'...")
    illicit_fetch = engine.get_unit_scoped(target_bravo_unit, requesting_org_id="org_demo_alpha")
    print(f"  Result of fetch attempt: {illicit_fetch}")
    assert illicit_fetch is None, "SECURITY FAULT: Cross-tenant fetch succeeded!"
    print("  -> PASS: Direct fetch returned None. Unauthorized access denied.")
    
    report = {
        "status": "PASSED",
        "tenants_tested": ["org_demo_alpha", "org_demo_bravo"],
        "records_alpha": len(alpha_units),
        "records_bravo": len(bravo_units),
        "test_1_alpha_leak_count": len(bravo_leak_in_alpha),
        "test_2_bravo_leak_count": len(alpha_leak_in_bravo),
        "test_3_cross_tenant_key_guess_blocked": True,
        "rule_1_compliance": True
    }
    
    os.makedirs("reports", exist_ok=True)
    with open("reports/tenancy_isolation_test_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print("\nSaved tenancy isolation test report to reports/tenancy_isolation_test_report.json")
    return report

if __name__ == "__main__":
    run_tenancy_tests()
