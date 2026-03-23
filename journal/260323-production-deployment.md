# Production Deployment and Operational Improvements

**Date:** 2026-03-23

## Context

Deployed the documentation MCP server to the infra VM and worked through several issues getting both sources (SRE docs and home-server docs) indexing correctly. This session focused on making the service observable, resilient, and efficient in production.

## Changes Made

### Health endpoint enriched

The `/health` endpoint now returns per-source breakdown (file count, chunk count, last indexed time) instead of just aggregate totals. This makes it possible to verify at a glance which sources are indexed and whether ingestion is current.

### Private repository support

Added `${VAR}` environment variable expansion in `sources.yaml` source paths. Private repos authenticate via a GitHub fine-grained PAT passed as `GITHUB_TOKEN` through docker-compose. Credentials are redacted in all log output.

Key lesson: Docker compose `.env` files treat quotes as literal characters. `GITHUB_TOKEN="abc"` sets the value to `"abc"` (with quotes), not `abc`.

### Comprehensive logging

Added structured logging across all components: config loading, KB initialization, ingestion cycle lifecycle, git sync/clone, file enumeration, and embedding model status. Every log line includes an `event` field for filtering. This was critical for diagnosing the deployment issues — without it, ingestion failures were completely silent.

### Embedding model caching

The ONNX embedding model (~110MB) was being re-downloaded on every container restart because it cached to the ephemeral container filesystem. Fixed by:

1. Pre-downloading into `/app/models-cache` during Docker build
2. Seeding to `/data/models/` (persistent volume) on first startup
3. Subsequent restarts load from persistent cache instantly

### Skip-unchanged optimization

Ingestion now compares file mtime against the stored `modified_at` timestamp and skips files that haven't changed. Before this, every 5-minute poll cycle re-embedded all chunks (~5+ minutes of CPU). Now unchanged cycles complete in seconds.

## Issues Encountered

1. **YAML indentation** — inconsistent indentation in `sources.yaml` caused a parse error that crash-looped the container
2. **Stale clone directory** — a failed clone attempt left an empty directory at `/data/clones/<name>`. The sync logic saw the directory existed and assumed it was a valid repo, then skipped cloning. Fix: delete the stale directory manually
3. **Quoted env vars** — `.env` file had `GITHUB_TOKEN="value"` with literal quotes, causing git auth to fail silently
4. **Slow first ingestion** — embedding 664 chunks on CPU took ~5 minutes, blocking the second source from being processed. APScheduler correctly skipped overlapping cycles (`max_instances=1`)

## Decisions

- **Mtime-based skip** over content hashing: simpler, no extra storage, and filesystem mtime is sufficient for the git-pull-then-index workflow. If a file is pulled with new content, git updates the mtime.
- **Sequential source processing**: sources are ingested one after another in the same cycle. Parallel ingestion would add complexity for marginal gain given the skip-unchanged optimization.
