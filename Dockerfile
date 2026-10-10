# Multi-stage lightweight production Dockerfile for CUBE Prep Manager
FROM python:3.11-slim as base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install minimal system dependencies for headless OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install core python dependencies (optimized for <200MB RAM runtime)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source, models, and reference data
COPY agent/ ./agent/
COPY models/ ./models/
COPY cube_prep_dataset/ ./cube_prep_dataset/
COPY data/ ./data/
COPY reports/ ./reports/
COPY submissions/ ./submissions/
COPY app.py ./app.py

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Start FastAPI production server with Uvicorn (adapts dynamically to cloud $PORT, default 8000)
CMD ["sh", "-c", "uvicorn agent.api:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
