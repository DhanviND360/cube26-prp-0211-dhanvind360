"""
Database Abstraction Layer for CUBE Prep Manager.
Supports:
- Local SQLite / JSON (offline local execution, development, CI)
- Supabase PostgreSQL (managed cloud database with Row-Level Security)
Guarantees tenant isolation before any query or write (Engineering Rule 1).
"""

import os
import json
import sqlite3
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from agent.config import settings

class BaseDatabaseProvider(ABC):
    @abstractmethod
    def save_record(self, record: Dict[str, Any], org_id: str) -> bool:
        pass

    @abstractmethod
    def get_record(self, unit_id: str, org_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def list_records(self, org_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def record_override(self, override_entry: Dict[str, Any]) -> bool:
        pass

class LocalDatabaseProvider(BaseDatabaseProvider):
    def __init__(self, db_path: str = "data/prep_records.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prep_records (
                    record_id TEXT PRIMARY KEY,
                    unit_id TEXT NOT NULL,
                    org_id TEXT NOT NULL,
                    work_order_id TEXT,
                    fba_shipment_id TEXT,
                    sku TEXT,
                    overall_status TEXT NOT NULL,
                    workflow_state TEXT NOT NULL,
                    issue_explanation TEXT,
                    record_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_overrides (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    unit_id TEXT NOT NULL,
                    org_id TEXT NOT NULL,
                    original_verdict TEXT NOT NULL,
                    new_verdict TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    operator_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_prep_org ON prep_records(org_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_prep_unit ON prep_records(unit_id)")
            conn.commit()

    def save_record(self, record: Dict[str, Any], org_id: str) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO prep_records 
                    (record_id, unit_id, org_id, work_order_id, fba_shipment_id, sku, overall_status, workflow_state, issue_explanation, record_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record["record_id"],
                    record["unit_id"],
                    org_id,
                    record.get("work_order_id"),
                    record.get("fba_shipment_id"),
                    record.get("sku"),
                    record["overall_status"],
                    record.get("workflow_state", "completed"),
                    record.get("issue_explanation", ""),
                    json.dumps(record)
                ))
                conn.commit()
            return True
        except Exception as e:
            print(f"[LocalDatabaseProvider] Error saving record: {e}")
            return False

    def get_record(self, unit_id: str, org_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT record_json FROM prep_records WHERE unit_id = ? AND org_id = ?", (unit_id, org_id))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
        return None

    def list_records(self, org_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT record_json FROM prep_records 
                WHERE org_id = ? 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (org_id, limit, offset))
            rows = cursor.fetchall()
            return [json.loads(r[0]) for r in rows]

    def record_override(self, override_entry: Dict[str, Any]) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO audit_overrides (unit_id, org_id, original_verdict, new_verdict, reason, operator_id, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    override_entry["unit_id"],
                    override_entry["org_id"],
                    override_entry["original_verdict"],
                    override_entry["new_verdict"],
                    override_entry["reason"],
                    override_entry["operator_id"],
                    override_entry["timestamp"]
                ))
                conn.commit()
            return True
        except Exception as e:
            print(f"[LocalDatabaseProvider] Error recording override: {e}")
            return False

class SupabaseDatabaseProvider(BaseDatabaseProvider):
    def __init__(self, supabase_url: str, supabase_key: str):
        self.fallback = LocalDatabaseProvider()
        self.client = None
        if supabase_url and supabase_key:
            try:
                from supabase import create_client
                self.client = create_client(supabase_url, supabase_key)
            except Exception as e:
                print(f"[SupabaseDatabaseProvider] Init failed: {e}. Falling back to SQLite.")

    def save_record(self, record: Dict[str, Any], org_id: str) -> bool:
        if self.client is None:
            return self.fallback.save_record(record, org_id)
        try:
            payload = {
                "record_id": record["record_id"],
                "unit_id": record["unit_id"],
                "org_id": org_id,
                "work_order_id": record.get("work_order_id"),
                "fba_shipment_id": record.get("fba_shipment_id"),
                "sku": record.get("sku"),
                "overall_status": record["overall_status"],
                "workflow_state": record.get("workflow_state", "completed"),
                "issue_explanation": record.get("issue_explanation", ""),
                "evidence_payload": record
            }
            self.client.table("prep_records").upsert(payload).execute()
            # Also save to local fallback for caching
            self.fallback.save_record(record, org_id)
            return True
        except Exception as e:
            print(f"[SupabaseDatabaseProvider] Save record error: {e}. Falling back to SQLite.")
            return self.fallback.save_record(record, org_id)

    def get_record(self, unit_id: str, org_id: str) -> Optional[Dict[str, Any]]:
        if self.client is None:
            return self.fallback.get_record(unit_id, org_id)
        try:
            # Query scoped strictly to org_id (Rule 1)
            resp = self.client.table("prep_records").select("evidence_payload").eq("unit_id", unit_id).eq("org_id", org_id).execute()
            if resp.data and len(resp.data) > 0:
                return resp.data[0]["evidence_payload"]
        except Exception as e:
            print(f"[SupabaseDatabaseProvider] Get record error: {e}")
        return self.fallback.get_record(unit_id, org_id)

    def list_records(self, org_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        if self.client is None:
            return self.fallback.list_records(org_id, limit, offset)
        try:
            resp = self.client.table("prep_records").select("evidence_payload").eq("org_id", org_id).range(offset, offset + limit - 1).execute()
            if resp.data:
                return [row["evidence_payload"] for row in resp.data]
        except Exception as e:
            print(f"[SupabaseDatabaseProvider] List records error: {e}")
        return self.fallback.list_records(org_id, limit, offset)

    def record_override(self, override_entry: Dict[str, Any]) -> bool:
        if self.client is None:
            return self.fallback.record_override(override_entry)
        try:
            self.client.table("audit_overrides").insert(override_entry).execute()
            self.fallback.record_override(override_entry)
            return True
        except Exception as e:
            print(f"[SupabaseDatabaseProvider] Override error: {e}")
            return self.fallback.record_override(override_entry)

def get_database_provider() -> BaseDatabaseProvider:
    if settings.DATABASE_BACKEND.lower() == "supabase" and settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        return SupabaseDatabaseProvider(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_SERVICE_ROLE_KEY
        )
    return LocalDatabaseProvider()
