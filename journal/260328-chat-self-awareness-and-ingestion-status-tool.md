# Chat Self-Awareness and Ingestion Status Tool

## Problem

The chat agent couldn't answer meta questions about itself — "are all sources indexed?",
"what's the most recent journal entry?" — even though the data was available. It would
respond with "I cannot confirm" or "I would need to use tools" instead of using the
inventory data already in its context.

## Changes

### Enriched Chat System Prompt

The system prompt now includes per-source indexing stats (file count, chunk count,
last-indexed timestamp) alongside the document inventory. It also includes root_docs
and engineering_team categories that were previously missing from the inventory.

The prompt instructions were rewritten to tell the agent to answer confidently from
the inventory data rather than hedging or deferring to tools it can't use.

All stats are queried live from the database on every chat request — nothing is static.

### Full Document Metadata in Inventory

The inventory initially only included document titles. The agent couldn't answer
date-based questions ("what's the oldest document?") because created_at, modified_at,
and size_bytes were available in the tree API but not passed through to the prompt.

Each document line now includes all metadata:
```
- Setup Guide | path=docs/setup.md | created=2025-06-15T10:00:00+00:00 | modified=2026-03-01T12:00:00+00:00 | size=4200b
```

Prompt builder refactored: extracted `_format_doc()` helper, category iteration uses
a loop over `(label, key)` pairs instead of repeated blocks.

### Testable Prompt Builders

Extracted `CHAT_SYSTEM_INSTRUCTIONS`, `build_inventory_context()`, and
`build_system_prompt()` as module-level pure functions (out of the `create_mcp` closure).
37 tests cover instruction content, inventory formatting with all metadata fields,
edge cases (missing dates, missing stats, empty tree), and full prompt assembly.

### New `ingestion_status` MCP Tool

Added a new MCP tool that compares configured sources against indexed sources:
- Lists all configured source names from the YAML config
- Lists all indexed sources with file counts, chunk counts, last indexed time
- Flags any sources that are configured but not yet indexed
- Returns a `fully_indexed` boolean

This is useful for MCP clients (not the chat endpoint) that want to check indexing health.

### Duplicate Source Name Validation

Added earlier in this session — `_parse_sources()` now raises `ValueError` if two sources
share the same name, preventing silent data loss from config copy-paste errors.
