"""
Packaging Dataset Provider for CUBE Prep Manager.
Supports:
1. New Packaging Dataset (manifest.csv, compliance_scenarios, inspection_reference, inspection_examples, packaged_products)
2. Retained cube_prep_dataset legacy units for backward compatibility.
"""

import os
import cv2
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from agent.config import settings

class PackagingDatasetManager:
    def __init__(self):
        self.dataset_root = self._resolve_dataset_root()
        self.manifest_df = self._load_manifest()
        self.units: Dict[str, Dict[str, Any]] = {}
        self._build_units_index()

    def _resolve_dataset_root(self) -> str:
        candidates = [
            settings.PACKAGING_DATASET_PATH,
            r"C:\Dhanvi\HACKATHONS\CUBE_2026_dataset\packaging_dataset",
            "data/packaging_dataset",
            os.path.abspath("data/packaging_dataset"),
        ]
        for c in candidates:
            if c and os.path.exists(c) and os.path.exists(os.path.join(c, "manifest.csv")):
                return c
        return "data/packaging_dataset"

    def _load_manifest(self) -> pd.DataFrame:
        manifest_path = os.path.join(self.dataset_root, "manifest.csv")
        if os.path.exists(manifest_path):
            try:
                return pd.read_csv(manifest_path)
            except Exception as e:
                print(f"[PackagingDatasetManager] Failed to read manifest: {e}")
        return pd.DataFrame()

    def _build_units_index(self):
        """Index units from packaging dataset manifest."""
        self.units.clear()

        # 1. Index from compliance_scenarios (9 core FBA compliance scenarios)
        scenario_metadata = {
            "ideal_case": {
                "sku": "SKU-IDEAL-100", "fnsku": "X001254567", "asin": "B08IDEAL01",
                "wo_polybag": True, "wo_suffocation_warning": True, "wo_expiry_date": False, "wo_handling_marks": "",
                "description": "Compliant FBA package with proper polybag seal, suffocation warning, flat FNSKU, and covered barcode."
            },
            "no_polybag": {
                "sku": "SKU-NOPOLY-200", "fnsku": "X002345678", "asin": "B08NOPOLY2",
                "wo_polybag": True, "wo_suffocation_warning": True, "wo_expiry_date": False, "wo_handling_marks": "",
                "description": "Defect scenario: Polybag missing entirely on an apparel/plush unit requiring polybagging."
            },
            "polybag_open_loose_seal": {
                "sku": "SKU-OPENSL-300", "fnsku": "X003456789", "asin": "B08OPENSL3",
                "wo_polybag": True, "wo_suffocation_warning": True, "wo_expiry_date": False, "wo_handling_marks": "",
                "description": "Defect scenario: Polybag present but open, loose, or heat seal failed."
            },
            "missing_warning_label": {
                "sku": "SKU-NOWARN-400", "fnsku": "X004567890", "asin": "B08NOWARN4",
                "wo_polybag": True, "wo_suffocation_warning": True, "wo_expiry_date": False, "wo_handling_marks": "",
                "description": "Defect scenario: Polybag present with >=5 inch opening but missing mandatory suffocation warning."
            },
            "warning_label_obscured": {
                "sku": "SKU-OBSWRN-500", "fnsku": "X005678901", "asin": "B08OBSWRN5",
                "wo_polybag": True, "wo_suffocation_warning": True, "wo_expiry_date": False, "wo_handling_marks": "",
                "description": "Defect scenario: Suffocation warning label obscured, folded, or covered."
            },
            "fnsku_on_flat_surface": {
                "sku": "SKU-FLATFN-600", "fnsku": "X006789012", "asin": "B08FLATFN6",
                "wo_polybag": True, "wo_suffocation_warning": True, "wo_expiry_date": False, "wo_handling_marks": "",
                "description": "Compliant scenario: FNSKU label affixed to flat planar surface with >0.25 inch edge margin."
            },
            "fnsku_on_seam_curve": {
                "sku": "SKU-SEAMFN-700", "fnsku": "X007890123", "asin": "B08SEAMFN7",
                "wo_polybag": True, "wo_suffocation_warning": True, "wo_expiry_date": False, "wo_handling_marks": "",
                "description": "Defect scenario: FNSKU label placed across package seam, curved edge, or heat-seal."
            },
            "original_barcode_not_covered": {
                "sku": "SKU-UNCOVBC-800", "fnsku": "X008901234", "asin": "B08UNCOVB8",
                "wo_polybag": True, "wo_suffocation_warning": True, "wo_expiry_date": False, "wo_handling_marks": "",
                "description": "Defect scenario: Original manufacturer UPC/EAN barcode exposed, creating scanning conflict."
            },
            "expiry_date_illegible_missing": {
                "sku": "SKU-BADEXP-900", "fnsku": "X009012345", "asin": "B08BADEXP9",
                "wo_polybag": False, "wo_suffocation_warning": False, "wo_expiry_date": True, "wo_handling_marks": "",
                "description": "Defect scenario: Expiry date required for consumable/topical but missing or illegible."
            }
        }

        if not self.manifest_df.empty:
            for grid_name in ["compliance_scenarios", "inspection_examples", "inspection_reference", "packaged_products"]:
                grid_sub = self.manifest_df[self.manifest_df["grid"] == grid_name]
                rows = grid_sub["row_label"].unique()
                for r_idx, r_label in enumerate(rows, 1):
                    unit_code = f"UNIT-{grid_name[:3].upper()}-{r_idx:02d}"
                    row_items = grid_sub[grid_sub["row_label"] == r_label]

                    # Map columns
                    img_map = {}
                    for _, item in row_items.iterrows():
                        col_lbl = item["column_label"]
                        rel_img = item["image"]
                        # Fix relative path: strip packaging_dataset/ prefix if dataset_root already points there
                        clean_rel = rel_img
                        if clean_rel.startswith("packaging_dataset/"):
                            clean_rel = clean_rel[len("packaging_dataset/"):]
                        full_img_p = os.path.join(self.dataset_root, clean_rel)
                        if not os.path.exists(full_img_p):
                            # Try alternative
                            full_img_p = os.path.join("data/packaging_dataset", clean_rel)
                        img_map[col_lbl] = full_img_p

                    # Determine 3 views: front, back, label
                    front_p = img_map.get("view_front") or img_map.get("product_01") or img_map.get("polybag_presence_seal") or list(img_map.values())[0]
                    back_p = img_map.get("view_back") or img_map.get("product_02") or img_map.get("suffocation_warning") or list(img_map.values())[min(1, len(img_map)-1)]
                    label_p = img_map.get("view_label_closeup") or img_map.get("fnsku_placement") or list(img_map.values())[min(2, len(img_map)-1)]

                    meta = scenario_metadata.get(r_label, {
                        "sku": f"SKU-{r_label.upper()[:10]}",
                        "fnsku": f"X00{r_idx:06d}",
                        "asin": f"B08{r_label[:6].upper()}",
                        "wo_polybag": True,
                        "wo_suffocation_warning": True,
                        "wo_expiry_date": False,
                        "wo_handling_marks": "",
                        "description": f"Packaging inspection unit for {r_label.replace('_', ' ')}."
                    })

                    self.units[unit_code] = {
                        "unit_id": unit_code,
                        "org_id": "org_demo_alpha" if r_idx % 2 != 0 else "org_demo_bravo",
                        "grid": grid_name,
                        "scenario": r_label,
                        "sku": meta["sku"],
                        "fnsku": meta["fnsku"],
                        "asin": meta["asin"],
                        "work_order_id": f"WO-{3000 + r_idx}",
                        "fba_shipment_id": f"FBA-CUBE-{100 + r_idx}",
                        "prep_price_usd": 0.75,
                        "wo_polybag": meta["wo_polybag"],
                        "wo_suffocation_warning": meta["wo_suffocation_warning"],
                        "wo_expiry_date": meta["wo_expiry_date"],
                        "wo_handling_marks": meta["wo_handling_marks"],
                        "description": meta["description"],
                        "front_image_path": front_p,
                        "back_image_path": back_p,
                        "label_image_path": label_p,
                        "all_images": img_map
                    }

        # 2. Add legacy cube_prep_dataset units if available for full backwards-compatibility
        legacy_csv = "data/compliance_records.csv"
        if not os.path.exists(legacy_csv):
            legacy_csv = "cube_prep_dataset/cube_prep_dataset.csv"
        if os.path.exists(legacy_csv):
            try:
                ldf = pd.read_csv(legacy_csv)
                for _, row in ldf.iterrows():
                    uid = row["unit_id"]
                    if uid not in self.units:
                        self.units[uid] = {
                            "unit_id": uid,
                            "org_id": str(row.get("org_id", "org_demo_alpha")),
                            "grid": "legacy_cube_prep",
                            "scenario": str(row.get("defect_type", "standard_prep")),
                            "sku": str(row.get("sku", f"SKU-{uid}")),
                            "fnsku": str(row.get("fnsku", f"X00{uid}")),
                            "asin": str(row.get("asin", f"B00{uid}")),
                            "work_order_id": str(row.get("work_order_id", "WO-3000")),
                            "fba_shipment_id": str(row.get("fba_shipment_id", "FBA-CUBE-100")),
                            "prep_price_usd": float(row.get("prep_price_usd", 0.75)),
                            "wo_polybag": bool(row.get("wo_polybag", True)),
                            "wo_suffocation_warning": bool(row.get("wo_suffocation_warning", True)),
                            "wo_expiry_date": bool(row.get("wo_expiry_date", False)),
                            "wo_handling_marks": str(row.get("wo_handling_marks", "")),
                            "description": f"Standard inbound unit {uid}",
                            "front_image_path": f"cube_prep_dataset/images/{uid}_front.jpg",
                            "back_image_path": f"cube_prep_dataset/images/{uid}_back.jpg",
                            "label_image_path": f"cube_prep_dataset/images/{uid}_label.jpg",
                            "all_images": {}
                        }
            except Exception as e:
                print(f"[PackagingDatasetManager] Failed indexing legacy dataset: {e}")

    def list_units(self, org_id: Optional[str] = None, grid: Optional[str] = None) -> List[Dict[str, Any]]:
        results = list(self.units.values())
        if org_id:
            results = [u for u in results if u["org_id"] == org_id]
        if grid:
            results = [u for u in results if u["grid"] == grid]
        return results

    def get_unit(self, unit_id: str) -> Optional[Dict[str, Any]]:
        return self.units.get(unit_id)

    def load_unit_images(self, unit_id: str) -> Tuple[Optional[Any], Optional[Any], Optional[Any]]:
        unit = self.get_unit(unit_id)
        if not unit:
            return None, None, None
        front = cv2.imread(unit["front_image_path"]) if os.path.exists(unit["front_image_path"]) else None
        back = cv2.imread(unit["back_image_path"]) if os.path.exists(unit["back_image_path"]) else None
        label = cv2.imread(unit["label_image_path"]) if os.path.exists(unit["label_image_path"]) else None
        return front, back, label

dataset_manager = PackagingDatasetManager()
