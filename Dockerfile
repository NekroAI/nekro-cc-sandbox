# syntax=docker/dockerfile:1

# ============================================
# nekro-cc-sandbox: Claude Code Workspace Agent
# ============================================

# ============================================
# Build stage - Frontend
# ============================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend
ENV CI=true

# Copy frontend dependency manifests (for better layer caching)
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && corepack prepare pnpm@latest --activate

COPY frontend/ ./
RUN pnpm install --frozen-lockfile && pnpm run build

# ============================================
# Build stage - Dependencies
# ============================================
FROM ghcr.io/astral-sh/uv:0.5 AS uv-bin

FROM python:3.13-slim AS deps-builder

WORKDIR /app

# Install uv (binary only)
COPY --from=uv-bin /uv /usr/local/bin/uv
ENV UV_SYSTEM_PYTHON=1
ENV UV_LINK_MODE=copy

# Copy dependency manifests and install dependencies (frozen by lockfile)
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen --no-install-project

# Copy source and install with dev dependencies
COPY src/ ./src/
RUN uv sync --no-dev --frozen

# ============================================
# Runtime stage
# ============================================
FROM python:3.13-slim AS runtime

# Install uv
COPY --from=uv-bin /uv /usr/local/bin/uv
ENV UV_SYSTEM_PYTHON=1
ENV UV_LINK_MODE=copy

# Install Claude Code and system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    unzip \
    util-linux \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code
RUN curl -fsSL https://claude.ai/install.sh | bash

# Make claude available on PATH for all users
RUN if [ -x /root/.local/bin/claude ]; then cp /root/.local/bin/claude /usr/local/bin/claude; fi

# Create non-root user
RUN useradd -m -s /bin/bash appuser

# Set working directory
WORKDIR /home/appuser

# Copy Python source
COPY --chown=appuser:appuser pyproject.toml uv.lock ./
COPY --chown=appuser:appuser src/ ./src/

# Install Python dependencies
RUN uv sync --no-dev --frozen

# Copy built frontend
COPY --from=frontend-builder --chown=appuser:appuser /app/frontend/dist ./frontend/dist

# Create workspace directory
RUN mkdir -p /home/appuser/workspaces && chown -R appuser:appuser /home/appuser

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Environment variables
ENV PYTHONPATH=/home/appuser
ENV HOST=0.0.0.0
ENV PORT=7021
ENV WORKSPACE_ROOT=/home/appuser/workspaces
ENV SKIP_PERMISSIONS=false
ENV DEBUG=false

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7021/health')" || exit 1

# Expose port
EXPOSE 7021

# Entrypoint
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
