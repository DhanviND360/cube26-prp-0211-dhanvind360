"""
Production Metrics, Telemetry & Performance Tracker for CUBE Prep Manager.
Tracks:
- Per-image and per-unit latency percentiles (mean, min, max, p50, p95, p99)
- Real-time and windowed throughput (units/sec, units/min, images/min)
- Overall and per-tenant verdicts (PASS, FAIL, UNCERTAIN) and UNCERTAIN rate
- Pipeline errors and failure rate
- Active concurrent inspection units
- Storage footprint (bytes, image count, MB)
- Actual unit compute economics vs Amazon SLA economic targets ($0.075/unit ceiling)
"""

import time
import threading
from typing import Dict, Any, List, Optional
import numpy as np

class ProductionMetricsTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self.start_time = time.time()
        
        # Counters
        self.total_units_inspected = 0
        self.total_images_processed = 0
        self.active_concurrent_units = 0
        self.total_errors = 0
        
        # Verdict distributions
        self.verdict_counts = {
            "PASS": 0,
            "FAIL": 0,
            "UNCERTAIN": 0
        }
        
        # Tenancy breakdown
        self.tenant_counts: Dict[str, int] = {}
        
        # Latency histories (in milliseconds)
        self.unit_latencies: List[float] = []
        self.view_latencies: Dict[str, List[float]] = {
            "front": [],
            "back": [],
            "label": []
        }
        
        # Economic telemetry
        self.total_compute_cost_usd = 0.0
        self.cost_per_inference_usd = 0.00012  # Hardware accelerated DirectML GPU cost
        self.target_max_cost_usd = 0.075       # SLA threshold
        
        # Recent errors log (capped at 50)
        self.recent_errors: List[Dict[str, Any]] = []

    def record_start(self):
        with self._lock:
            self.active_concurrent_units += 1

    def record_finish(
        self,
        unit_id: str,
        org_id: str,
        verdict: str,
        total_latency_ms: float,
        view_latencies: Optional[Dict[str, float]] = None,
        cost_usd: Optional[float] = None
    ):
        with self._lock:
            if self.active_concurrent_units > 0:
                self.active_concurrent_units -= 1
            
            self.total_units_inspected += 1
            self.total_images_processed += 3  # front, back, label
            
            if verdict in self.verdict_counts:
                self.verdict_counts[verdict] += 1
            else:
                self.verdict_counts["UNCERTAIN"] += 1
                
            self.tenant_counts[org_id] = self.tenant_counts.get(org_id, 0) + 1
            
            self.unit_latencies.append(total_latency_ms)
            # Keep history bounded
            if len(self.unit_latencies) > 2000:
                self.unit_latencies = self.unit_latencies[-1000:]
                
            if view_latencies:
                for view, lat in view_latencies.items():
                    if view in self.view_latencies:
                        self.view_latencies[view].append(lat)
                        if len(self.view_latencies[view]) > 2000:
                            self.view_latencies[view] = self.view_latencies[view][-1000:]
                            
            actual_cost = cost_usd if cost_usd is not None else self.cost_per_inference_usd
            self.total_compute_cost_usd += actual_cost

    def record_error(self, unit_id: str, org_id: str, error_msg: str):
        with self._lock:
            if self.active_concurrent_units > 0:
                self.active_concurrent_units -= 1
            self.total_errors += 1
            self.recent_errors.append({
                "unit_id": unit_id,
                "org_id": org_id,
                "error": str(error_msg),
                "timestamp": time.time()
            })
            if len(self.recent_errors) > 50:
                self.recent_errors.pop(0)

    def _calculate_percentiles(self, values: List[float]) -> Dict[str, float]:
        if not values:
            return {"mean": 0.0, "min": 0.0, "max": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}
        arr = np.array(values)
        return {
            "mean": round(float(np.mean(arr)), 2),
            "min": round(float(np.min(arr)), 2),
            "max": round(float(np.max(arr)), 2),
            "p50": round(float(np.percentile(arr, 50)), 2),
            "p95": round(float(np.percentile(arr, 95)), 2),
            "p99": round(float(np.percentile(arr, 99)), 2)
        }

    def get_summary(self, storage_provider=None, db_provider=None) -> Dict[str, Any]:
        with self._lock:
            uptime_seconds = max(1.0, time.time() - self.start_time)
            units = self.total_units_inspected
            uncertain_count = self.verdict_counts["UNCERTAIN"]
            uncertain_rate = round((uncertain_count / max(1, units)) * 100.0, 2)
            error_rate = round((self.total_errors / max(1, units + self.total_errors)) * 100.0, 2)
            
            units_per_sec = round(units / uptime_seconds, 4)
            units_per_min = round(units_per_sec * 60.0, 2)
            images_per_min = round(units_per_min * 3, 2)
            
            unit_stats = self._calculate_percentiles(self.unit_latencies)
            view_stats = {
                view: self._calculate_percentiles(lats)
                for view, lats in self.view_latencies.items()
            }
            
            avg_cost_unit = (
                round(self.total_compute_cost_usd / units, 6)
                if units > 0 else self.cost_per_inference_usd
            )
            
            # Storage usage calculation
            storage_stats = {"total_bytes": 0, "total_images": 0, "size_mb": 0.0}
            if storage_provider and hasattr(storage_provider, "get_storage_stats"):
                try:
                    storage_stats = storage_provider.get_storage_stats()
                except Exception:
                    pass

            return {
                "uptime_seconds": round(uptime_seconds, 1),
                "throughput": {
                    "total_units_inspected": units,
                    "total_images_processed": self.total_images_processed,
                    "active_concurrent_units": self.active_concurrent_units,
                    "units_per_second": units_per_sec,
                    "units_per_minute": units_per_min,
                    "images_per_minute": images_per_min
                },
                "verdicts": {
                    "distribution": self.verdict_counts,
                    "uncertain_rate_percent": uncertain_rate,
                    "tenants": self.tenant_counts
                },
                "latencies_ms": {
                    "per_unit": unit_stats,
                    "per_view": view_stats
                },
                "errors": {
                    "total_errors": self.total_errors,
                    "error_rate_percent": error_rate,
                    "recent_errors": self.recent_errors[-10:]
                },
                "storage_usage": storage_stats,
                "economics": {
                    "total_compute_cost_usd": round(self.total_compute_cost_usd, 5),
                    "actual_cost_per_unit_usd": avg_cost_unit,
                    "target_max_check_cost_usd": self.target_max_cost_usd,
                    "cost_within_economics": avg_cost_unit <= self.target_max_cost_usd,
                    "cost_margin_percent": round(((self.target_max_cost_usd - avg_cost_unit) / self.target_max_cost_usd) * 100.0, 1),
                    "fba_defect_fee_avoidance_usd": round(self.verdict_counts["FAIL"] * 0.45, 2)
                }
            }

# Singleton instance
metrics_tracker = ProductionMetricsTracker()
