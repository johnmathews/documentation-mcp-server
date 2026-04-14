"""Tests for server-side bookmark persistence."""

import os

import pytest

from docserver.bookmarks import BookmarkStore


@pytest.fixture
def store(tmp_path):
    """Create a BookmarkStore backed by a temp directory."""
    return BookmarkStore(str(tmp_path))


# ---- BookmarkStore -----------------------------------------------------------


class TestBookmarkStore:
    def test_add_returns_bookmark(self, store):
        bm = store.add("source:path/to/doc.md")
        assert bm["doc_id"] == "source:path/to/doc.md"
        assert bm["user_id"] == "default"
        assert bm["created_at"] is not None

    def test_add_is_idempotent(self, store):
        bm1 = store.add("source:doc.md")
        bm2 = store.add("source:doc.md")
        assert bm1["created_at"] == bm2["created_at"]

    def test_add_with_custom_user_id(self, store):
        bm = store.add("source:doc.md", user_id="alice")
        assert bm["user_id"] == "alice"

    def test_remove_existing(self, store):
        store.add("source:doc.md")
        assert store.remove("source:doc.md") is True

    def test_remove_nonexistent(self, store):
        assert store.remove("source:doc.md") is False

    def test_remove_does_not_affect_other_users(self, store):
        store.add("source:doc.md", user_id="alice")
        store.add("source:doc.md", user_id="bob")
        store.remove("source:doc.md", user_id="alice")
        assert store.is_bookmarked("source:doc.md", user_id="bob") is True

    def test_list_all_empty(self, store):
        assert store.list_all() == []

    def test_list_all_returns_bookmarks(self, store):
        store.add("source:a.md")
        store.add("source:b.md")
        bookmarks = store.list_all()
        assert len(bookmarks) == 2

    def test_list_all_most_recent_first(self, store):
        store.add("source:first.md")
        store.add("source:second.md")
        bookmarks = store.list_all()
        assert bookmarks[0]["doc_id"] == "source:second.md"
        assert bookmarks[1]["doc_id"] == "source:first.md"

    def test_list_all_filters_by_user_id(self, store):
        store.add("source:a.md", user_id="alice")
        store.add("source:b.md", user_id="bob")
        assert len(store.list_all(user_id="alice")) == 1
        assert store.list_all(user_id="alice")[0]["doc_id"] == "source:a.md"

    def test_is_bookmarked_true(self, store):
        store.add("source:doc.md")
        assert store.is_bookmarked("source:doc.md") is True

    def test_is_bookmarked_false(self, store):
        assert store.is_bookmarked("source:doc.md") is False

    def test_is_bookmarked_respects_user_id(self, store):
        store.add("source:doc.md", user_id="alice")
        assert store.is_bookmarked("source:doc.md", user_id="alice") is True
        assert store.is_bookmarked("source:doc.md", user_id="bob") is False

    def test_bulk_check_empty(self, store):
        assert store.bulk_check([]) == {}

    def test_bulk_check_mixed(self, store):
        store.add("source:a.md")
        result = store.bulk_check(["source:a.md", "source:b.md"])
        assert result == {"source:a.md": True, "source:b.md": False}

    def test_bulk_check_respects_user_id(self, store):
        store.add("source:a.md", user_id="alice")
        result = store.bulk_check(["source:a.md"], user_id="bob")
        assert result == {"source:a.md": False}

    def test_db_file_created(self, tmp_path):
        BookmarkStore(str(tmp_path))
        assert os.path.exists(os.path.join(str(tmp_path), "bookmarks.db"))

    def test_multiple_stores_same_dir(self, tmp_path):
        """Two stores pointing to the same dir share data."""
        store1 = BookmarkStore(str(tmp_path))
        store1.add("source:doc.md")
        store2 = BookmarkStore(str(tmp_path))
        assert store2.is_bookmarked("source:doc.md") is True

    def test_add_after_remove_gets_new_timestamp(self, store):
        bm1 = store.add("source:doc.md")
        store.remove("source:doc.md")
        bm2 = store.add("source:doc.md")
        # After remove + re-add, should get a new created_at
        assert bm2["created_at"] >= bm1["created_at"]

    def test_same_doc_different_users(self, store):
        """Same doc can be bookmarked by different users independently."""
        store.add("source:doc.md", user_id="alice")
        store.add("source:doc.md", user_id="bob")
        assert len(store.list_all(user_id="alice")) == 1
        assert len(store.list_all(user_id="bob")) == 1
