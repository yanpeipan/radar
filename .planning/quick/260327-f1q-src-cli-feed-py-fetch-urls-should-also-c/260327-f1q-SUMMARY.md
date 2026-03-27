---
phase: quick
plan: "260327-f1q"
subsystem: cli
tags:
  - async
  - fetch
  - embeddings
key_links:
  - from: src/cli/feed.py (fetch command)
    to: src/application/fetch.py (fetch_url_async)
    via: async loop for URL processing
tech_stack:
  added:
    - asyncio.Semaphore for concurrency limiting
    - uvloop event loop
  patterns:
    - Async generator with asyncio.as_completed() for progress tracking
    - Rich Progress bar for user feedback
decisions:
  - Used same async pattern as --all case for consistency
  - fetch_url_async mirrors fetch_one_async logic but for raw URLs
---

# Quick Task 260327-f1q: Async URL Fetch with Storage/Embedding/Tagging

## One-liner

Refactored `fetch` command URL case to use async loop with article storage, embedding generation, and tag rule application.

## Changes

### Modified Files

**src/cli/feed.py**
- Added `asyncio` import
- Replaced synchronous `crawl_url` loop with async approach using `fetch_url_async`
- URL case now uses Rich Progress bar (same pattern as `--all`)
- Concurrency limited via `asyncio.Semaphore`

**src/application/fetch.py**
- Added `fetch_url_async(url: str)` function
- Uses `discover_or_default` to find provider for URL
- Calls `provider.crawl_async()` to get raw items
- Stores articles via `store_article_async`
- Generates embeddings via `add_article_embedding`
- Applies tag rules via `apply_rules_to_article`

## Truths Achieved

- [x] URLs passed to fetch command are processed through async loop
- [x] Articles from URLs are stored to database
- [x] Embeddings are generated for URL-fetched articles
- [x] Tag rules are applied to URL-fetched articles
- [x] Rich progress bar shows during URL fetch

## Verification

- `crawl_url` no longer imported in feed.py fetch command
- Syntax check passed for both modified files
- Commit: `b0408f7`

## Deviations from Plan

None - plan executed exactly as written.

## Metrics

- Duration: <1 min
- Tasks: 1
- Files: 2
