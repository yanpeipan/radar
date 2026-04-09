---
status: investigating
issue: fetch-long-running-no-progress
slug: fetch-stuck-37-percent
created: "2026-04-05T09:00:00.000Z"
hypothesis: null
next_action: null
checkpoints: []
root_cause: null
confidence: null
files_involved: []
---

# Debug Session: fetch-stuck-37-percent

**Issue:** `feedship fetch` stuck at 37% progress for 45+ minutes
**Mode:** diagnose-only (--diagnose)
**Created:** 2026-04-05

## Symptoms

- "The Cloudflare Blog" stuck at 37% with 0:12:42 elapsed time remaining
- Multiple stealth fetcher 60s timeouts: aiwire.net, datanami.com
- rss.nytimes.com took 20s per item for embedding
- One batch: 500 articles, 1,315,386 chars embedding taking 40.848s
- Progress bar spinners appear stuck: ⠦ ⠏ ⠇
- Semaphore(10) concurrency limiting
- `Locator.bounding_box: Timeout 60000ms exceeded` errors

## Root Cause Analysis

### Primary Root Cause

**Synchronous blocking Playwright operations in `asyncio.to_thread()` cannot be interrupted by asyncio timeout mechanisms, causing thread pool exhaustion and event loop starvation.**

### Mechanism

1. **Stealth Fetcher is Synchronous Blocking Code**
   - `StealthyFetcher().fetch()` (line 377-388 in `scraping_utils.py`) launches headless Chrome via Playwright
   - This is a **synchronous blocking call** - it does not yield to the asyncio event loop
   - When called via `asyncio.to_thread()` in `_fetch_with_fallback_async` (line 547-548), it blocks a thread pool thread

2. **Timeout Mismatch**
   - Configured `_STEALTH_TIMEOUT_MS = 15000` (15 seconds) at line 256
   - Passed to `stealth.fetch(url, **fetch_kwargs)` at line 388
   - BUT the error shows "Locator.bounding_box: Timeout 60000ms exceeded"
   - This 60-second timeout is Playwright's **default locator timeout**, NOT our configured timeout
   - The `timeout` parameter to `StealthyFetcher.fetch()` does NOT properly override Playwright's internal timeouts

3. **Thread Pool Exhaustion**
   - Python's default `ThreadPoolExecutor` has `max_workers = min(32, os.cpu_count() + 4)` (typically 8-12 threads)
   - With `concurrency=10` and multiple feeds triggering stealth fetcher timeouts (60s each)
   - Each blocked stealth fetcher holds a thread indefinitely
   - Thread pool becomes saturated with blocked threads

4. **Event Loop Starvation**
   - `asyncio.to_thread()` does not block the event loop itself - the thread runs concurrently
   - HOWEVER, when thread pool is exhausted, new `asyncio.to_thread()` calls **block the calling coroutine** waiting to submit work
   - This blocking at the event loop level prevents `asyncio.as_completed()` from processing results
   - Progress bar updates (`fp.update()`) cannot be processed

5. **Why Progress Bar Stops**
   - Progress updates happen via `fp.update(result)` in `_collect_and_update()` async generator
   - This async generator is driven by `uvloop.run(_collect_and_update())`
   - If the event loop is blocked waiting to submit work to exhausted thread pool, it cannot process the `asyncio.as_completed()` results
   - Rich's `SpinnerColumn` animation also requires event loop cycles to update display

### Evidence

- Error: `Locator.bounding_box: Timeout 60000ms exceeded` - Playwright's default, not our 15s config
- `asyncio.Semaphore(10)` limits concurrent feed fetches, but threads are the actual bottleneck
- Synchronous `_sync_fetch_with_fallback` called via `asyncio.to_thread()` without asyncio-level timeout wrapper
- `asyncio.to_thread()` in `_fetch_with_fallback_async` (line 547-548) passes `timeout` but this only affects basic fetcher, not stealth fetcher's Playwright operations

### Call Chain

```
fetch_one_async(feed)                    # fetch.py:79
  └── asyncio.to_thread(provider.fetch_articles, feed)
        └── RSSProvider.fetch_articles()  # rss_provider.py:196
              └── fetch_with_fallback(url)  # rss_provider.py:126
                    └── _sync_fetch_with_fallback()  # scraping_utils.py:311
                          └── StealthyFetcher().fetch()  # scraping_utils.py:388
                                └── Playwright (BLOCKING, ~60s timeout)

async_fetch_with_fallback(url)           # scraping_utils.py:558
  └── _fetch_with_fallback_async()       # scraping_utils.py:505
        └── asyncio.to_thread(_sync_fetch_with_fallback)  # scraping_utils.py:547
              └── StealthyFetcher().fetch()  # BLOCKING, ~60s timeout
```

## ROOT CAUSE FOUND

**Root Cause:** The stealth fetcher (`StealthyFetcher`) is a synchronous blocking operation that launches Playwright headless Chrome. When Playwright's internal locator timeout (60 seconds default) exceeds the configured stealth timeout (15 seconds), the blocking call cannot be interrupted by asyncio. This causes thread pool exhaustion and event loop starvation, preventing progress updates.

**Confidence:** high

**Files Involved:**
- `src/utils/scraping_utils.py` - `_sync_fetch_with_fallback` (lines 376-391), `_fetch_with_fallback_async` (lines 505-555)
- `src/application/fetch.py` - `fetch_one_async` (line 79), `fetch_all_async` (line 161)

**Mechanism:** `asyncio.to_thread()` runs synchronous Playwright operations in thread pool threads. When Playwright's internal timeout (60s) exceeds the configured timeout (15s), threads are blocked for 60+ seconds. With multiple concurrent feeds triggering this, the thread pool becomes saturated. The asyncio event loop cannot process `asyncio.as_completed()` results because it's blocked waiting to submit work to the exhausted thread pool. This causes the progress bar to freeze.

**Fix Strategies:**
1. Wrap the `asyncio.to_thread()` call with `asyncio.timeout()` context manager or `asyncio.wait_for()` to enforce the configured timeout at the asyncio level and properly cancel the operation
2. Replace synchronous Playwright with async Playwright (`async_playwright`) so the stealth fetcher can yield to the event loop and be properly interruptible
3. Alternatively, reduce the number of concurrent feeds to stay below thread pool saturation threshold, but this is a workaround not a fix
