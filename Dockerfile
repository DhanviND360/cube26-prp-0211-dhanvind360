# Multi-stage lightweight production Dockerfile for CUBE Prep Manager
FROM python:3.11-slim as base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install system dependencies for OpenCV and PyZBar
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libzbar0 \
    tesseract-ocr \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install core python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source, models, and reference data
COPY agent/ ./agent/
COPY models/best_detector.onnx ./models/best_detector.onnx
COPY cube_prep_dataset/ ./cube_prep_dataset/
COPY data/ ./data/
COPY reports/ ./reports/

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start FastAPI production server with Uvicorn
CMD ["uvicorn", "agent.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
