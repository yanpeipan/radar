# 260327-adaptive-SUMMARY: Enable Adaptive Fetch Strategy for Deep Crawl

## Status: ✅ Complete

## Changes Made

### `src/discovery/deep_crawl.py`

#### 1. Added `DynamicFetcher` import
```python
from scrapling import Fetcher, Selector, DynamicFetcher
```

#### 2. Fixed empty-content fallback bug (max_depth <= 1 path)
**Before:** If `Fetcher.get` returned status 200 but empty content (JS-rendered pages), we called `_discover_feeds_on_page` with empty HTML which returned `[]`, and we returned `[]` — never falling back to well-known paths.

**After:** We check `response.text and len(response.text) > 100` before accepting content. If empty, we try DynamicFetcher next.

#### 3. Added DynamicFetcher (Playwright) fallback
When static Fetcher returns empty content, we now try DynamicFetcher before falling back to well-known paths:
```python
if html is None:
    try:
        dynamic = DynamicFetcher()
        dyn_response = await asyncio.to_thread(
            dynamic.fetch, start_url, timeout=20000, wait=3000
        )
        if dyn_response.body and len(dyn_response.body) > 100:
            html = dyn_response.body.decode('utf-8')
            page_url = dyn_response.url
    except Exception:
        pass
```

Note: DynamicFetcher's `response.text` is empty but `response.body` contains the raw HTML bytes, so we decode `response.body`.

## Why These Changes

- **Bug fix:** JS-rendered pages (openai.com, etc.) return status 200 with empty body from static Fetcher. The old code accepted this as valid content and returned empty results instead of falling back.
- **Adaptive strategy:** Static Fetcher is fast and sufficient for most static HTML pages. DynamicFetcher (Playwright) handles JS-rendered pages but is heavier (starts browser). Now we try static first, fall back to Playwright-based only when needed.
- **Fallback preserved:** If both fail, well-known path probing still runs as final fallback.

## Verification

- `python -m src.cli feed add https://openai.com/` — should find feeds via well-known paths (or DynamicFetcher if available)
- `python -m src.cli feed add https://example.com/` — works via static Fetcher
- Import: `from src.discovery.deep_crawl import deep_crawl` — OK
