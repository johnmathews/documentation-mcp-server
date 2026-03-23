# Content Hash Skip Logic and Orphan Cleanup

**Date:** 2026-03-23

## Problem

Two related issues caused the documentation server to re-index all documents on every restart:

1. **Mtime-based skip logic broke on fresh clones.** The ingestion layer compared filesystem `modified_at` timestamps to decide whether a file had changed. When a git repo was freshly cloned (new clone directory), all files got the current timestamp as their mtime, so every file appeared "modified" even though the content was identical.

2. **Source renames caused fresh clones.** Clone directories are stored at `/data/clones/<source_name>/`. Renaming a source in `sources.yaml` (e.g. `container-exporter` to `container-status-exporter`) meant the system couldn't find the old clone directory, triggered a fresh clone, and hit issue #1. The old source's data in the KB and old clone directory were orphaned.

## Changes

### Content hash skip (ingestion.py, knowledge_base.py)

- Added `content_hash` column (SHA-256) to the SQLite `documents` table with a migration for existing databases.
- Replaced `get_indexed_modified_times()` with `get_indexed_content_hashes()`.
- Ingestion now computes SHA-256 of file content and compares against the stored hash. Identical content is skipped regardless of filesystem mtime.

### Orphan cleanup (ingestion.py, knowledge_base.py)

- Added `cleanup_orphaned_sources()` method to `Ingester`. Runs at the start of every full ingestion cycle (not filtered runs).
- Compares configured source names against source names in the KB.
- Deletes KB entries (SQLite + ChromaDB) and clone directories for sources no longer in the config.
- Added `get_all_source_names()` to `KnowledgeBase`.

### Tests

Added 7 new tests covering:
- Content hash skip with identical content but different mtime
- Content hash detection of actually modified content
- Orphan cleanup of KB entries and clone directories
- Orphan cleanup auto-runs on full ingestion
- Orphan cleanup skipped on filtered ingestion
- KB methods: `get_indexed_content_hashes`, `get_all_source_names`

## Decisions

- **Content hash over mtime**: Content hashing is more robust than mtime comparison. It handles fresh clones, copied files, and any scenario where mtimes change without content changing. The SHA-256 cost is negligible compared to embedding generation.
- **Orphan cleanup on full runs only**: Filtered runs (`run_once(sources=["x"])`) skip cleanup to avoid accidentally deleting sources that just weren't targeted.
- **No rename mapping**: Considered adding an `aliases` field to config for explicit rename tracking, but content hashing + orphan cleanup makes this unnecessary — renamed sources just do a fast no-op re-scan (content matches) and the old name gets cleaned up.
