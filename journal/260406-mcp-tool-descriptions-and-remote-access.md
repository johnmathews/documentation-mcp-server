# MCP Tool Descriptions and Remote Access Setup

**Date:** 2026-04-06

## Summary

Improved MCP server tool descriptions so that Claude Code agents can determine
when the documentation tools are relevant, and configured the MCP server for
global access from any working directory.

## Changes

### Enriched MCP server instructions and tool docstrings

The FastMCP `instructions` field was a single generic line. Agents seeing 50+
tools from multiple MCP servers had no way to know this server covers home
server infrastructure documentation. Updated to include:

- Domain context (home server, Proxmox, Docker, monitoring, self-hosted services)
- Document types covered (project docs, journals, learning notes, runbooks, ADRs)
- Dynamically generated list of currently indexed source names
- Guidance on which tool to start with

Also enriched `search_docs` and `query_docs` docstrings with domain context and
cross-references to `list_sources` for discovering source names.

### User-level MCP server configuration

Added the documentation server as a user-scoped MCP server in `~/.claude.json`
so it's available in all Claude Code sessions regardless of working directory.

### Remote access via Cloudflare tunnel

Set up `docs-mcp.itsa-pizza.com` as a new Cloudflare tunnel subdomain pointing
to the MCP backend (separate from `docs.itsa-pizza.com` which serves the
SvelteKit web UI). Configured Cloudflare Access headers via environment
variables stored in `~/.env` and sourced from `~/.zshrc`.

### Documentation

Fixed tool count in `docs/architecture.md` (was "five", actually six) and added
note about the enriched server instructions.
