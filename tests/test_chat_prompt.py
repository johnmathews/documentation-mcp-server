"""Tests for chat prompt building functions.

These test the pure functions that construct the system prompt for the chat
endpoint, ensuring the agent receives the right context to answer meta
questions about indexing status, document counts, and source inventory.
"""


from docserver.server import (
    CHAT_SYSTEM_INSTRUCTIONS,
    CHAT_TOOLS,
    _execute_chat_tool,
    _safe_int,
    build_inventory_context,
    build_system_prompt,
)

# ---- Fixtures ---------------------------------------------------------------


def _make_tree(
    *,
    sources: list[str] | None = None,
    with_root_docs: bool = True,
    with_engineering: bool = True,
    with_skills: bool = False,
    with_runbooks: bool = False,
) -> list[dict]:
    """Build a minimal doc_tree fixture."""
    if sources is None:
        sources = ["home-server", "timer-app"]

    tree = []
    for src in sources:
        entry: dict = {
            "source": src,
            "root_docs": [],
            "docs": [
                {
                    "title": "Setup Guide",
                    "file_path": "docs/setup.md",
                    "created_at": "2025-06-15T10:00:00+00:00",
                    "modified_at": "2026-03-01T12:00:00+00:00",
                    "size_bytes": 4200,
                },
                {
                    "title": "Architecture",
                    "file_path": "docs/architecture.md",
                    "created_at": "2025-08-20T14:30:00+00:00",
                    "modified_at": "2026-03-15T09:00:00+00:00",
                    "size_bytes": 8500,
                },
            ],
            "journal": [
                {
                    "title": "Initial commit",
                    "file_path": "journal/260101-init.md",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "modified_at": "2026-01-01T00:00:00+00:00",
                    "size_bytes": 1200,
                },
            ],
        }
        if with_root_docs:
            entry["root_docs"] = [
                {"title": None, "file_path": "README.md", "created_at": "2025-01-01T00:00:00+00:00", "modified_at": "2026-03-28T10:00:00+00:00", "size_bytes": 3000},
                {"title": None, "file_path": "CLAUDE.md", "created_at": "2025-11-01T00:00:00+00:00", "modified_at": "2026-03-20T10:00:00+00:00", "size_bytes": 1500},
            ]
        if with_engineering:
            entry["engineering_team"] = [
                {"title": "Eval Report", "file_path": ".engineering-team/evaluation-report.md", "created_at": "2026-03-25T00:00:00+00:00", "modified_at": "2026-03-25T22:00:00+00:00", "size_bytes": 13000},
            ]
        if with_skills:
            entry["skills"] = [
                {"title": "Weather Skill", "file_path": "container/skills/weather/skill.md", "created_at": "2026-03-20T00:00:00+00:00", "modified_at": "2026-03-20T00:00:00+00:00", "size_bytes": 2000},
                {"title": "Calendar Skill", "file_path": "container/skills/calendar/skill.md", "created_at": "2026-03-21T00:00:00+00:00", "modified_at": "2026-03-21T00:00:00+00:00", "size_bytes": 1800},
            ]
        if with_runbooks:
            entry["runbooks"] = [
                {"title": "Deploy Guide", "file_path": "runbooks/deploy-guide.md", "created_at": "2026-03-18T00:00:00+00:00", "modified_at": "2026-03-18T00:00:00+00:00", "size_bytes": 3500},
            ]
        tree.append(entry)
    return tree


def _make_stats(sources: list[str] | None = None) -> dict[str, dict]:
    """Build a source_stats fixture keyed by source name."""
    if sources is None:
        sources = ["home-server", "timer-app"]
    return {
        src: {
            "source": src,
            "file_count": 10 + i * 5,
            "chunk_count": 30 + i * 15,
            "last_indexed": f"2026-03-28T12:00:0{i}+00:00",
        }
        for i, src in enumerate(sources)
    }


# ---- CHAT_SYSTEM_INSTRUCTIONS ------------------------------------------------


class TestSystemInstructions:
    """Verify the system instructions contain critical phrases."""

    def test_identifies_as_documentation_assistant(self):
        assert "documentation assistant" in CHAT_SYSTEM_INSTRUCTIONS

    def test_mentions_inventory(self):
        assert "inventory" in CHAT_SYSTEM_INSTRUCTIONS

    def test_mentions_tools(self):
        assert "search_docs" in CHAT_SYSTEM_INSTRUCTIONS
        assert "query_docs" in CHAT_SYSTEM_INSTRUCTIONS
        assert "get_document" in CHAT_SYSTEM_INSTRUCTIONS

    def test_encourages_proactive_search(self):
        assert "Search proactively" in CHAT_SYSTEM_INSTRUCTIONS

    def test_mentions_unified_server(self):
        assert "unified documentation server" in CHAT_SYSTEM_INSTRUCTIONS

    def test_mentions_structural_questions(self):
        assert "structural questions" in CHAT_SYSTEM_INSTRUCTIONS

    def test_mentions_journal_dates(self):
        assert "most recent journal entry" in CHAT_SYSTEM_INSTRUCTIONS


