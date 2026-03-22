# Pre-deployment Hardening

**Date:** 2026-03-22

## Context

Full engineering evaluation and improvement pass before first Docker deployment to the infra VM. 50 tests passed before changes; identified 11 work units across critical bugs, security hardening, robustness, testing, and documentation.

## Changes

### Critical Fixes

- **Tightened dependency pins** (pyproject.toml): Added upper bounds to prevent breakage from upcoming major releases (MCP SDK v2, ChromaDB 2.x, APScheduler 4.x). GitPython lower bound raised to 3.1.41 to ensure all known CVE fixes are included.
- **Fixed reindex source filter bug** (server.py, ingestion.py): `reindex(source="x")` was re-indexing ALL sources and only filtering the stats output. Now `run_once()` accepts a `sources` parameter and only processes the specified sources.

### Security / Docker Hardening

- **Non-root container user** (Dockerfile): Added `docserver` user (UID 1000). Container no longer runs as root.
- **Resource limits** (docker-compose.yml): 2GB memory limit, log rotation (3x10MB), 30s stop grace period.

### Robustness

- **Closed GitPython Repo objects** (ingestion.py): Added `repo.close()` in `finally` blocks for `_sync_remote()` and `_sync_local()` to prevent resource leaks in the long-running daemon.
- **Input validation** (server.py): `num_results` and `limit` clamped to 1-100.
- **File size guard** (ingestion.py): Files > 5MB are skipped with a warning log to prevent OOM.
- **Search exception logging** (knowledge_base.py): `except Exception: return []` now logs the exception instead of silently swallowing it.
- **Health endpoint error handling** (server.py): Returns 503 with `{"status": "error"}` on KB failure instead of unhandled 500.

### Stats Cleanup

- Removed misleading `added` key from ingestion stats. Was always 0. Stats now use `upserted` and `deleted` keys.

### Tests

- Added 19 new tests (50 -> 69 total), covering:
  - RepoManager: path resolution, file globbing, git sync (mocked)
  - Ingester: full `run_once()` cycle, source filtering, stale doc cleanup, large file skipping
  - Health endpoint: 200 and 503 responses
  - Input validation: boundary values for num_results/limit
  - KnowledgeBase: delete_source_documents
- Coverage: 71% -> 85%

### Documentation

- **README.md**: Expanded MCP Tools section with full parameter tables. Added Health Endpoint section.
- **docs/operations.md**: New operational guide covering monitoring, troubleshooting, backup/restore, resource usage, and configuration changes.

## Decisions

- Kept `all-mpnet-base-v2` embedding model. Newer alternatives exist (BGE-M3, Nomic Embed v2) but current model is well-tested and appropriate for the use case.
- Kept GitPython despite maintenance-mode status. Added `close()` calls to mitigate leak risk. If leaks appear in production, switching to subprocess-based git calls is the next step.
- File size limit set at 5MB -- high enough for any reasonable markdown doc, low enough to prevent OOM from accidental large files.

## Remaining Concerns

- `__main__.py` and `run_server()` are untested (entry point integration). Acceptable -- these are thin wrappers.
- Broad `except Exception` blocks remain in ingestion orchestration (intentional: scheduler must not die from individual source failures).
