# ============================================================================
# Stage 1: Build frontend
# ============================================================================
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build

# ============================================================================
# Stage 2: Python runtime
# ============================================================================
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="AStockPursue" \
      org.opencontainers.image.description="AI-powered quantitative trading research platform" \
      org.opencontainers.image.version="2026.5.24" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.url="https://github.com/SZWzz/AStockPursue"

WORKDIR /app

# System deps (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps (install before copying code for layer caching)
COPY agent/requirements.txt agent/requirements.txt
RUN pip install --no-cache-dir -r agent/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# Copy project
COPY pyproject.toml LICENSE NOTICE SECURITY.md README.md README_EN.md ./
COPY agent/ agent/

# Copy built frontend
COPY --from=frontend-build /app/frontend/dist frontend/dist

# Create service user + writable directories before pip install
# so .egg-info / __pycache__ are owned by the research user
RUN useradd --create-home --shell /usr/sbin/nologin research \
    && mkdir -p agent/runs agent/sessions agent/uploads agent/.swarm/runs \
              /home/research/.AStockPursue/skills \
    && chown -R research:research /app /home/research/.AStockPursue
USER research

# Install CLI entrypoint
RUN pip install --no-cache-dir -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# Default ports: API (8899) + MCP Server SSE (8900)
EXPOSE 8899 8900

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8899/health')" || exit 1

# Run API server (serves frontend/dist as static files)
CMD ["AStockPursue", "serve", "--host", "0.0.0.0", "--port", "8899"]
