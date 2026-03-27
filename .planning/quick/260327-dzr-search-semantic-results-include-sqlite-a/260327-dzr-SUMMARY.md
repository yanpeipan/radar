---
quick_id: 260327-dzr
type: quick
slug: search-semantic-results-include-sqlite-a
phase: quick
plan: 260327-dzr
date: 2026-03-27
duration: ~5 minutes
tasks_completed: 3
---

# Quick Plan 260327-dzr: Add SQLite ID to Semantic Search Results - Summary

## Objective
Add SQLite article nanoid to semantic search results so users can copy IDs to use with `article related` and other commands.

## Tasks Completed

| # | Task | Commit | Files Modified |
|---|------|--------|----------------|
| 1 | Add get_article_id_by_url to sqlite.py | - | src/storage/sqlite.py, src/storage/__init__.py |
| 2 | Include sqlite_id in search_articles_semantic results | - | src/storage/vector.py |
| 3 | Display article ID in search --semantic CLI output | - | src/cli/article.py |

## Changes Made

### Task 1: Add get_article_id_by_url to sqlite.py
- Added `get_article_id_by_url(url: str) -> Optional[str]` function to `src/storage/sqlite.py` (line 626)
- Function queries `SELECT id FROM articles WHERE guid = ?` to resolve SQLite nanoid from article URL (guid)
- Exported from `src/storage/__init__.py`

### Task 2: Include sqlite_id in search_articles_semantic results
- Modified `search_articles_semantic()` in `src/storage/vector.py` (line 182-186)
- Added import of `get_article_id_by_url` inside the loop
- Added `"sqlite_id": sqlite_id` to returned dict
- Updated docstring to mention `sqlite_id` in return keys

### Task 3: Display article ID in search --semantic CLI output
- Modified `article_search()` in `src/cli/article.py` (lines 326-328, 336-337)
- Verbose mode: Shows `ID: {sqlite_id[:8]}` after title
- Non-verbose mode: Shows `{sqlite_id[:8]} | {title[:40]} | Similarity: {similarity}`

## Verification

```
grep -r "sqlite_id" src/storage/vector.py       # 3 matches
grep -r "get_article_id_by_url" src/storage/sqlite.py  # 1 match
grep -r "result.get..sqlite_id" src/cli/article.py      # 2 matches
```

## Success Criteria

- [x] `grep -r "sqlite_id" src/storage/vector.py` finds the new field
- [x] `grep -r "get_article_id_by_url" src/storage/sqlite.py` finds the helper function
- [x] `grep -r "result.get..sqlite_id" src/cli/article.py` finds the CLI display code
- [x] Semantic search results show article ID (8-char truncated)

## Deviations

None - plan executed exactly as written.

## Artifacts Created

- `.planning/quick/260327-dzr-search-semantic-results-include-sqlite-a/260327-dzr-SUMMARY.md`
