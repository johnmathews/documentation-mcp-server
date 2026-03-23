# Operations

## Monitoring

### Health Endpoint

`GET :8080/health` returns JSON with the current indexing status and per-source breakdown:

```json
{
  "status": "ok",
  "total_sources": 2,
  "total_chunks": 150,
  "sources": [
    {
      "source": "home-server-docs",
      "file_count": 12,
      "chunk_count": 85,
      "last_indexed": "2026-03-23T10:00:00"
    },
    {
      "source": "nanoclaw",
      "file_count": 5,
      "chunk_count": 65,
      "last_indexed": "2026-03-23T10:00:00"
    }
  ]
}
```

Each source entry includes:

- `source` -- source name from `sources.yaml`
- `file_count` -- number of parent documents (markdown files)
- `chunk_count` -- number of indexed chunks
- `last_indexed` -- timestamp of the most recent indexing for that source

Returns **503** with `{"status": "error"}` if the knowledge base is unreachable.

### Rescan Endpoint

`POST :8080/rescan` triggers an immediate ingestion cycle without waiting for the next poll interval. Optionally pass `?source=name` to rescan a single source.

```bash
# Rescan all sources
curl -X POST http://localhost:8085/rescan

# Rescan a single source
curl -X POST "http://localhost:8085/rescan?source=SRE%20documentation"
```

Returns JSON with ingestion stats and duration:

```json
{
  "status": "ok",
  "duration_ms": 1200,
  "stats": {
    "SRE documentation": {"files": 24, "new": 0, "modified": 1, "skipped": 23, "deleted": 0, "errors": 0, "upserted": 4}
  }
}
```

### Docker Health Check

The Dockerfile configures a health check against `/health`:

- Interval: 30s
- Timeout: 10s
- Start period: 120s (allows time for embedding model load and first ingestion)
- Retries: 3

### Logging

Logs are structured JSON to stdout by default, suitable for Docker log collection. Each line includes `timestamp`, `level`, `logger`, `message`, and optional structured fields.

Configure with environment variables:

- `DOCSERVER_LOG_FORMAT` -- `json` (default) or `text`
- `DOCSERVER_LOG_LEVEL` -- `INFO` (default), `DEBUG`, `WARNING`, etc.

Key log events (filter with `grep '"event":'`):

| Event | Extra Fields | Description |
|-------|-------------|-------------|
| `config` | `source` | Config file loaded, each source configured |
| `kb_init` | -- | SQLite and ChromaDB initialization |
| `startup` | -- | Server started with poll interval and data dir |
| `model_cached` | -- | Embedding model loaded from persistent cache |
| `model_download_start/done` | -- | Embedding model being downloaded |
| `ingestion_start` | `sources` | Ingestion cycle beginning |
| `sync_start` / `sync_done` | `source`, `changed` | Git sync per source |
| `clone_start` / `clone_done` | `source` | First-time clone of remote repo |
| `files_found` | `source`, `file_count` | Files matched by glob patterns |
| `indexing_file` | `source`, `doc_id`, `change_type`, `chunks`, `progress` | Per-file progress: `[3/24] Indexing new file 'docs/setup.md' (5 chunks)` |
| `skip_summary` | `source`, `processed`, `skipped` | Summary after file loop: how many processed vs skipped |
| `ingestion_source_done` | `source`, `stats` | Per-source completion with new/modified/skipped/deleted/error counts |
| `ingestion_done` | `stats` | Full cycle completion |
| `search` | `duration_ms` | Each search query with timing |
| `reindex` | `duration_ms`, `stats` | Manual reindex via MCP tool |

Credentials in source URLs are redacted in all log output (`https://<redacted>@...`).

Docker log rotation is configured in `docker-compose.yml`: 3 files, 10MB max each.

## Troubleshooting

### Failed ingestion

Check logs for these messages:

- `"Failed to parse"` -- A markdown file could not be parsed. The file is skipped.
- `"Failed to pull"` -- A git pull failed for a source. May indicate network issues or auth problems for remote repos.
- `"Unexpected error syncing"` -- Catch-all for other ingestion failures.

Each source is ingested independently. One source failing does not block others.

### Remote repo not cloning

If a remote source shows `"exists but is not a git repo; skipping sync"`, a previous failed clone left an empty directory. Delete it and restart:

```bash
docker exec documentation-mcp-server rm -rf "/data/clones/<source name>"
docker compose restart docserver
```

### Search returns no results

