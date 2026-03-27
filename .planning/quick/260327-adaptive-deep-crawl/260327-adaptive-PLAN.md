# 260327-adaptive-PLAN: Enable Adaptive Fetch Strategy for Deep Crawl

## Task Summary
Fix `deep_crawl` to use DynamicFetcher (Playwright) when static Fetcher returns empty content, and fix the empty-content fallback bug.

## Problem Analysis

### Bug 1: Empty content doesn't trigger fallback
In `deep_crawl` for `max_depth <= 1`:
```python
if response.status == 200:
    html = response.text        # '' for JS-rendered pages (status 200 but no body)
    page_url = response.url
    return await _discover_feeds_on_page(html, page_url)  # Returns [] → we return [], never fallback!
```
Fix: Check `len(response.text) == 0` → fall back to `_probe_well_known_paths`.

### Bug 2: `_extract_feed_title` uses `response.text` which is empty for DynamicFetcher
DynamicFetcher sets `response.body` but not `response.text`. Fix: use `response.body.decode('utf-8')`.

### Feature: Adaptive fetch strategy
When static Fetcher gets empty content, try DynamicFetcher (Playwright) before falling back to well-known paths.

## Implementation Plan

### Step 1: Fix `_extract_feed_title` to use `body` not `text`
In `src/discovery/deep_crawl.py`, `_extract_feed_title`:
- Current: `feed = feedparser.parse(response.content)` where `response.content` is not set
- Fix: `feed = feedparser.parse(response.body)` after decoding

### Step 2: Fix empty-content fallback in `deep_crawl` (max_depth <= 1)
Add check: if `response.status == 200 and (not response.text or len(response.text) < 100)`, fall back to `_probe_well_known_paths`.

### Step 3: Add adaptive fetch with DynamicFetcher
In `deep_crawl`, when static Fetcher returns empty content, try DynamicFetcher before well-known paths:
```python
# After static Fetcher returns empty content
dynamic_resp = await asyncio.to_thread(DynamicFetcher().fetch, start_url, ...)
if dynamic_resp.body:
    html = dynamic_resp.body.decode('utf-8')
    return await _discover_feeds_on_page(html, dynamic_resp.url)
```

### Files to Modify
- `src/discovery/deep_crawl.py`:
  - `_extract_feed_title`: use `response.body.decode('utf-8')` instead of `response.content`
  - `deep_crawl` `max_depth <= 1` path: add empty-content check
  - `deep_crawl`: add DynamicFetcher fallback when static Fetcher gets empty content

### Verification
- `python -m src.cli feed add https://openai.com/` → should show feed titles (not `—`)
- `python -m src.cli feed add https://example.com/` → should still work with static Fetcher
- No regression on existing feed discovery
