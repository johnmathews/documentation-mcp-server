# Token Efficiency and SSE Streaming for Chat Endpoint

## Context

The `/api/chat` endpoint was hitting Anthropic's 30,000 input tokens per minute (ITPM)
rate limit, causing 502 errors in the webapp. Root cause: the agentic tool-use loop
resends the entire conversation (system prompt + tools + all messages) on each iteration,
and the system prompt included a full per-document inventory listing (~4,000-7,000 tokens)
that grew with every indexed file.

## Changes

### 1. Prompt Caching (highest impact)

Enabled Anthropic's prompt caching by structuring the system prompt as content blocks
with `cache_control: {"type": "ephemeral"}` on static instructions, and on the last
tool definition. Cached tokens are read at 0.1x cost and critically **do not count
toward ITPM rate limits**. This means the ~1,000 tokens of static content (instructions
+ tools) are only counted on the first API call per cache window (5 min TTL).

### 2. Compact Inventory Context (~95% reduction)

Replaced the per-document inventory listing with a compact per-source summary showing
only category counts. Before: every document across all sources listed with title, path,
dates, and size (~115 chars/doc x 130 docs = ~15,000 chars). After: per-source one-liner
with file count and category breakdown (~100 chars/source x 12 sources = ~1,200 chars).

The model now uses `query_docs` to find specific documents when needed, rather than
having the full listing in every system prompt.

### 3. Tool Result Truncation

- `search_docs`: default results 5->3, max 20->10, content truncated at 300 chars
- `query_docs`: max 100->20, returns only key fields (doc_id, title, source, file_path)
  instead of full metadata dump
- `get_document`: truncated at 6,000 chars (was unlimited)
- `list_sources`: compact JSON (no indent)

### 4. Agentic Loop Compaction

After each tool-use iteration, older tool result messages are replaced with short
summaries (`[Prior result: N chars]`). Only the most recent tool results remain
verbose. This prevents linear token accumulation across iterations.

### 5. Token Usage Logging

Each API response now logs input_tokens, output_tokens, cache_read_input_tokens,
and cache_creation_input_tokens. This provides operational visibility into whether
the optimizations are working.

### 6. Removed Document Embedding from System Prompt

The `current_doc_id` handling previously fetched the full document and embedded it
in the system prompt. Replaced with a short hint telling the model which document
the user is viewing, and it can use `get_document` if needed.

### 7. Rate Limit Error Handling

`RateLimitError` is now caught separately from generic `APIError`, returning a 429
with a user-friendly message instead of a confusing 502.

## Expected Impact

A 3-iteration tool-use loop should go from ~25,000 effective ITPM tokens to ~3,000-5,000
with caching + compact inventory. The rate limit errors should be eliminated.

## Decisions

- Did NOT switch to Haiku for routing — model switching breaks prompt cache sharing
  between iterations, negating the biggest optimization.
- Did NOT request an API tier upgrade — caching should reduce effective ITPM by 80%+.
- Kept `build_system_prompt()` function for test compatibility even though `api_chat`
  now builds content blocks directly.

---

## SSE Streaming for Tool-Use Progress

### Problem

The chat endpoint ran the entire agentic tool-use loop (potentially 30-60 seconds)
before returning a response. The user saw only a bouncing dots animation with no
visibility into what was happening.

### Solution

Added `/api/chat/stream` endpoint that returns Server-Sent Events during the loop.

**Event protocol:**
- `status` — thinking/iteration updates
- `tool_call` — before tool execution (tool name + input)
- `tool_result` — after execution (human-readable summary like "3 results found")
- `reply` — final response with conversation_id
- `error` — on failure mid-stream

**Architecture:**
- Backend: async generator yielding `ServerSentEvent` objects via `sse-starlette`
  (already a dependency). `asyncio.to_thread` wraps sync Anthropic API calls.
  15-second ping keep-alive prevents proxy timeouts.
- SvelteKit proxy: new `/api/chat/stream` route passes `ReadableStream` through
  without buffering.
- Frontend: `fetch()` + `ReadableStream` + manual SSE parsing (EventSource only
  supports GET, but we need POST with a body).

**Refactoring:**
- Extracted `_prepare_chat_request()` and `_ChatRequest` dataclass so both
  `/api/chat` and `/api/chat/stream` share request parsing logic.
- Added `_tool_result_summary()` for concise human-readable tool result descriptions.

### UI Changes (documentation-webapp)

ChatPanel now shows real-time tool progress:
- Spinning arrow + "Searching documentation" while a tool is active
- Checkmark + summary when complete (e.g., "3 results found")
- Thinking dots remain at the bottom throughout

### Decisions

- Kept `/api/chat` unchanged for backward compatibility. The webapp uses the new
  streaming endpoint; other clients can still use the JSON endpoint.
- Did not stream the final text response token-by-token — responses are short and
  markdown rendering mid-stream adds complexity for low payoff. The main UX win is
  tool-use progress visibility during the long wait.
