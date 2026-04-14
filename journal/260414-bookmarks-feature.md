# Bookmarks / Favourites Feature

## What Changed

Added the ability to bookmark/favourite documents across both the documentation server and webapp.

### Server (`documentation-server`)

- **New module `bookmarks.py`**: SQLite-backed `BookmarkStore` with `user_id` column for future multi-user support. Defaults to `"default"` user. Operations: add (idempotent), remove, list_all, is_bookmarked, bulk_check.
- **REST API endpoints**: GET/POST `/api/bookmarks`, POST `/api/bookmarks/check` (bulk status), DELETE `/api/bookmarks/{doc_id}`. The list endpoint enriches bookmarks with document metadata from the knowledge base.
- **MCP tool `get_bookmarks`**: Available to the chat agent so users can say "review my starred docs" or "look in my bookmarks" and the agent will fetch and use the bookmarked documents.
- **Chat system prompt updated**: Instructs the agent to use `get_bookmarks` when users mention bookmarks, starred docs, or favourites.
- **Separate database**: Bookmarks stored in `bookmarks.db` (not `documents.db`) following the same pattern as `conversations.db`.

### Webapp (`documentation-webapp`)

- **API proxy routes**: SvelteKit server routes proxy all bookmark endpoints to the backend. Added `proxyDelete` utility to `server/api.ts`.
- **Client API functions**: `listBookmarks`, `addBookmark`, `removeBookmark`, `checkBookmarks` in `api.ts`.
- **`BookmarkButton` component**: Toggle button with filled/outlined bookmark icon. Supports `small` and `normal` sizes. Prevents event propagation so it works inside clickable list items.
- **Document view**: Bookmark button in the doc header next to the source badge.
- **Category listings**: Small bookmark buttons on each document row, with bulk status check on page load.
- **`/bookmarks` page**: New top-level page grouped by source then category. Uses the masthead/breadcrumb pattern from the journal page.
- **Service nav**: "Bookmarks" link added to the top navigation bar.

## Key Decisions

- **Server-side storage** (not localStorage) so the chat agent can access bookmarks via a tool. This is the critical decision — without server-side storage, "review my starred docs" wouldn't work.
- **`user_id` column** added from the start to avoid a schema migration when multi-user support is added. Defaults to `"default"` everywhere.
- **Separate `bookmarks.db`** rather than adding a table to `documents.db` — follows the pattern of `conversations.db` and keeps concerns isolated.
- **Bulk check endpoint** (`POST /api/bookmarks/check`) to avoid N+1 requests when rendering document listings with bookmark status.
- **Tags/labels deferred** to next phase — the `created_at` (bookmarked date) is the only metadata for now.

## Test Coverage

- **Server**: 20 unit tests for `BookmarkStore`, 9 endpoint tests, 2 MCP tool tests. All 364 tests pass.
- **Webapp**: 4 API function tests added. All 194 tests pass (2 pre-existing failures unrelated to bookmarks).
