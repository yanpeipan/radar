# Quick Task 260328-3wa: Fix search display issues

## Summary

Fixed 3 display issues in `src/application/search.py`:

### Issue 1: Empty ID Column
- **Root cause**: `_format_fts_items` hardcoded `"id": ""` instead of `article.id`
- **Fix**: Changed to `"id": article_id[:8]` (matching `_format_list_items`)

### Issue 2: Garbled Format
- **Root cause**: Missing ID caused first column to be empty, breaking alignment
- **Fix**: Same as Issue 1 - ID now properly populated

### Issue 3: Date Format
- **Root cause**: RFC 2822 dates ("Thu, 26 Mar 2026") truncated to 10 chars became "Thu, 26 Ma"
- **Fix**: Added `_format_date_for_display()` function that parses RFC 2822 and ISO dates, converts to yyyy-mm-dd format

## Changes

- `src/application/search.py`:
  - Added `from email.utils import parsedate_to_datetime` import
  - Added `_format_date_for_display()` function
  - Updated `_format_list_items()` to use formatted date
  - Updated `_format_fts_items()` to use formatted date and correct ID
  - Updated docstring for `format_fts_results()`

## Verification

```
$ python -m src.cli search "CS"
ID | Title | Source | Date | Score
--------------------------------------------------------------------------------
5sC8MEAE | When Brain Foundation Model Meets Cauchy-Schwarz Divergence: | cs.LG updates o | 2026-03-26 | FTS
...
```

- All 9 `test_search.py` tests pass
- `test_article_search_found` CLI test passes
