# Agentic Chat with Tool Use and Conversation Persistence

## What changed

The webapp chat agent was a single-shot RAG system: it stuffed 8 search results into the
system prompt and made one Claude API call. It also had no awareness of which page the user
was browsing when on `/source/[name]` or category pages (it explicitly set `currentDocId`
to null on those routes).

### Problem

When a user on `/source/m3` asked "what page am I looking at right now?", the agent replied
that it had no access to the current page. The frontend was clearing page context on source
and category routes, and the backend had no tool-use capability to research further.

### Changes

**1. Agentic tool-use loop (backend)**

Replaced the single-shot RAG pattern with a Claude API tool-use loop. The chat agent now has
4 tools: `search_docs`, `query_docs`, `get_document`, `list_sources`. When the model returns
`tool_use` blocks, the backend executes them against the KnowledgeBase, feeds results back,
and loops (up to 10 iterations). The system prompt was rewritten to encourage proactive
tool use and cross-source research.

**2. Page context on all routes (frontend + backend)**

Added `currentPageContext` store (source, category) alongside `currentDocId`. Source pages
set `{source: name}`, category pages set `{source, category}`. The backend builds appropriate
system prompt context: "The user is currently browsing the 'm3' source..."

**3. Conversation persistence (new module)**

Created `src/docserver/conversations.py` with `ConversationStore` backed by SQLite
(`conversations.db`). Every chat exchange is saved with title (auto-generated from first
message), page context, and full message history. New API endpoints:
`GET /api/conversations`, `GET /api/conversations/:id`, `DELETE /api/conversations/:id`.

**4. Conversation history UI (frontend)**

ChatPanel now has a clock icon that toggles a conversation history list. Users can browse
past conversations, click to resume, or delete them. The localStorage-based persistence
was replaced with server-side storage.

## Code review fixes

- Added `_safe_int` helper for model-controlled integer inputs (prevents ValueError/TypeError)
- Guarded against empty `tool_results` list in the agentic loop
- Changed conversation route from `:path` to default string converter
- Fixed conversation persistence to store full history, not just last 10 messages

## Files

- `src/docserver/server.py` - Agentic chat, tool definitions, conversation endpoints
- `src/docserver/conversations.py` - New conversation store module
- `tests/test_chat_prompt.py` - Updated + new tests for tools, _safe_int
- `tests/test_conversations.py` - 23 tests, 100% coverage on conversations module
- Frontend: stores, api, ChatPanel, source/category pages, layout, proxy routes
- `docs/architecture.md` - Updated endpoint docs
- `CLAUDE.md` - Added conversations module and architecture notes
