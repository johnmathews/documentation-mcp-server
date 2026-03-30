# Fix: Local sources no longer run git commands

**Date:** 2026-03-30

## Problem

`_sync_local()` in `ingestion.py` ran `git fetch` + `git reset --hard
origin/<branch>` on local source directories every poll cycle (default 300s).
If the doc server was running locally with a source pointing to a real working
directory, this would silently destroy uncommitted changes — tracked file
modifications, staged work, and any local commits not yet pushed.

The same `fetch + reset --hard` pattern is correct for *remote* sources
(disposable clones owned by the server) but catastrophic for local working
directories that belong to the user.

## Fix

Replaced `_sync_local()` with a simple path-existence check. The method now:

1. Verifies the configured path exists and is a directory.
2. Returns `False` (no sync-level change signal).
3. Performs **zero** git operations.

Change detection for local sources is handled entirely by the content-hash
comparison that already runs during ingestion — each file's SHA-256 is compared
against its previously indexed hash, so changed files are still re-indexed
without needing git.

## What was removed

- `git fetch` from origin
- `git reset --hard origin/<branch>` (the destructive operation)
- `git checkout -B <branch> origin/<branch>` (corrupt HEAD recovery)
- All `Repo()` instantiation for local sources
- Error handling for git operations that no longer happen

## Tests

- `test_sync_local_never_runs_git_commands` — mocks `Repo` and asserts it is
  never called for local sources
- `test_sync_local_git_repo_is_not_modified` — creates a real git repo with
  uncommitted work, runs sync, verifies files are untouched
- `test_sync_local_does_not_modify_plain_directory` — verifies plain
  directories are also unmodified (mtime preserved)

## Removed `is_remote` config option

The `is_remote` YAML field has been removed from the config surface entirely.
Remote vs local is now determined automatically by `_looks_like_git_url()` in
`config.py` — paths matching `https://`, `git@`, `ssh://`, `git://`, or ending
in `.git` are remote; everything else is local. The `is_remote` field on
`RepoSource` still exists internally but is never read from config. Any
`is_remote` field in existing YAML files is silently ignored.

## Design principle

The server is a read-only observer. It must never modify source files — local
or remote. For remote sources the server owns the clone directory; for local
sources it has no ownership and must not write.
