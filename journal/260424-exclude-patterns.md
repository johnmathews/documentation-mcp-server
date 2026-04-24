# Add exclude_patterns support for source configuration

**Date:** 2026-04-24

## Context

The tech-blog source was indexing all markdown files in the repo, including the `data/`
directory which contains blog post content. Blog entries are not useful as documentation
and were cluttering search results. The existing `patterns` config only supported inclusion
globs with no way to exclude specific directories.

## Changes

Added `exclude_patterns` as an optional field on source configuration. It accepts a list
of glob patterns that are applied after inclusion matching to filter out unwanted files.

- `RepoSource` dataclass: new `exclude_patterns: list[str]` field (defaults to empty list)
- `_parse_sources()`: parses `exclude_patterns` from YAML config
- `RepoManager.get_files()`: after matching inclusion globs, removes files matching any
  exclusion glob. Exclusion runs before auto-includes (README.md, `.engineering-team/`,
  `documentation/`), so those directories are never accidentally excluded.
- Logs excluded file count under the `files_excluded` event for operational visibility.

## Usage

```yaml
sources:
  - name: "tech-blog"
    path: "https://github.com/johnmathews/tech-blog.git"
    branch: "main"
    exclude_patterns:
      - "data/**"
```

## Testing

6 new tests added across `test_config.py` and `test_ingestion.py`:
- Config parsing: exclude_patterns from YAML, defaults to empty list, defaults assertion
- Ingestion: single pattern exclusion, multiple patterns, empty patterns (no-op)

All 369 tests pass. Coverage stable at 87%.
