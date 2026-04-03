# Rename to unified-documentation-server

Renamed the project from `documentation-mcp-server` to `unified-documentation-server`
to reflect that the server is more than just an MCP server (it also serves a web UI,
exposes REST endpoints for health/rescan, etc.).

## What changed

- GitHub remote renamed to `unified-documentation-server`
- Updated all functional references across:
  - CI workflow (ghcr.io image name)
  - docker-compose.yml (image + container name)
  - pyproject.toml (package name)
  - docs/operations.md (docker exec/logs/cp commands, CI/CD section)
  - docs/architecture.md (title reference)
  - CLAUDE.md (project title)
  - config/sources.yaml and sources.local.yaml (comment header, source entry, data_dir)
- Regenerated uv.lock
- Left journal entries referencing the old name untouched (historical record)

## Note for deployment

The old ghcr.io image (`ghcr.io/johnmathews/documentation-mcp-server`) will stop
receiving updates. After the first CI push under the new name, the server host needs
to pull `ghcr.io/johnmathews/unified-documentation-server:latest` instead.
