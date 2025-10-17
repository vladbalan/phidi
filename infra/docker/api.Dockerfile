FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (curl for health checks, make for benchmark workflows, nodejs for node crawler)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    make \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Copy and install API dependencies
COPY src/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and build files
COPY src/ ./src/
COPY configs/ ./configs/
COPY scripts/ ./scripts/
COPY Makefile ./Makefile
COPY data/inputs/ ./data/inputs/

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1

# Run API with uvicorn
CMD ["uvicorn", "src.api.app:get_uvicorn_app", "--host", "0.0.0.0", "--port", "8000"]