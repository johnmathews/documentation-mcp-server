# 260322 - Initial MVP Build

## What Was Built

Complete working MVP of the Documentation MCP Server: a Python 3.13 service that indexes markdown documentation from git repos and serves it to AI agents via MCP.

### Components

- **Config** (`config.py`): YAML-based source configuration with env var overrides
- **Ingestion** (`ingestion.py`): Git repo syncing (local + remote), markdown parsing, section-aware chunking with overlap, APScheduler-based polling
- **Knowledge Base** (`knowledge_base.py`): SQLite for structured metadata, ChromaDB for vector search using all-mpnet-base-v2 embeddings (768 dims)
- **MCP Server** (`server.py`): FastMCP with 5 tools (search_docs, query_docs, get_document, list_sources, reindex), `/health` endpoint, structured JSON logging
- **Logging** (`logging_config.py`): JSON-formatted structured logging for Docker, with configurable format and level
- **Docker**: Single container with docker-compose, persistent volumes, embedding model pre-downloaded in build, curl-based healthcheck
- **Dependency management**: uv with lockfile

### Test Suite

50 tests covering config loading, env var overrides, section parsing, chunking (overlap, lists, code fences, section context), markdown parsing, knowledge base CRUD, semantic search, source filtering, all 5 MCP tools, and structured logging. 71% code coverage.

## Key Decisions

- **Dual store (SQLite + ChromaDB)** rather than ChromaDB alone, because the user needs both semantic search ("does service X talk to Y") and structured queries ("when was doc X created"). ChromaDB metadata filtering is limited compared to SQL.

- **Section-aware chunking at ~400 chars** rather than naive paragraph splitting. Documentation is terse and functional — smaller chunks give more precise embeddings. Each chunk is prefixed with its heading hierarchy (e.g. `[Setup > Networking > Ports]`) so it's self-describing in isolation. ~100 chars of overlap between consecutive chunks preserves context across boundaries. Lists and code fences are kept intact as single blocks.

- **all-mpnet-base-v2 embedding model** (109M params, 768 dims, ~500MB RAM) rather than ChromaDB's default all-MiniLM-L6-v2 (22M params, 384 dims). Significantly better semantic similarity for short technical statements. Pre-downloaded in Docker build to avoid 420MB download on first startup.

- **Parent doc + chunk separation**: Parent docs (is_chunk=False) are SQLite-only metadata records. Chunks (is_chunk=True) go into both stores. This means `query_documents()` returns whole files while `search()` returns relevant text fragments.

- **Streamable HTTP transport** rather than stdio, since this runs as a network service in Docker that nanoclaw connects to remotely. MCP endpoint at `/mcp`, health check at `/health`.

- **Lazy initialization** in server.py — KB and ingester are created by `init_app()` rather than at import time, making the module testable with injected config.

- **Structured JSON logging** to stdout so Docker log drivers can parse it. Each line is a JSON object with timestamp, level, logger, message, and optional structured fields (event, duration_ms, stats).

- **uv** for dependency and environment management with a committed lockfile for reproducible builds.

## Bugs Caught During Build

1. The ingestion module initially used `is_index: True/False` in metadata instead of `is_chunk: True/False`. Since the knowledge base reads `metadata.get("is_chunk", False)`, this would have caused all records to be treated as parent docs — nothing would have been indexed in ChromaDB and semantic search would have returned zero results.

2. FastMCP constructor doesn't accept `description` — it uses `instructions`. Caught by server tests.

3. The healthcheck was pointing at `/mcp` (the MCP protocol endpoint) which doesn't respond to plain HTTP GET. Added a custom `/health` route.

## Follow-up Items

- Add web scraping support for documentation websites (project brief mentions this as a future source type)
- Consider adding a `get_chunks` tool that returns all chunks for a given file
- Add integration test that runs a full ingestion cycle against a test git repo (would improve the 56% coverage on ingestion.py)
- Evaluate search quality once real documentation is indexed — may need to tune chunk size or overlap
