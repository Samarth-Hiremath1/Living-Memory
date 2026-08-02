# syntax=docker/dockerfile:1
#
# Living Memory backend — FastAPI + LangGraph + MCP server.
#
# Layer ordering matters: dependency metadata is copied and installed BEFORE
# application source. Docker caches each layer keyed on the files that went
# into it, so editing a .py file invalidates only the final COPY — the pip
# install layer is reused. Copying source first would reinstall every
# dependency on every code change.

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# curl is needed by the container HEALTHCHECK below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# ── Dependency layer ─────────────────────────────────────────────────────────
# Only the dependency manifest is copied here, so this layer rebuilds ONLY when
# dependencies change — not when application code changes.
#
# requirements.txt is generated from pyproject.toml (see `make deps`) rather
# than hand-maintained, so the two cannot drift. Version constraints — notably
# the mcp<2.0 pin — are therefore identical in local dev and in the image.
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Source layer ─────────────────────────────────────────────────────────────
# Changes here do not invalidate the dependency layer above.
COPY src/ ./src/
COPY eval/ ./eval/

# Seed data lives one level up in the repo; compose mounts or copies it to /data.
ENV GRAPH_STORE_PATH=/data/graph_store.json

# Run as a non-root user.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000

# Container-level health check. Kubernetes uses its own probes (see k8s/),
# but this makes `docker compose ps` and plain `docker run` useful too.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health/live || exit 1

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
