# Documentation MCP Server

An MCP server that indexes documentation from git repositories and makes it searchable by AI agents. Designed to run as a
containerized service on a home server, providing documentation context to agents via the Model Context Protocol.

## Architecture

```
Git Repos (local/remote)
        |
        v
  [Ingestion Layer]     Polls repos every 5 min, parses markdown, chunks text
        |
        v
  [Knowledge Base]      SQLite (metadata) + ChromaDB (vector embeddings)
        |
        v
  [MCP Server]          FastMCP with streamable HTTP transport
        |
        v
  AI Agent (nanoclaw)   Queries docs via MCP tools
```

## MCP Tools

### `search_docs` -- Semantic search

Find documentation relevant to a natural language question.

| Parameter     | Type  | Default | Description                                      |
| ------------- | ----- | ------- | ------------------------------------------------ |
| `query`       | `str` | --      | Natural language search query (required).         |
| `num_results` | `int` | `10`    | Maximum number of results to return (1--100).     |
| `source`      | `str` | `""`    | Optional source name to restrict results to one repo. |

### `query_docs` -- Structured metadata query

Query document metadata by source, path, title, or date range. Useful for questions like "list all docs in source Y" or "what was added after date Z".

| Parameter            | Type  | Default | Description                                 |
| -------------------- | ----- | ------- | ------------------------------------------- |
| `source`             | `str` | `""`    | Filter by source name.                      |
| `file_path_contains` | `str` | `""`    | Filter by substring in file path.           |
| `title_contains`     | `str` | `""`    | Filter by substring in title.               |
| `created_after`      | `str` | `""`    | ISO date string, e.g. `"2024-01-01"`.       |
| `created_before`     | `str` | `""`    | ISO date string.                            |
| `limit`              | `int` | `20`    | Maximum number of results to return (1--100). |

### `get_document` -- Retrieve by ID

Retrieve a specific document or chunk by its ID. Document IDs follow the format `source_name:relative/path` for parent documents, or `source_name:relative/path#chunkN` for chunks.

| Parameter | Type  | Default | Description                         |
| --------- | ----- | ------- | ----------------------------------- |
| `doc_id`  | `str` | --      | The document ID to retrieve (required). |

### `list_sources` -- List sources and status

List all configured documentation sources and their indexing status. Returns source names, file counts, chunk counts, and last indexed time. Takes no parameters.

### `reindex` -- Trigger re-indexing

Trigger an immediate re-indexing of documentation sources.

| Parameter | Type  | Default | Description                                            |
| --------- | ----- | ------- | ------------------------------------------------------ |
| `source`  | `str` | `""`    | Optional source name. If empty, re-indexes all sources. |

## Health Endpoint

`GET /health` returns the current status of the knowledge base.

**200 OK** -- knowledge base is available:

```json
{"status": "ok", "sources": 3, "total_chunks": 542}
```

**503 Service Unavailable** -- knowledge base is unreachable or errored:

```json
{"status": "error"}
```

This endpoint is used by the Docker health check configured in `docker-compose.yml`.

## Quick Start

### 1. Configure sources

```bash
cp config/sources.example.yaml config/sources.yaml
# Edit config/sources.yaml to add your documentation repos
```

### 2. Run with Docker Compose

```bash
# Add volume mounts for local repos in docker-compose.yml, then:
docker compose up -d
```

The server starts on port 8080 and begins indexing immediately.

### 3. Connect from an MCP client

Add to your MCP client configuration (e.g., `.mcp.json`):

```json
{
 "mcpServers": {
  "documentation": {
   "url": "http://localhost:8080/mcp"
  }
 }
}
```

## Configuration

### sources.yaml

```yaml
sources:
 - name: "my-docs"
   path: "/repos/my-docs" # Local path (mount in docker-compose)
   branch: "main"
   patterns:
    - "**/*.md"

 - name: "remote-docs"
   path: "https://github.com/user/repo.git"
   branch: "main"
   is_remote: true

poll_interval: 300 # Seconds between index cycles
data_dir: "/data" # Persistent storage path
```

### Environment Variables

| Variable                  | Default                | Description                  |
| ------------------------- | ---------------------- | ---------------------------- |
| `DOCSERVER_CONFIG`        | `/config/sources.yaml` | Path to config file          |
| `DOCSERVER_DATA_DIR`      | `/data`                | Persistent storage directory |
| `DOCSERVER_POLL_INTERVAL` | `300`                  | Polling interval in seconds  |
| `DOCSERVER_HOST`          | `0.0.0.0`              | Server bind address          |
| `DOCSERVER_PORT`          | `8080`                 | Server port                  |
| `DOCSERVER_LOG_FORMAT`    | `json`                 | Log format (`json` or `text`) |
| `DOCSERVER_LOG_LEVEL`     | `INFO`                 | Log level                    |

## Development

```bash
uv sync --group dev
uv run pytest tests/ -v
```

## How It Works

1. **Ingestion**: The server polls configured git repos on a schedule. For remote repos, it clones them on first run then
   pulls updates. For local repos (mounted as volumes), it pulls if they have a remote, or just reads the files directly.

2. **Parsing**: Markdown files are parsed to extract titles (first `#` heading), creation dates (from git history), and
   modification times. Documents are split into ~400-character chunks at section and paragraph boundaries, with each chunk
   prefixed by its heading hierarchy (e.g. `[Setup > Ports]`) and ~100 chars of overlap between chunks. Lists and code
   fences are kept intact.

3. **Storage**: Parent document metadata goes into SQLite for structured queries. Document chunks are embedded and stored
   in ChromaDB for semantic search.

4. **Serving**: The FastMCP server exposes tools over streamable HTTP. Agents can search semantically, query by metadata,
   or retrieve specific documents. A `/health` endpoint returns indexing status for container orchestration.
