# Chat Logging and Endpoint Tests

**Date:** 2026-04-07

## Changes

### Enhanced chat request logging

Added structured logging to both `/api/chat` and `/api/chat/stream` endpoints:

- **Request entry**: logs user message preview (first 80 chars), conversation ID, model, and history length
- **Tool execution timing**: each tool call now includes duration in milliseconds
- **Request completion**: logs conversation ID, iteration count, total tool calls, reply length, and total duration in milliseconds

All log entries use structured `extra` fields for machine-parseable filtering (e.g., `event: chat_request`, `event: chat_stream_complete`, `event: chat_tool_call`).

### Chat endpoint HTTP tests

New test file `tests/test_chat_endpoint.py` with 16 tests covering:

- `/api/chat`: input validation, missing API key, simple reply, tool-use loop, rate limit error, CORS, conversation continuation
- `/api/chat/stream`: input validation, CORS, SSE event formatting, tool-use events, rate limit error events, generic error events
- `/api/conversations`: list, get, delete lifecycle

Uses `MagicMock(spec=TextBlock)` and `MagicMock(spec=ToolUseBlock)` to properly satisfy `isinstance()` checks in the agentic loop.

### Documentation updates

- `docs/operations.md`: added chat log events to the structured events table
- `docs/architecture.md`: updated logging section to describe chat request logging

## Context

The chat feature was working correctly on the backend but the frontend couldn't parse SSE events due to a CRLF line ending mismatch. While investigating, we identified that chat requests had minimal logging — no request entry/exit, no tool timing, no duration tracking. These gaps would make it difficult to debug production issues like slow responses, excessive tool calls, or API errors.
