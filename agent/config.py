"""
Configuration settings for CUBE Prep Manager.
Supports local development, CI testing, and production deployment on cloud platforms
(Render, Fly.io, Railway, Supabase, Vercel).
"""

import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Environment & Server
    ENV: str = Field(default="development", description="Environment: development, staging, production")
    DEBUG: bool = Field(default=False, description="Debug mode")
    HOST: str = Field(default="0.0.0.0", description="Host to bind server")
    PORT: int = Field(default=8000, description="Port to listen on")
    
    # CORS Configuration
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8501", "https://*.vercel.app"],
        description="Allowed CORS origins"
    )
    
    # Storage Backend: 'local' or 'supabase'
    STORAGE_BACKEND: str = Field(default="local", description="Storage backend: local or supabase")
    LOCAL_STORAGE_DIR: str = Field(default="data/uploads", description="Directory for local image uploads")
    
    # Database Backend: 'local' or 'supabase'
    DATABASE_BACKEND: str = Field(default="local", description="Database backend: local or supabase")
    
    # Supabase Configuration (Optional for cloud production)
    SUPABASE_URL: str = Field(default="", description="Supabase Project URL")
    SUPABASE_ANON_KEY: str = Field(default="", description="Supabase Anon/Public Key")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(default="", description="Supabase Service Role Key for server-side operations")
    SUPABASE_STORAGE_BUCKET: str = Field(default="prep-evidence-images", description="Storage bucket name")
    
    # Model & Inference
    ONNX_MODEL_PATH: str = Field(default="models/best_detector.onnx", description="Path to slimmed ONNX detector")
    FALLBACK_MODEL_PATH: str = Field(default="yolov8n.pt", description="Fallback PyTorch weights")
    INFERENCE_IMGSZ: int = Field(default=640, description="Input image size for detector")
    
    # Quality & Calibration Thresholds
    BLUR_THRESHOLD: float = Field(default=25.0, description="Minimum Laplacian variance for calibration")
    MAX_GLARE_RATIO: float = Field(default=0.35, description="Maximum saturated glare pixel ratio")
    
    # Multi-Tenancy & Security
    DEFAULT_ORG_ID: str = Field(default="org_demo_alpha", description="Default tenant org_id for demo")
    API_KEY_HEADER: str = Field(default="X-API-Key", description="Header for API Key authentication")
    TENANT_HEADER: str = Field(default="X-Org-ID", description="Header for multi-tenant isolation")
    REQUIRE_AUTH: bool = Field(default=False, description="Whether to enforce API key in production")
    SERVER_API_KEY: str = Field(default="", description="Server API key secret")
    
    # Gemini AI Agent Configuration
    GEMINI_API_KEY: str = Field(default="", description="Gemini API Key")
    GEMINI_MODEL: str = Field(default="gemini-3.6-flash", description="Gemini Model Identifier")
    
    # Packaging Dataset Path
    PACKAGING_DATASET_PATH: str = Field(
        default="data/packaging_dataset",
        description="Path to new packaging dataset directory"
    )

    # Economic Targets
    TARGET_MAX_CHECK_COST_USD: float = Field(default=0.075, description="Maximum allowable check cost")
    
    # Resiliency & Concurrency Controls
    INSPECTION_TIMEOUT_SECONDS: float = Field(default=25.0, description="Max execution timeout per unit inspection")
    MAX_CONCURRENT_INSPECTIONS: int = Field(default=10, description="Max concurrent active unit inspections")

    @property
    def clean_gemini_api_key(self) -> str:
        """Returns Gemini API key stripped of any punctuation or trailing whitespace."""
        return self.GEMINI_API_KEY.strip(". \t\r\n")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
