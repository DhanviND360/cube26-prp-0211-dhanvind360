"""
Storage Abstraction Layer for CUBE Prep Manager.
Provides cloud-agnostic storage for photographic evidence.
Supports:
- Local Storage (default for development, offline execution, and tests)
- Supabase Storage (S3-compatible managed cloud object storage)
Ensures strict multi-tenant path partitioning by org_id (Rule 1).
"""

import os
import io
import cv2
import numpy as np
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from agent.config import settings

class BaseStorageProvider(ABC):
    @abstractmethod
    def save_image(self, unit_id: str, view: str, image_data: bytes, org_id: str) -> str:
        """Saves image bytes and returns a URI / path reference."""
        pass

    @abstractmethod
    def get_image(self, image_ref: str, org_id: str) -> Optional[np.ndarray]:
        """Loads and returns an OpenCV image matrix from a URI/path, enforcing tenant isolation."""
        pass

    @abstractmethod
    def get_storage_stats(self, org_id: Optional[str] = None) -> dict:
        """Returns storage metrics: total bytes, image count, and formatted size."""
        pass

class LocalStorageProvider(BaseStorageProvider):
    def __init__(self, base_dir: str = "data/uploads"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def save_image(self, unit_id: str, view: str, image_data: bytes, org_id: str) -> str:
        tenant_dir = os.path.join(self.base_dir, org_id)
        os.makedirs(tenant_dir, exist_ok=True)
        filename = f"{unit_id}_{view}.jpg"
        full_path = os.path.join(tenant_dir, filename)
        with open(full_path, "wb") as f:
            f.write(image_data)
        # Return standardized relative URI
        return f"{self.base_dir}/{org_id}/{filename}".replace("\\", "/")

    def get_image(self, image_ref: str, org_id: str) -> Optional[np.ndarray]:
        # Enforce tenancy: path MUST belong to requesting org_id or base fixture directory
        normalized = image_ref.replace("\\", "/")
        
        # Check if loading from primary dataset fixtures
        if "cube_prep_dataset" in normalized or "packaging_dataset" in normalized or "data/packaging_dataset" in normalized:
            if os.path.exists(normalized):
                return cv2.imread(normalized)
            # Try prepending repo root if needed
            for prefix in ["cube_prep_dataset", "data/packaging_dataset", "packaging_dataset"]:
                alt = os.path.join(prefix, normalized)
                if os.path.exists(alt):
                    return cv2.imread(alt)
            if os.path.exists(image_ref):
                return cv2.imread(image_ref)

        # Tenant isolation check on uploaded assets
        if f"/{org_id}/" not in normalized and not normalized.startswith(f"{self.base_dir}/{org_id}/"):
            # Block cross-tenant file read
            return None

        if os.path.exists(normalized):
            return cv2.imread(normalized)
        return None

    def get_storage_stats(self, org_id: Optional[str] = None) -> dict:
        target_dir = os.path.join(self.base_dir, org_id) if org_id else self.base_dir
        total_bytes = 0
        file_count = 0
        if os.path.exists(target_dir):
            for root, _, files in os.walk(target_dir):
                for f in files:
                    fp = os.path.join(root, f)
                    if os.path.isfile(fp):
                        total_bytes += os.path.getsize(fp)
                        file_count += 1
        return {
            "total_bytes": total_bytes,
            "total_images": file_count,
            "size_mb": round(total_bytes / (1024 * 1024), 3)
        }

class SupabaseStorageProvider(BaseStorageProvider):
    def __init__(self, supabase_url: str, supabase_key: str, bucket_name: str = "prep-evidence-images"):
        self.bucket_name = bucket_name
        self.fallback = LocalStorageProvider()
        self.client = None
        if supabase_url and supabase_key:
            try:
                from supabase import create_client
                self.client = create_client(supabase_url, supabase_key)
            except Exception as e:
                print(f"[SupabaseStorageProvider] Warning: Supabase client init failed ({e}), falling back to local")

    def save_image(self, unit_id: str, view: str, image_data: bytes, org_id: str) -> str:
        if self.client is None:
            return self.fallback.save_image(unit_id, view, image_data, org_id)
            
        file_path = f"{org_id}/{unit_id}_{view}.jpg"
        try:
            self.client.storage.from_(self.bucket_name).upload(
                path=file_path,
                file=image_data,
                file_options={"content-type": "image/jpeg", "upsert": "true"}
            )
            # Get public or signed URL
            url = self.client.storage.from_(self.bucket_name).get_public_url(file_path)
            return url
        except Exception as e:
            print(f"[SupabaseStorageProvider] Upload failed: {e}. Falling back to local.")
            return self.fallback.save_image(unit_id, view, image_data, org_id)

    def get_image(self, image_ref: str, org_id: str) -> Optional[np.ndarray]:
        # If local reference or fixture, resolve via fallback
        if not image_ref.startswith("http"):
            return self.fallback.get_image(image_ref, org_id)
            
        # Security check: URL must contain org_id partition
        if f"/{org_id}/" not in image_ref:
            return None
            
        try:
            import httpx
            resp = httpx.get(image_ref, timeout=10.0)
            if resp.status_code == 200:
                img_arr = np.asarray(bytearray(resp.content), dtype=np.uint8)
                return cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
        except Exception as e:
            print(f"[SupabaseStorageProvider] Download error: {e}")
        return None

    def get_storage_stats(self, org_id: Optional[str] = None) -> dict:
        if self.client is None:
            return self.fallback.get_storage_stats(org_id)
        try:
            folder = org_id if org_id else ""
            res = self.client.storage.from_(self.bucket_name).list(folder)
            total_bytes = sum(item.get("metadata", {}).get("size", 0) for item in res if isinstance(item, dict))
            return {
                "total_bytes": total_bytes,
                "total_images": len(res),
                "size_mb": round(total_bytes / (1024 * 1024), 3)
            }
        except Exception:
            return self.fallback.get_storage_stats(org_id)

def get_storage_provider() -> BaseStorageProvider:
    """Factory creating configured storage provider without vendor lock-in."""
    if settings.STORAGE_BACKEND.lower() == "supabase" and settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        return SupabaseStorageProvider(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_SERVICE_ROLE_KEY,
            bucket_name=settings.SUPABASE_STORAGE_BUCKET
        )
    return LocalStorageProvider(base_dir=settings.LOCAL_STORAGE_DIR)
