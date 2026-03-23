# Improve ingestion error logging

When a source repo is accessible but no documentation files are found (e.g., wrong glob
patterns, docs in a subdirectory, missing mount), the previous error messages were vague --
"No files matched for source 'x' -- check glob patterns" didn't tell you what was actually
in the directory or what patterns were tried.

## Changes

Overhauled error and warning messages throughout `ingestion.py` to be explicit and
actionable:

- **`get_files()`**: When no files match, logs the directory contents, lists which glob
  patterns were tried with per-pattern match counts, checks for common doc directory names
  (`docs/`, `doc/`, `wiki/`, etc.), and suggests fixes.
- **`_sync_remote()`**: Clone failures now have a dedicated try/except with specific
  causes listed (bad URL, expired creds, nonexistent branch, network, disk). The empty
  clone directory is auto-cleaned so the next cycle retries. Pull failures include the
  redacted URL, branch, and path.
- **`_sync_local()`**: Path-not-found checks whether the parent directory exists to
  distinguish "wrong path" from "Docker mount missing entirely". Non-directory paths are
  caught explicitly.
- **`run_once()`**: Sync and file-listing errors now include source path, remote flag,
  branch, and glob patterns.

Updated `docs/operations.md` with new log event types and expanded troubleshooting
guidance for the "no files found" scenario.
