# syntax=docker/dockerfile:1.9
# Multi-stage build for deterministic OneLake migrator runtime
ARG PYTHON_VERSION=3.11-slim
FROM python:${PYTHON_VERSION} AS base

LABEL org.opencontainers.image.title="onelake-migrator" \
      org.opencontainers.image.description="Containerized SharePoint -> OneLake migration tooling" \
      org.opencontainers.image.source="https://github.com/Bralabee/onelake-migration-case-study" \
      org.opencontainers.image.licenses="MIT"

# Set UTF-8 & no bytecode
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# System deps (minimal; add azure cli/azcopy later if needed)
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    curl ca-certificates tzdata bash \
  && rm -rf /var/lib/apt/lists/*

# Install dependencies separately for caching
COPY requirements.txt ./
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# Copy source (exclude large data via .dockerignore)
COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
COPY scripts ./scripts

# Non-root runtime
RUN useradd -u 1001 -m appuser
USER appuser

# Default mount points (runtime):
#   /data  -> bind for data/ (progress, caches)
#   /logs  -> bind for logs/
VOLUME ["/data","/logs"]

# Healthcheck (lightweight import)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import fabric.migration.production as m; print('ok')" || exit 1

# Default entry prints help
ENTRYPOINT ["python","-m","fabric.migration.production"]
CMD ["--help"]
