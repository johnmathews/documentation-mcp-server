# PDF file support

Added support for indexing and serving binary files (PDFs) alongside existing markdown documents.

## Changes

### Ingestion pipeline
- Added `DocumentParser.parse_binary()` method for non-text files. Stores metadata only (title from filename, dates, size) with empty content. No text extraction or chunking.
- `BINARY_EXTENSIONS = {".pdf"}` controls which extensions use binary parsing. Extensible for future formats.
- `Ingester.run_once()` branches on file extension: binary files skip chunking and ChromaDB entirely, but still use SHA-256 hash of raw bytes for change detection.
- To include PDFs, add `"**/*.pdf"` to the source's `patterns` in `sources.yaml`.

### Raw file serving endpoint
- Added `GET /api/files/{doc_id}` endpoint that serves raw files from disk with correct MIME type.
- Uses `Content-Disposition: inline` so browsers display PDFs inline rather than downloading.
- Path traversal protection via `Path.resolve().relative_to()` validation.
- Resolves the repo root from the source config (handles both local and remote/cloned repos).

### PDF document category
- Added a `"pdf"` category to `get_document_tree()` in the knowledge base. PDF files are detected by file extension (checked first, before directory-based rules) and placed in their own category instead of ending up in `docs`.
- The tree API response now includes a `pdf` array per source alongside the existing categories.

### Tests
- 5 new ingestion tests: `parse_binary` metadata, nested paths, size guard, extension set, full PDF ingestion cycle.
- 3 new server tests: raw file serving, 404, path traversal blocked.
- 1 new knowledge base test: PDF files categorized separately from markdown docs.

## Design decisions

- PDFs are not searchable via vector search. The user explicitly asked for "view as-is" without search. This keeps the implementation simple and avoids pulling in PDF text extraction libraries.
- Content hash for change detection uses raw bytes (`file_path.read_bytes()`) rather than the empty content string, so PDFs are correctly re-indexed when the file changes on disk.
- The `/api/files/` endpoint is separate from `/api/documents/` because it serves binary content, not JSON metadata.
