# Quick Task 260414-nek: 精简 src/cli/feed.py 和 src/cli/article.py

**Completed:** 2026-04-14

## Changes

### src/cli/feed.py

| Change | Before | After |
|--------|--------|-------|
| Unused function | `_fetch_with_progress` (8 lines) | Removed |
| Conditional imports | `cProfile`, `io`, `pstats` at module level | Lazy import inside `if profile:` block |
| Duplicate code | 3x identical `FeedMetaData(...)` construction | Extracted `_build_feed_meta()` helper |
| Import order | `from src.cli import cli` at line 95 | Moved to top with other imports |

**Net: -22 lines**

### src/cli/article.py

| Change | Before | After |
|--------|--------|-------|
| Imports | `datetime`, `get_timezone` inside `_format_date()` | Moved to module level |
| Helper position | `_print_content_view` at bottom of file | Moved before `article_view` command |

**Net: -0 lines (reorganization only)**

## Verification

- `git diff src/cli/` shows clean diff
- No functional changes — only structural improvements
- All imports verified correct after reordering

## Commit

`e38f832` — refactor(cli): 精简 feed.py 和 article.py