# ---- build_inventory_context -------------------------------------------------


class TestBuildInventoryContext:
    """Test the inventory context builder."""

    def test_includes_source_count(self):
        tree = _make_tree()
        stats = _make_stats()
        result = build_inventory_context(tree, stats)
        assert "2 sources" in result

    def test_includes_total_file_count(self):
        tree = _make_tree()
        stats = _make_stats()
        result = build_inventory_context(tree, stats)
        # 10 + 15 = 25
        assert "25 files" in result

    def test_includes_total_chunk_count(self):
        tree = _make_tree()
        stats = _make_stats()
        result = build_inventory_context(tree, stats)
        # 30 + 45 = 75
        assert "75 vector chunks" in result

    def test_includes_per_source_stats(self):
        tree = _make_tree()
        stats = _make_stats()
        result = build_inventory_context(tree, stats)
        assert "**home-server** (10 files, 30 chunks" in result
        assert "**timer-app** (15 files, 45 chunks" in result

    def test_includes_last_indexed_timestamp(self):
        tree = _make_tree()
        stats = _make_stats()
        result = build_inventory_context(tree, stats)
        assert "2026-03-28T12:00:00+00:00" in result

    def test_includes_root_docs_category(self):
        tree = _make_tree(with_root_docs=True)
        stats = _make_stats()
        result = build_inventory_context(tree, stats)
        assert "Root docs (2)" in result
        assert "README.md" in result
        assert "CLAUDE.md" in result

    def test_includes_documentation_category(self):
        tree = _make_tree()
        stats = _make_stats()
        result = build_inventory_context(tree, stats)
        assert "Documentation (2)" in result
        assert "Setup Guide" in result
        assert "Architecture" in result

    def test_includes_journal_category(self):
        tree = _make_tree()
        stats = _make_stats()
        result = build_inventory_context(tree, stats)
        assert "Journal (1)" in result
        assert "Initial commit" in result

    def test_includes_engineering_team_category(self):
        tree = _make_tree(with_engineering=True)
        stats = _make_stats()
        result = build_inventory_context(tree, stats)
        assert "Engineering team (1)" in result
        assert "Eval Report" in result

    def test_includes_skills_category(self):
        tree = _make_tree(with_skills=True)
        stats = _make_stats()
        result = build_inventory_context(tree, stats)
        assert "Skills (2)" in result
        assert "Weather Skill" in result
        assert "Calendar Skill" in result

    def test_includes_runbooks_category(self):
        tree = _make_tree(with_runbooks=True)
        stats = _make_stats()
        result = build_inventory_context(tree, stats)
        assert "Runbooks (1)" in result
        assert "Deploy Guide" in result

    def test_includes_created_at_dates(self):
        tree = _make_tree()
        stats = _make_stats()
        result = build_inventory_context(tree, stats)
        assert "created=2025-06-15T10:00:00+00:00" in result  # Setup Guide
        assert "created=2026-01-01T00:00:00+00:00" in result  # Initial commit

    def test_includes_modified_at_dates(self):
        tree = _make_tree()
        stats = _make_stats()
        result = build_inventory_context(tree, stats)
        assert "modified=2026-03-01T12:00:00+00:00" in result  # Setup Guide

    def test_includes_size_bytes(self):
        tree = _make_tree()
        stats = _make_stats()
        result = build_inventory_context(tree, stats)
        assert "size=4200b" in result  # Setup Guide
        assert "size=8500b" in result  # Architecture

    def test_includes_file_path_when_title_present(self):
        tree = _make_tree()
        stats = _make_stats()
        result = build_inventory_context(tree, stats)
        assert "path=docs/setup.md" in result
        assert "path=docs/architecture.md" in result

    def test_doc_without_dates_omits_date_fields(self):
        tree = [{
            "source": "test",
            "root_docs": [],
            "docs": [{"title": "No Dates", "file_path": "docs/nodates.md"}],
            "journal": [],
        }]
        stats = _make_stats(sources=["test"])
        result = build_inventory_context(tree, stats)
        assert "No Dates" in result
        assert "created=" not in result
        assert "modified=" not in result

    def test_omits_empty_root_docs(self):
        tree = _make_tree(with_root_docs=False)
        stats = _make_stats()
        result = build_inventory_context(tree, stats)
        assert "Root docs" not in result

    def test_omits_empty_engineering_team(self):
        tree = _make_tree(with_engineering=False)
        stats = _make_stats()
        result = build_inventory_context(tree, stats)
        assert "Engineering team" not in result

    def test_missing_engineering_team_key(self):
        """Tree entries without engineering_team key should not crash."""
        tree = _make_tree()
        for src in tree:
            del src["engineering_team"]
        stats = _make_stats()
        result = build_inventory_context(tree, stats)
        assert "Engineering team" not in result

    def test_source_not_in_stats_shows_zeros(self):
        tree = _make_tree(sources=["unknown-source"])
        stats = {}  # No stats at all
        result = build_inventory_context(tree, stats)
        assert "**unknown-source** (0 files, 0 chunks, last indexed: never)" in result

    def test_fallback_to_file_path_when_title_is_none(self):
        tree = [{
            "source": "test",
            "root_docs": [],
            "docs": [{"title": None, "file_path": "docs/no-title.md"}],
            "journal": [],
        }]
        stats = _make_stats(sources=["test"])
        result = build_inventory_context(tree, stats)
        assert "docs/no-title.md" in result

    def test_empty_tree(self):
        result = build_inventory_context([], {})
        assert "0 sources" in result
        assert "0 files" in result
        assert "0 vector chunks" in result

    def test_single_source(self):
        tree = _make_tree(sources=["solo"])
        stats = _make_stats(sources=["solo"])
        result = build_inventory_context(tree, stats)
        assert "1 sources" in result
        assert "**solo**" in result


