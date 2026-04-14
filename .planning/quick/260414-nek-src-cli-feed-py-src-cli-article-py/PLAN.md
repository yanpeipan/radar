# Plan: Refactor feed.py and article.py

## Context

Both `src/cli/feed.py` and `src/cli/article.py` have structural issues:
- Misplaced imports (inline imports after code)
- Unused code
- Lazy imports mixed with eager imports
- Duplicate code patterns
- Poor import organization

## Tasks

### Task 1: Refactor feed.py

**File:** `src/cli/feed.py`

**Issues to fix:**
1. Move `from src.cli import cli` (line 95) to top with other third-party imports
2. Remove unused `_fetch_with_progress` function (lines 53-60)
3. Move `cProfile`, `io`, `pstats` imports inside the `if profile:` block (lines 9-12,1164-1183)
4. Extract duplicate FeedMetaData construction in `feed_add` (lines 207-212 and 258-263) into a helper

**Action:**
```python
# 1. Move cli import to top with other imports
# 2. Delete _fetch_with_progress (lines 53-60) - unused
# 3. Change top-level imports to lazy inside fetch() or profiling block:
#    - Remove cProfile, io, pstats from top
#    - Import them inside `if profile:` block
# 4. Create helper:
def _build_feed_meta(feed) -> FeedMetaData:
    """Build FeedMetaData from discovered feed."""
    return FeedMetaData(
        feed_type=feed.feed_type.value if hasattr(feed.feed_type, "value") else feed.feed_type,
        selectors=feed.metadata.selectors if feed.metadata else None,
    )
```

**Verify:** `uv run ruff check src/cli/feed.py --fix && uv run python -c "from src.cli.feed import feed, feed_add, feed_list, feed_remove, feed_update, feed_export, feed_import, fetch"` - no import errors

**Done:** FeedMetaData duplication eliminated, imports reorganized, unused function removed

---

### Task 2: Refactor article.py

**File:** `src/cli/article.py`

**Issues to fix:**
1. Move `datetime` import and `get_timezone` to module level in `_format_date` (currently inside function, lines 36-38)
2. Move `_print_content_view` helper function (lines 319-327) up before `article_view` command where it's used
3. Lazy import of `get_related_articles` is already correct placement - no change needed

**Action:**
```python
# At module level, add:
from datetime import datetime, timezone
from src.application.config import get_timezone

# Update _format_date to use module-level imports:
def _format_date(published_at: int | str | None) -> str:
    """Format published_at as 'YYYY-MM-DD' or return '-'."""
    if published_at is None:
        return "-"
    if isinstance(published_at, int):
        tz = get_timezone()
        dt = datetime.fromtimestamp(published_at, tz=tz)
        return dt.strftime("%Y-%m-%d")
    if isinstance(published_at, str):
        if len(published_at) >= 10:
            return published_at[:10]
        return published_at
    return "-"

# Move _print_content_view before article_view command definition
```

**Verify:** `uv run ruff check src/cli/article.py --fix && uv run python -c "from src.cli.article import article, article_list, article_view, article_open, article_search, article_related, article_mark, article_star"` - no import errors

**Done:** Imports moved to module level, helper function relocated

---

## Verification

Run after both tasks:
```bash
uv run ruff check src/cli/feed.py src/cli/article.py --fix
uv run ruff format src/cli/feed.py src/cli/article.py
```

## Artifacts
- Refactored `src/cli/feed.py`
- Refactored `src/cli/article.py`
