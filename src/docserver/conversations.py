"""Server-side conversation persistence for the chat agent.

Stores chat conversations in SQLite so they can be reviewed, resumed,
and used to improve the chat experience over time.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class ConversationSummary(TypedDict):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    preview: str


class Conversation(TypedDict):
    id: str
    title: str
    created_at: str
    updated_at: str
    page_context: dict[str, str] | None
    messages: list[dict[str, str]]


def _generate_title(messages: list[dict[str, str]]) -> str:
    """Generate a conversation title from the first user message."""
    for msg in messages:
        if msg.get("role") == "user":
            text = msg["content"].strip()
            if len(text) <= 60:
                return text
            return text[:57] + "..."
    return "Untitled conversation"


class ConversationStore:
    """SQLite-backed conversation storage."""

    def __init__(self, data_dir: str) -> None:
        import os

        os.makedirs(data_dir, exist_ok=True)
        self.db_path = os.path.join(data_dir, "conversations.db")
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    page_context TEXT,
                    messages TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_conv_updated "
                "ON conversations(updated_at DESC)"
            )

    def create(
        self,
        messages: list[dict[str, str]],
        page_context: dict[str, str] | None = None,
    ) -> str:
        """Create a new conversation. Returns the conversation ID."""
        conv_id = uuid.uuid4().hex[:12]
        now = datetime.now(UTC).isoformat()
        title = _generate_title(messages)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at, page_context, messages) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    conv_id,
                    title,
                    now,
                    now,
                    json.dumps(page_context) if page_context else None,
                    json.dumps(messages),
                ),
            )
        logger.info(
            "Created conversation %s: %s",
            conv_id,
            title,
            extra={"event": "conversation_create", "conversation_id": conv_id},
        )
        return conv_id

    def update(
        self,
        conv_id: str,
        messages: list[dict[str, str]],
        page_context: dict[str, str] | None = None,
    ) -> bool:
        """Update conversation messages. Returns False if not found."""
        now = datetime.now(UTC).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE conversations SET messages = ?, updated_at = ?, page_context = COALESCE(?, page_context) "
                "WHERE id = ?",
                (
                    json.dumps(messages),
                    now,
                    json.dumps(page_context) if page_context else None,
                    conv_id,
                ),
            )
            return cursor.rowcount > 0

    def get(self, conv_id: str) -> Conversation | None:
        """Get a conversation by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT id, title, created_at, updated_at, page_context, messages "
                "FROM conversations WHERE id = ?",
                (conv_id,),
            ).fetchone()
            if row is None:
                return None
            return Conversation(
                id=row["id"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                page_context=json.loads(row["page_context"]) if row["page_context"] else None,
                messages=json.loads(row["messages"]),
            )

    def list_all(self, limit: int = 50) -> list[ConversationSummary]:
        """List conversations, most recent first."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, title, created_at, updated_at, messages "
                "FROM conversations ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

        result: list[ConversationSummary] = []
        for row in rows:
            messages: list[dict[str, Any]] = json.loads(row["messages"])  # pyright: ignore[reportExplicitAny]
            # Preview: last assistant message, truncated
            preview = ""
            for msg in reversed(messages):
                if msg.get("role") == "assistant":
                    text = msg["content"].strip()
                    preview = text[:100] + "..." if len(text) > 100 else text
                    break

            result.append(
                ConversationSummary(
                    id=row["id"],
                    title=row["title"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    message_count=len(messages),
                    preview=preview,
                )
            )
        return result

    def delete(self, conv_id: str) -> bool:
        """Delete a conversation. Returns False if not found."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            return cursor.rowcount > 0

    def close(self) -> None:
        """No-op — connections are opened per-call."""