# ---- build_system_prompt -----------------------------------------------------


class TestBuildSystemPrompt:
    """Test the full system prompt assembly."""

    def test_starts_with_instructions(self):
        prompt = build_system_prompt([])
        assert prompt.startswith(CHAT_SYSTEM_INSTRUCTIONS)

    def test_no_context_parts_returns_instructions_only(self):
        prompt = build_system_prompt([])
        assert prompt == CHAT_SYSTEM_INSTRUCTIONS

    def test_context_parts_appended_after_separator(self):
        prompt = build_system_prompt(["Part one", "Part two"])
        assert CHAT_SYSTEM_INSTRUCTIONS in prompt
        assert "Part one" in prompt
        assert "Part two" in prompt

    def test_context_parts_separated_by_hr(self):
        prompt = build_system_prompt(["AAA", "BBB"])
        # Parts should be separated by ---
        assert "AAA\n\n---\n\nBBB" in prompt

    def test_instructions_separated_from_context(self):
        prompt = build_system_prompt(["Context here"])
        # There should be a double newline between instructions and context
        idx = prompt.index("Context here")
        before = prompt[:idx]
        assert before.endswith("\n\n")

    def test_full_prompt_with_inventory(self):
        """Integration: build inventory, then full prompt, verify key data present."""
        tree = _make_tree()
        stats = _make_stats()
        inventory = build_inventory_context(tree, stats)
        prompt = build_system_prompt([inventory])

        # Instructions present
        assert "documentation assistant" in prompt
        assert "Search proactively" in prompt

        # Inventory data present
        assert "2 sources" in prompt
        assert "**home-server**" in prompt
        assert "10 files" in prompt
        assert "30 chunks" in prompt
        assert "Root docs (2)" in prompt
        assert "Journal (1)" in prompt

    def test_full_prompt_with_inventory_and_rag(self):
        """Inventory + RAG context both appear in final prompt."""
        tree = _make_tree(sources=["myrepo"])
        stats = _make_stats(sources=["myrepo"])
        inventory = build_inventory_context(tree, stats)
        rag = "Relevant documentation excerpts:\n\nSome search result content here."
        prompt = build_system_prompt([inventory, rag])

        assert "**myrepo**" in prompt
        assert "Some search result content here" in prompt
        # Both separated by ---
        assert "---" in prompt

    def test_page_context_source_only(self):
        """Page context with source only produces correct context."""
        inventory = build_inventory_context([], {})
        ctx = (
            "The user is currently browsing the 'm3' source "
            "overview page. Use your tools to look up documents in this "
            "source if relevant to the user's question."
        )
        prompt = build_system_prompt([inventory, ctx])
        assert "'m3' source" in prompt

    def test_page_context_source_and_category(self):
        """Page context with source and category produces correct context."""
        inventory = build_inventory_context([], {})
        ctx = (
            "The user is currently browsing the 'journal' category "
            "within the 'm3' source. Use your tools to look up "
            "documents in this source if relevant to the user's question."
        )
        prompt = build_system_prompt([inventory, ctx])
        assert "'journal' category" in prompt
        assert "'m3' source" in prompt


# ---- CHAT_TOOLS -------------------------------------------------------------


