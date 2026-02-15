# ── MCP EDA Server — Production Dockerfile ───────────────────────────────────
# Builds a self-contained image for Archestra K8s self-hosted deployment.
#
# Build:  docker build -t chip-mcp-server .
# Run:    docker run -e MCP_TRANSPORT=stdio chip-mcp-server

FROM python:3.12-slim

LABEL maintainer="archestra-eda"
LABEL description="MCP EDA Server — Chip Design Agent (Yosys, OpenROAD, OpenLane)"

# System deps (Docker CLI needed for EDA tool containers)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server.py .
COPY app/ ./app/

# Create workspace directory
RUN mkdir -p /app/workspace

# Default environment (non-secret only — secrets injected at runtime by K8s)
ENV MCP_TRANSPORT=stdio
ENV PORT=3334
ENV LOG_LEVEL=INFO

# Entry point
CMD ["python", "server.py"]
