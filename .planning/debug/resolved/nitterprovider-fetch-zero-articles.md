---
status: resolved
trigger: "NitterProvider returns 0 articles when fetching elonmusk feed via `python -m src.cli fetch --all`. Nitter instances are reported as failed."
created: 2026-04-01T00:00:00Z
updated: 2026-04-01T13:59:00Z
---

## Root Cause Summary

**THREE bugs were found and fixed:**

### Bug 1: Wrong config path (config.py)
- **File:** `src/application/config.py`
- **Issue:** `Path(__file__).parent.parent / "config.yaml"` resolved to `/src/config.yaml` (wrong)
- **Fix:** Changed to `Path(__file__).parent.parent.parent / "config.yaml"`
- **Impact:** Nitter settings were never loaded (returned None), so provider had no instances to try

### Bug 2: Typo in import (nitter_provider.py)
- **File:** `src/providers/nitter_provider.py`
- **Issue:** `from src.utils.scrapling_utils` (wrong spelling)
- **Fix:** Changed to `from src.utils.scraping_utils`
- **Impact:** `ModuleNotFoundError` when trying to fetch articles

### Bug 3: StealthyFetcher proxy support (scraping_utils.py)
- **File:** `src/utils/scraping_utils.py`
- **Issue:** StealthyFetcher (headless Chrome) doesn't automatically use system proxy
- **Fix:** Added `_get_proxy()` function to detect proxy from env vars and pass it to StealthyFetcher
- **Impact:** Fallback to StealthyFetcher failed with timeouts when basic Fetcher returned 429

## Verification

After fixes, NitterProvider successfully fetched 20 articles from nitter:elonmusk.

**Test output:**
```
Fetching articles from nitter:elonmusk...
Result: 20 articles
```

## Files Changed
1. `src/application/config.py` - Fixed config.yaml path
2. `src/providers/nitter_provider.py` - Fixed import typo (scrapling_utils -> scraping_utils)
3. `src/utils/scraping_utils.py` - Added proxy support for StealthyFetcher

## Prior State (Incorrect Assumption)
Prior session concluded "external infrastructure issue" based on CLI-only tests. User's browser-accessible evidence was correct - nitter.net IS reachable. The issue was code bugs, not nitter being down.

## Evidence Timeline
1. `curl https://nitter.net/elonmusk/rss` via proxy: SUCCESS
2. scrapling Fetcher test: SUCCESS (200, 24109 bytes)
3. But NitterProvider failed: due to bugs #1, #2, #3 above

## Resolution
root_cause: "Three code bugs prevented NitterProvider from working: (1) config.py path wrong, (2) import typo, (3) StealthyFetcher didn't use proxy"
fix: "Fixed all three bugs - verified by successful fetch of 20 articles"
verification: "python3 test: NitterProvider.fetch_articles returned 20 articles from nitter:elonmusk"
files_changed: ["src/application/config.py", "src/providers/nitter_provider.py", "src/utils/scraping_utils.py"]
