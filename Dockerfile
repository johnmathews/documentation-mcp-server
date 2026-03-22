FROM python:3.13-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ src/

RUN uv sync --frozen --no-dev --no-editable

# Pre-download the embedding model so first startup doesn't block on a 420MB download
RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-mpnet-base-v2')"

RUN useradd -r -u 1000 -m docserver && \
    mkdir -p /data /config && \
    chown -R docserver:docserver /data /config /app

USER docserver

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -sf http://localhost:8080/health || exit 1

CMD ["uv", "run", "python", "-m", "docserver"]