1. Hit the health endpoint and check `total_chunks`. If 0, no documents have been indexed.
2. Verify `config/sources.yaml` has sources configured and paths are correct.
3. First ingestion runs immediately on startup -- if the container just started, wait for the start period (up to 120s) and check again.
4. Check logs for ingestion errors on the source you expect results from.

### Container shows as unhealthy

The Docker health check calls `GET /health`. A 503 response or connection failure triggers unhealthy status.

Common causes:

- The `/data` volume is not mounted or not writable. Verify the `docserver-data` volume exists and the container user (UID 1000) has write access.
- The server failed to start. Check container logs with `docker logs documentation-mcp-server`.
- The embedding model is still loading. The start period is 120s to account for this.

### Large files skipped

Files over 5MB are skipped during ingestion. A warning is logged with the file path and size. This is intentional to avoid excessive memory usage during parsing and embedding.

## Backup and Restore

All persistent data lives in the `docserver-data` Docker volume, mounted at `/data` inside the container.

Contents:

| Path | Description |
|------|-------------|
| `/data/documents.db` | SQLite database (document metadata) |
| `/data/chroma/` | ChromaDB vector store (embeddings) |
| `/data/clones/` | Git clones of remote repos |
| `/data/models/` | Cached ONNX embedding model (~110MB) |

### Backup

```bash
docker cp documentation-mcp-server:/data /backup/docserver-data
```

### Restore

Copy the backed-up data back into the volume and restart the container.

### Full rebuild

The data is fully rebuildable from source repositories. Deleting the volume and restarting the container will re-clone all repos and re-index everything from scratch. This takes longer than restoring a backup but requires no backup files.

```bash
docker compose down -v   # removes the volume
docker compose up -d     # rebuilds from source repos
```

## Resource Usage

| Resource | Typical | Limit |
|----------|---------|-------|
| Memory | ~1--1.5 GB (embedding model + ChromaDB) | 2 GB (set in docker-compose.yml) |
| Disk | ~100 MB per 10K documents | -- |
| CPU | Low at idle; spikes during ingestion (embedding generation) | -- |

Log rotation: 3 files of 10 MB max (configured in `docker-compose.yml` logging options).

## Configuration Changes

### Changing sources

Edit `config/sources.yaml` and restart the container:

```bash
docker compose restart docserver
```

The `reindex` MCP tool only re-indexes sources that were loaded at startup. Adding a new source requires a restart so the config is reloaded.

Unchanged files are skipped during ingestion (compared by mtime), so restarts and re-indexes are fast when nothing has changed.

### Private repositories

Source paths in `sources.yaml` support `${VAR}` environment variable expansion. Use this to authenticate with private repos without hardcoding tokens:

```yaml
sources:
  - name: "private-repo"
    path: "https://${GITHUB_TOKEN}@github.com/user/repo.git"
    branch: "main"
    is_remote: true
```

Pass the token to the container via `docker-compose.yml`:

```yaml
environment:
  - GITHUB_TOKEN=${GITHUB_TOKEN}
```

And set the actual value in your `.env` file. The token needs **Contents: Read-only** permission on the target repository (use a fine-grained GitHub PAT).

If a referenced environment variable is not set, the server will raise an error at startup.

### Environment variables

Set in `docker-compose.yml` under `environment`, or in a `.env` file alongside `docker-compose.yml`.

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCSERVER_POLL_INTERVAL` | `300` | Seconds between ingestion cycles |
| `DOCSERVER_DATA_DIR` | `/data` | Persistent storage directory |
| `DOCSERVER_CONFIG` | `/config/sources.yaml` | Path to config file |
| `DOCSERVER_HOST` | `0.0.0.0` | Server bind address |
| `DOCSERVER_PORT` | `8080` | Server port |
| `DOCSERVER_LOG_FORMAT` | `json` | `json` or `text` |
| `DOCSERVER_LOG_LEVEL` | `INFO` | Python log level |

Changes to environment variables require a container restart to take effect.

## CI/CD

A GitHub Actions workflow (`.github/workflows/docker-publish.yml`) builds and pushes the Docker image to `ghcr.io/johnmathews/documentation-mcp-server` on every push to `main`.

The image is tagged with:

- `latest` -- always points to the most recent build from `main`
- `sha-<short>` -- the git commit SHA for traceability

The workflow authenticates to `ghcr.io` using the built-in `GITHUB_TOKEN` secret (no manual secret configuration needed).
