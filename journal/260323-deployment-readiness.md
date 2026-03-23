# Deployment Readiness Assessment

**Date:** 2026-03-23

## Context

Assessed whether the documentation MCP server is ready to deploy onto the infra VM (192.168.2.106) as part of the existing docker compose stack managed by Ansible.

## Documentation Sources

Two sources configured:
1. **home-server-docs** — mkdocs source files at `/srv/infra/mkdocs/docs` on the infra VM, mounted read-only into the container
2. **nanoclaw** — cloned from `https://github.com/johnmathews/nanoclaw.git` via the docserver's built-in remote repo support, indexing `docs/**/*.md` and `journal/**/*.md`

## Decision: Git Clone for Cross-Host Docs

The nanoclaw docs live on the agent LXC (192.168.2.107), not the infra VM. Considered NFS mounts, SSHFS, and Proxmox bind mounts, but chose git clone from GitHub because:
- Zero infrastructure changes needed
- Natively supported by the docserver (`is_remote: true`)
- For documentation, committed content is the right thing to index
- No new failure modes (NFS/SSHFS add fragile dependencies)

Tradeoff: docs must be pushed to GitHub before they're searchable. Acceptable for documentation workflows.

## Blockers Found and Fixed

1. **Port conflict** — cAdvisor uses 8080, changed docserver to host port 8085
2. **Image source** — switched from `build: .` to `ghcr.io/johnmathews/documentation-mcp-server:latest`
3. **sources.yaml** — created production config (was only an example file)
4. **mem_limit** — added 1536m per stack convention
5. **Volume mount** — mapped `/srv/infra/mkdocs/docs` to `/repos/home-server-docs` in container

## Consumer

The MCP server will be consumed by the nanoclaw personal AI assistant at `http://192.168.2.106:8085/mcp/`. Nanoclaw runs Anthropic models and serves via Slack, WhatsApp, and (future) web UI.

## Next Steps

- Add the service block to the infra VM's central docker-compose.yml (via Ansible)
- Place sources.yaml alongside the compose file
- Push this repo to trigger GHCR image build
- Deploy via Ansible and verify with `curl http://192.168.2.106:8085/health`
- Configure nanoclaw as an MCP client pointing to the docserver
