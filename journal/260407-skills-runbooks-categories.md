# Add Skills and Runbooks Document Categories

**Date:** 2026-04-07

## Summary

Added two new document categories — **skills** and **runbooks** — to support the nanoclaw data source's directory structure. Changes span both the documentation server (Python backend) and the documentation UI (SvelteKit webapp).

## Motivation

Nanoclaw has skill documentation at `container/skills/<skill-name>/skill.md` and operational runbooks under `runbooks/`. Previously these would all land in the generic "docs" category, making them hard to find. Giving them dedicated categories improves discoverability for both human users and the AI chat assistant.

## Changes

### Server (unified-documentation-server)

- `config/sources.yaml` — Added `container/skills/**/skill.md` and `runbooks/**/*.md` glob patterns to the nanoclaw source (file is gitignored, updated locally)
- `knowledge_base.py` — Added `skills` and `runbooks` to the path-based category detection in `get_document_tree()`, before the generic `docs` fallback. Both sort alphabetically by title.
- `server.py` — Added Skills and Runbooks to the chat inventory prompt so the AI assistant knows about these categories
- `docs/architecture.md` — Updated `/api/tree` endpoint documentation to list all 9 categories

### Webapp (unified-documentation-webapp)

- `api.ts` — Added `skills?` and `runbooks?` fields to `TreeSource` interface; added matching branches to `categorizeFilePath()`
- `stores.svelte.ts` — Added Skills and Runbooks to the `CATEGORIES` constant
- `Sidebar.svelte` — Added expand/collapse, count, and render blocks for both categories (star icon for skills, book icon for runbooks)
- `+page.svelte` (homepage) — Added skills and runbooks to `allDocs()` document count
- `source/[name]/+page.svelte` — Added stat tags and document list sections
- `source/[name]/[category]/+page.svelte` — Added routing and labels
- `CLAUDE.md` and `docs/architecture.md` — Updated category lists

### Tests

- `test_knowledge_base.py` — Added `test_get_document_tree_skills_category` and `test_get_document_tree_runbooks_category`
- `test_chat_prompt.py` — Added `with_skills`/`with_runbooks` params to `_make_tree()` fixture, plus `test_includes_skills_category` and `test_includes_runbooks_category`

## Design Decisions

- Categories are path-based (matching `skills/` or `runbooks/` in the file path), consistent with all existing categories
- The webapp's `titles.ts` already had `Skill: <Name>` display logic using the parent directory name — no change needed
- Both categories sort alphabetically by title, matching other reference-style categories (docs, engineering_team)
