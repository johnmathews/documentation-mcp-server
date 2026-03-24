# Ingestion Performance Optimizations

Investigated why document scanning/ingestion was slow and implemented four
optimizations to speed it up without lowering quality.

## Problem

Full ingestion cycles were slow, especially for repos with many files. The
main bottlenecks were:

1. **Per-file git subprocess calls** — `git log --follow --diff-filter=A` ran
   once per file to get creation dates, spawning O(n) subprocesses.
2. **One-at-a-time ChromaDB upserts** — each chunk was upserted individually,
   causing the ONNX embedding model to process 1 document per inference call
   despite supporting batch_size=32.
3. **One-at-a-time SQLite inserts** — each document opened a new connection
   and ran a single INSERT.
4. **Sequential source syncing** — git fetch/pull for each source ran one
   after another.

## Changes

### Bulk git log (`DocumentParser._bulk_git_created_at`)
Single `git log --diff-filter=A --name-only --reverse` call retrieves
creation dates for all files in the repo. Files not found in the bulk result
(e.g. renamed files that need `--follow`) fall back to per-file lookup.

### Batch ChromaDB + SQLite upserts (`KnowledgeBase.upsert_documents_batch`)
New method that:
- Uses `executemany` for SQLite within a single transaction
- Sends chunks to ChromaDB in capped batches (`_CHROMA_BATCH_SIZE = 64`)
  so the embedding model processes 32 docs at a time

The ingestion loop collects items and flushes every 64 items
(`BATCH_FLUSH_SIZE`). Each flush is logged with item counts and running
totals. On batch failure, falls back to individual upserts.

### Parallel source syncing
`ThreadPoolExecutor` (up to 4 workers) runs git sync for all sources
concurrently. KB writes remain sequential (SQLite/ChromaDB not thread-safe).

### Progress tracking
Batch flushes log: item count, chunk count, and cumulative total upserted.
Combined with existing per-file `[N/M]` progress logs.

## Expected Impact
- Git log batching: ~10-50x faster for parsing phase
- ChromaDB batching: ~10-30x faster for embedding computation
- SQLite batching: ~2-5x faster for DB writes
- Parallel sync: ~Nx faster for N sources during git fetch
