# Source Rename Detection

**Date:** 2026-03-23

## Problem

Every time a source name was changed in `sources.yaml`, the orphan cleanup logic
treated the old name as a deleted source and the new name as a brand-new source.
This triggered a full delete → re-clone → re-embed cycle for every file, taking
minutes per source due to embedding computation (~5s per file on the ARM host).

In production, renaming 3 sources caused ~2,100 documents to be deleted and then
immediately re-indexed from scratch on the next ingestion cycle.

## Solution

Added URL-based rename detection to the orphan cleanup step:

1. Before deleting an orphaned source, inspect its clone directory's git remote URL.
2. Normalise URLs (strip credentials, `.git` suffix, trailing slashes, lowercase)
   and compare against configured sources.
3. If a match is found and the new name has no existing data, migrate in-place:
   - Update doc_ids and source column in SQLite
   - Migrate ChromaDB entries preserving existing embeddings (fetch → delete → re-add with new IDs)
   - Rename the clone directory

## Key decisions

- **URL normalisation**: Needed because the same repo can appear with different URL
  forms (with/without `.git`, with/without credentials, different casing).
- **Preserve embeddings**: ChromaDB doesn't support renaming IDs, so we fetch entries
  with their embeddings, delete old IDs, and re-add with new IDs + same embeddings.
  This avoids the expensive re-computation.
- **Safety guard**: If the new source name already has data in the KB, skip the
  rename to avoid data corruption from false URL matches.

## Files changed

- `src/docserver/knowledge_base.py` — `rename_source()` method
- `src/docserver/ingestion.py` — `_normalise_repo_url()`, `_detect_rename()`, `_migrate_renamed_source()`, updated `cleanup_orphaned_sources()`
- `tests/test_knowledge_base.py` — rename tests
- `tests/test_ingestion.py` — rename detection + URL normalisation tests
- `docs/architecture.md` — documented rename detection
- `docs/operations.md` — new log events, updated config change docs
