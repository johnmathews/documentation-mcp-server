# Unified Documentation Server

## Project Structure

- `src/docserver/` - Main package
  - `config.py` - YAML + env var configuration
  - `ingestion.py` - Git repo syncing, markdown parsing, chunking
  - `knowledge_base.py` - SQLite + ChromaDB storage layer
  - `server.py` - FastMCP server with tool definitions
  - `logging_config.py` - Structured JSON logging for Docker
  - `__main__.py` - Entry point
- `tests/` - pytest test suite
- `config/` - Configuration files (sources.yaml)
- `docs/` - Project documentation
- `journal/` - Development journal

## Key Commands

- `uv sync --group dev` - Install dependencies
- `uv run pytest tests/ -v` - Run tests
- `uv run python -m docserver` - Run server locally
- `docker compose up -d` - Run containerized

## Architecture Decisions

- **uv** for dependency and environment management
- **ChromaDB** for vector search with all-mpnet-base-v2 embedding model (768 dims, ~500MB RAM)
- **SQLite** for structured metadata queries (dates, paths, sources)
- Documents are chunked at ~400 chars on section/paragraph boundaries with 100-char overlap; parent doc metadata stored separately for structured queries
- Doc IDs follow pattern: `{source}:{path}` (parent) and `{source}:{path}#chunk{N}` (chunks)
- Only chunks go into ChromaDB; parent docs are SQLite-only
- APScheduler runs ingestion on a background thread
- MCP transport: streamable HTTP on port 8080