class TestChatTools:
    """Verify the chat tool definitions are well-formed."""

    def test_has_four_tools(self):
        assert len(CHAT_TOOLS) == 4

    def test_tool_names(self):
        names = {t["name"] for t in CHAT_TOOLS}
        assert names == {"search_docs", "query_docs", "get_document", "list_sources"}

    def test_all_tools_have_required_fields(self):
        for tool in CHAT_TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"

    def test_search_docs_requires_query(self):
        search = next(t for t in CHAT_TOOLS if t["name"] == "search_docs")
        assert "query" in search["input_schema"]["required"]

    def test_get_document_requires_doc_id(self):
        get_doc = next(t for t in CHAT_TOOLS if t["name"] == "get_document")
        assert "doc_id" in get_doc["input_schema"]["required"]


# ---- _execute_chat_tool -----------------------------------------------------


class TestExecuteChatTool:
    """Test the chat tool executor with a mock KnowledgeBase."""

    class MockKB:
        """Minimal mock for KnowledgeBase methods used by _execute_chat_tool."""

        def search(self, *, query: str, n_results: int, source_filter: str | None = None):
            if query == "empty":
                return []
            return [
                {
                    "content": f"Result for: {query}",
                    "score": 0.95,
                    "metadata": {
                        "title": "Test Doc",
                        "source": "test-source",
                        "file_path": "docs/test.md",
                    },
                }
            ]

        def query_documents(self, **kwargs):
            if kwargs.get("source") == "empty":
                return []
            return [{"doc_id": "test:docs/test.md", "title": "Test Doc"}]

        def get_document(self, doc_id: str):
            if doc_id == "missing:doc":
                return None
            return {"doc_id": doc_id, "title": "Found", "content": "Content here"}

        def get_sources_summary(self):
            return [{"source": "test-source", "file_count": 5, "chunk_count": 20}]

    def test_search_docs_returns_results(self):
        kb = self.MockKB()
        result = _execute_chat_tool(kb, "search_docs", {"query": "hello"})  # type: ignore[arg-type]
        assert "Test Doc" in result
        assert "Result for: hello" in result

    def test_search_docs_empty(self):
        kb = self.MockKB()
        result = _execute_chat_tool(kb, "search_docs", {"query": "empty"})  # type: ignore[arg-type]
        assert "No matching documents found" in result

    def test_query_docs_returns_results(self):
        kb = self.MockKB()
        result = _execute_chat_tool(kb, "query_docs", {"source": "test"})  # type: ignore[arg-type]
        assert "Test Doc" in result

    def test_query_docs_empty(self):
        kb = self.MockKB()
        result = _execute_chat_tool(kb, "query_docs", {"source": "empty"})  # type: ignore[arg-type]
        assert "No matching documents found" in result

    def test_get_document_found(self):
        kb = self.MockKB()
        result = _execute_chat_tool(kb, "get_document", {"doc_id": "test:docs/test.md"})  # type: ignore[arg-type]
        assert "Found" in result
        assert "Content here" in result

    def test_get_document_not_found(self):
        kb = self.MockKB()
        result = _execute_chat_tool(kb, "get_document", {"doc_id": "missing:doc"})  # type: ignore[arg-type]
        assert "not found" in result

    def test_list_sources(self):
        kb = self.MockKB()
        result = _execute_chat_tool(kb, "list_sources", {})  # type: ignore[arg-type]
        assert "test-source" in result
        assert "5" in result

    def test_unknown_tool(self):
        kb = self.MockKB()
        result = _execute_chat_tool(kb, "nonexistent", {})  # type: ignore[arg-type]
        assert "Unknown tool" in result

    def test_search_docs_invalid_num_results(self):
        """Non-numeric num_results falls back to default without crashing."""
        kb = self.MockKB()
        result = _execute_chat_tool(kb, "search_docs", {"query": "hello", "num_results": "five"})  # type: ignore[arg-type]
        assert "Test Doc" in result

    def test_query_docs_invalid_limit(self):
        """Non-numeric limit falls back to default without crashing."""
        kb = self.MockKB()
        result = _execute_chat_tool(kb, "query_docs", {"source": "test", "limit": None})  # type: ignore[arg-type]
        assert "Test Doc" in result


# ---- _safe_int ---------------------------------------------------------------


class TestSafeInt:
    def test_valid_int(self):
        assert _safe_int(10, default=5, lo=1, hi=20) == 10

    def test_string_number(self):
        assert _safe_int("10", default=5, lo=1, hi=20) == 10

    def test_none_returns_default(self):
        assert _safe_int(None, default=5, lo=1, hi=20) == 5

    def test_invalid_string_returns_default(self):
        assert _safe_int("five", default=5, lo=1, hi=20) == 5

    def test_clamped_low(self):
        assert _safe_int(0, default=5, lo=1, hi=20) == 1

    def test_clamped_high(self):
        assert _safe_int(100, default=5, lo=1, hi=20) == 20
