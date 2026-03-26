# Engineering Team Directory Auto-Ingestion and Tree API Category

## Changes

### Ingestion (`ingestion.py`)
- Added auto-include logic for `.engineering-team/` and `documentation/` directories during file discovery
- These directories are always included even when custom glob patterns are specified, since they contain important project documentation
- Deduplicates against files already matched by glob patterns using `samefile()`

### Knowledge Base (`knowledge_base.py`)
- Added `engineering_team` as a new document category in `get_document_tree()`
- Files under `.engineering-team/` are categorized separately from regular docs
- Engineering team documents are sorted alphabetically by title

### Tests
- Added `test_get_files_includes_engineering_team` — verifies `.engineering-team/*.md` files are auto-included
- Added `test_get_files_includes_documentation_dir` — verifies `documentation/*.md` files are auto-included
- Added `test_get_document_tree_engineering_team` — verifies tree API categorizes `.engineering-team/` files correctly
- Updated existing tree test to assert `engineering_team` key exists (empty list)
