---
status: fixing
trigger: "uv run feedship fetch --all fails with multiple feed fetch failures"
created: 2026-04-07T00:00:00
updated: 2026-04-07T00:00:00
---

## Current Focus
hypothesis: RSSProvider.fetch_articles() doesn't check for None response before accessing .headers
test: Add None check after _fetch_feed_content_sync() call
expecting: If response is None, return empty FetchedResult instead of crashing
next_action: Implement fix in rss_provider.py

## Symptoms
expected: fetch --all completes even when some feeds timeout or are malformed
actual: "'NoneType' object has no attribute 'headers'" error crashes individual feed processing
errors:
  - "'NoneType' object has no attribute 'headers'" (main bug)
  - Network timeouts on multiple feeds (transient, acceptable)
  - Malformed XML on 2 feeds (external issue, handled by try/except)
reproduction: Run `uv run feedship fetch --all`
started: Multiple feeds timing out simultaneously

## Eliminated
<!-- No hypotheses eliminated yet -->

## Evidence
- timestamp: 2026-04-07
  checked: src/providers/rss_provider.py fetch_articles method
  found: Line 211 accesses response.headers without checking if response is None
  implication: When stealth fetcher times out, response is None and .headers access crashes

- timestamp: 2026-04-07
  checked: src/utils/scraping_utils.py _sync_fetch_with_fallback
  found: Returns None when stealth fetcher fails (line 390-391)
  implication: Timeout errors return None, not an exception

## Resolution
root_cause: RSSProvider.fetch_articles() doesn't handle None response from _fetch_feed_content_sync()
fix: Add None check after _fetch_feed_content_sync() call, return empty FetchedResult if None
verification: Confirmed - fetch --all completed with 4993 articles from 110 feeds. Malformed feeds handled gracefully with warnings only. No NoneType crash.
files_changed: [src/providers/rss_provider.py]
