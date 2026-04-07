"""Tests for server-side conversation persistence."""

import os

import pytest

from docserver.conversations import ConversationStore, _generate_title


@pytest.fixture
def store(tmp_path):
    """Create a ConversationStore backed by a temp directory."""
    return ConversationStore(str(tmp_path))


@pytest.fixture
def sample_messages():
    return [
        {"role": "user", "content": "What is m3?"},
        {"role": "assistant", "content": "M3 is a monitoring service."},
    ]


# ---- _generate_title --------------------------------------------------------


class TestGenerateTitle:
    def test_uses_first_user_message(self):
        messages = [
            {"role": "user", "content": "Hello world"},
            {"role": "assistant", "content": "Hi there"},
        ]
        assert _generate_title(messages) == "Hello world"

    def test_truncates_long_messages(self):
        long_msg = "x" * 100
        messages = [{"role": "user", "content": long_msg}]
        title = _generate_title(messages)
        assert len(title) == 60
        assert title.endswith("...")

    def test_short_message_not_truncated(self):
        messages = [{"role": "user", "content": "Short question"}]
        assert _generate_title(messages) == "Short question"

    def test_exactly_60_chars_not_truncated(self):
        msg = "x" * 60
        messages = [{"role": "user", "content": msg}]
        assert _generate_title(messages) == msg

    def test_no_user_message(self):
        messages = [{"role": "assistant", "content": "Hello"}]
        assert _generate_title(messages) == "Untitled conversation"

    def test_empty_messages(self):
        assert _generate_title([]) == "Untitled conversation"


# ---- ConversationStore -------------------------------------------------------


class TestConversationStore:
    def test_create_returns_id(self, store, sample_messages):
        conv_id = store.create(sample_messages)
        assert isinstance(conv_id, str)
        assert len(conv_id) == 12

    def test_get_returns_conversation(self, store, sample_messages):
        conv_id = store.create(sample_messages)
        conv = store.get(conv_id)
        assert conv is not None
        assert conv["id"] == conv_id
        assert conv["title"] == "What is m3?"
        assert conv["messages"] == sample_messages
        assert conv["created_at"] is not None
        assert conv["updated_at"] is not None

    def test_get_missing_returns_none(self, store):
        assert store.get("nonexistent") is None

    def test_create_with_page_context(self, store, sample_messages):
        ctx = {"source": "m3", "category": "journal"}
        conv_id = store.create(sample_messages, page_context=ctx)
        conv = store.get(conv_id)
        assert conv is not None
        assert conv["page_context"] == ctx

    def test_create_without_page_context(self, store, sample_messages):
        conv_id = store.create(sample_messages)
        conv = store.get(conv_id)
        assert conv is not None
        assert conv["page_context"] is None

    def test_update_messages(self, store, sample_messages):
        conv_id = store.create(sample_messages)
        extended = [
            *sample_messages,
            {"role": "user", "content": "Tell me more"},
            {"role": "assistant", "content": "Sure, here's more info."},
        ]
        assert store.update(conv_id, extended) is True
        conv = store.get(conv_id)
        assert conv is not None
        assert len(conv["messages"]) == 4

    def test_update_missing_returns_false(self, store):
        assert store.update("nonexistent", []) is False

    def test_update_with_page_context(self, store, sample_messages):
        conv_id = store.create(sample_messages)
        ctx = {"source": "m3"}
        store.update(conv_id, sample_messages, page_context=ctx)
        conv = store.get(conv_id)
        assert conv is not None
        assert conv["page_context"] == ctx

    def test_list_all_returns_summaries(self, store, sample_messages):
        store.create(sample_messages)
        store.create([{"role": "user", "content": "Second conversation"}])
        convs = store.list_all()
        assert len(convs) == 2
        # Most recent first
        assert convs[0]["title"] == "Second conversation"
        assert convs[1]["title"] == "What is m3?"

    def test_list_all_includes_message_count(self, store, sample_messages):
        store.create(sample_messages)
        convs = store.list_all()
        assert convs[0]["message_count"] == 2

    def test_list_all_includes_preview(self, store, sample_messages):
        store.create(sample_messages)
        convs = store.list_all()
        assert "M3 is a monitoring service" in convs[0]["preview"]

    def test_list_all_empty(self, store):
        assert store.list_all() == []

    def test_list_all_respects_limit(self, store):
        for i in range(5):
            store.create([{"role": "user", "content": f"Conv {i}"}])
        assert len(store.list_all(limit=3)) == 3

    def test_delete_existing(self, store, sample_messages):
        conv_id = store.create(sample_messages)
        assert store.delete(conv_id) is True
        assert store.get(conv_id) is None

    def test_delete_missing(self, store):
        assert store.delete("nonexistent") is False

    def test_db_file_created(self, tmp_path):
        ConversationStore(str(tmp_path))
        assert os.path.exists(os.path.join(str(tmp_path), "conversations.db"))

    def test_multiple_stores_same_dir(self, tmp_path, sample_messages):
        """Two stores pointing to the same dir share data."""
        store1 = ConversationStore(str(tmp_path))
        conv_id = store1.create(sample_messages)
        store2 = ConversationStore(str(tmp_path))
        conv = store2.get(conv_id)
        assert conv is not None
        assert conv["title"] == "What is m3?"
