# Quick Task 260325-5mi: 增加Rich Progress bar到async fetch

**Status:** ✅ Complete
**Date:** 2026-03-24
**Commit:** 33ea0e4

## Summary

Added Rich Progress bar to the async feed fetch, providing real-time visual feedback during concurrent feed fetching.

## Changes

### 1. `src/application/fetch.py`
- Converted `fetch_all_async()` from a regular async function to an **async generator**
- Uses `asyncio.as_completed()` instead of `asyncio.gather()` to yield results as each feed completes
- Each yield produces: `feed_id`, `feed_name`, `new_articles`, `error`

### 2. `src/cli/feed.py`
- Added Rich `Progress` bar with: `SpinnerColumn`, `TextColumn`, `BarColumn`, `TaskProgressColumn`, `TimeRemainingColumn`
- Progress updates in real-time showing:
  - Feed name + article count
  - Visual progress bar
  - Percentage complete
  - ETA
- Color-coded status: green (+articles), blue (up to date), red (error)
- Summary output after completion

## Verification

```
$ python -m src.cli fetch --all
  OpenAI News: +895 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00

✓ Fetched 4683 articles from 69 feeds, 1 errors
  - anthropics/claude-code / CHANGELOG.md: 'GitHubReleaseProvider' object has no attribute 'crawl_async'
```

## Known Issue

GitHubReleaseProvider does not implement `crawl_async` — causes error for GitHub URLs during async fetch. This is a pre-existing gap from v1.5 milestone.
