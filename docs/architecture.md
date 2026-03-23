# Architecture

## Overview

The Documentation MCP Server has three layers:

```
Git Repos (local/remote)
        |
        v
  [Ingestion Layer]     Polls repos, parses markdown, chunks text
        |
        v
  [Knowledge Base]      SQLite (metadata) + ChromaDB (vector embeddings)
        |
        v
  [MCP Server]          FastMCP with streamable HTTP transport
```

## Ingestion Layer

**Module:** `src/docserver/ingestion.py`

The ingestion layer manages git repositories and converts markdown files into searchable documents.

### Components

- **RepoManager**: Handles git operations for a single source. Remote repos are cloned into `/data/clones/<source_name>/` on first run, then pulled on subsequent cycles. Local repos (mounted as Docker volumes) are pulled if they have a git remote, or treated as static directories otherwise.

- **DocumentParser**: Reads a markdown file and extracts:
  - Title (first `#` heading, or filename as fallback)
  - Creation date (from `git log --follow --diff-filter=A`)
  - Modification time (filesystem mtime)
  - File size

- **Chunking** (section-aware): Documents are split into ~400-character chunks using a multi-step strategy:
  1. Parse markdown headings into a section tree
  2. Within each section, group blocks (paragraphs, lists, code fences) into chunks at ~400 chars
  3. Prepend each chunk with its section heading path (e.g. `[Setup > Networking > Ports]`) so chunks are self-describing in isolation
  4. Add ~100 chars of overlap from the previous chunk (prefixed with `[...]`) to preserve context across boundaries

  Special handling:
  - **Lists**: Contiguous list items (`-`, `*`, `1.`) are kept together as a single block
  - **Code fences**: Everything between ` ``` ` markers stays in one block; headings inside code fences are ignored
  - **Oversized blocks**: Blocks larger than the target size are emitted whole rather than split mid-content

- **Ingester**: Orchestrates the full cycle via APScheduler. On each tick:
  1. Sync each repo (clone/pull)
  2. Enumerate files matching glob patterns
  3. Compare file mtime against stored `modified_at` — skip unchanged files
  4. Parse and chunk changed files
  5. Upsert into the knowledge base
  6. Delete stale documents that no longer exist in the repo

  The skip-unchanged optimization means typical poll cycles (no changes) finish in seconds instead of re-embedding all chunks.

### Document ID Scheme

Each file produces two types of records:

| Type | Doc ID Format | Purpose |
|------|--------------|---------|
| Parent doc | `source:relative/path.md` | Metadata-only record for structured queries |
| Chunk | `source:relative/path.md#chunk0` | Text content for semantic search |

Parent docs have `is_chunk = False` and are stored in SQLite only. Chunks have `is_chunk = True` and are stored in both SQLite and ChromaDB.

## Knowledge Base

**Module:** `src/docserver/knowledge_base.py`

Dual-store design:

### SQLite (`/data/documents.db`)

Stores all document metadata in a single `documents` table:

```sql
doc_id        TEXT PRIMARY KEY
source        TEXT NOT NULL
file_path     TEXT NOT NULL
title         TEXT
content       TEXT
chunk_index   INTEGER
total_chunks  INTEGER
created_at    TEXT           -- ISO timestamp from git history
modified_at   TEXT           -- ISO timestamp from file mtime
indexed_at    TEXT           -- ISO timestamp when we indexed it
size_bytes    INTEGER
is_chunk      BOOLEAN
section_path  TEXT           -- heading hierarchy, e.g. "Setup > Ports"
```

Supports structured queries like:
- "When was documentation about X created?"
- "List all files in source Y"
- "What was indexed after date Z?"

Parent docs (non-chunks) are returned by `query_documents()` so results represent whole files, not fragments.

### ChromaDB (`/data/chroma/`)

Stores chunk text with vector embeddings for semantic similarity search. Uses the **all-mpnet-base-v2** embedding model via ONNX Runtime (768 dimensions, ~500MB RAM, runs locally with no external API calls). ONNX Runtime was chosen over PyTorch-based sentence-transformers to keep Docker images small (~1GB vs ~8GB) and build times fast.

Only chunks are stored in ChromaDB. Parent docs are excluded since they have no content body. Each chunk's metadata in ChromaDB includes `source`, `file_path`, `title`, `chunk_index`, `total_chunks`, and `section_path` for filtering.

## MCP Server

**Module:** `src/docserver/server.py`

Built with FastMCP, exposes five tools over streamable HTTP:

| Tool | Use Case |
|------|----------|
| `search_docs` | Natural language questions ("what ports does VM X use?") |
| `query_docs` | Structured filters (source, path, title, date range) |
| `get_document` | Retrieve a specific document by its ID |
| `list_sources` | Show all sources with file/chunk counts and last indexed time |
| `reindex` | Trigger an immediate ingestion cycle |

### Endpoints

- `/mcp` — MCP protocol endpoint (streamable HTTP transport)
- `/health` — Health check returning status, total source/chunk counts, and per-source breakdown (file count, chunk count, last indexed time)

### Logging

**Module:** `src/docserver/logging_config.py`

Structured JSON logging to stdout for Docker log collection. Each log line is a JSON object with `timestamp`, `level`, `logger`, `message`, and any extra structured fields (all extra fields are included automatically). Configurable via `DOCSERVER_LOG_FORMAT` (json/text) and `DOCSERVER_LOG_LEVEL`.

Logging covers every phase: config loading, KB initialization, ingestion cycle start/end, per-source sync/clone/file-enumeration/upsert/cleanup, embedding model status, and search queries. Credentials are redacted in all log output. Each log line includes an `event` field for easy filtering (e.g. `sync_start`, `ingestion_done`, `clone_start`).

## Deployment

Single Docker container (Python 3.13) running all three layers. The ONNX embedding model files are pre-downloaded during the Docker build into `/app/models-cache`. On first startup, this is copied to `/data/models/` (the persistent volume) so subsequent restarts load the model instantly without re-downloading.

Source paths in `sources.yaml` support `${VAR}` environment variable expansion for authenticating with private repositories (e.g. `https://${GITHUB_TOKEN}@github.com/...`).

Data persists in a named Docker volume mounted at `/data`. Local repos are mounted read-only into `/repos/`.

```yaml
# docker-compose.yml volumes
volumes:
  - docserver-data:/data                    # Persistent storage
  - ./config/sources.yaml:/config/sources.yaml:ro  # Config
  - /path/to/repo:/repos/repo-name:ro      # Local repos
```
