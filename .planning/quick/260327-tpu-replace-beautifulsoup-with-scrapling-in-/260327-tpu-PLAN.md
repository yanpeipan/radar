---
phase: quick
plan: 260327-tpu
type: execute
wave: 1
depends_on: []
files_modified:
  - src/discovery/deep_crawl.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "deep_crawl page fetching uses Scrapling Fetcher (not httpx)"
    - "robots.txt fetching uses Scrapling Fetcher (not httpx)"
    - "Code compiles with no import errors"
    - "Deep crawl discovers feeds correctly"
  artifacts:
    - path: src/discovery/deep_crawl.py
      provides: HTTP fetching with Scrapling Fetcher
      contains: "from scrapling import Fetcher"
  key_links:
    - from: src/discovery/deep_crawl.py
      to: scrapling.Fetcher
      via: asyncio.to_thread(Fetcher.get, url)
      pattern: "to_thread.*Fetcher"
---

<objective>
Replace httpx.AsyncClient page fetching with Scrapling Fetcher in deep_crawl.py for TLS fingerprinting (anti-blocking) benefits.
</objective>

<execution_context>
@/Users/y3/radar/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@src/discovery/deep_crawl.py
@src/providers/rss_provider.py (lines 300-348, shows async Scrapling pattern with asyncio.to_thread)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Replace httpx with Scrapling Fetcher in deep_crawl.py</name>
  <files>src/discovery/deep_crawl.py</files>
  <action>
    In src/discovery/deep_crawl.py:

    1. Remove line 9: `import httpx`
    2. Remove line 17: `from src.providers.rss_provider import BROWSER_HEADERS`
    3. Add import: `from scrapling import Fetcher`

    4. In `deep_crawl()` function (lines 117-135), replace the httpx.AsyncClient fetch with Scrapling Fetcher wrapped in asyncio.to_thread():
    ```python
    # Before (lines 120-128):
    async with httpx.AsyncClient(
        headers=BROWSER_HEADERS,
        follow_redirects=True,
        timeout=10.0,
    ) as client:
        response = await client.get(start_url)
        if response.status_code == 200:
            html = response.text
            page_url = str(response.url)

    # After:
    def _sync_fetch(url):
        response = Fetcher.get(url)
        if response.status == 200:
            return response.text, response.url
        return None, url

    response_text, response_url = await asyncio.to_thread(_sync_fetch, start_url)
    if response_text:
        html = response_text
        page_url = str(response_url)
        return await _discover_feeds_on_page(html, page_url)
    ```

    5. In `_fetch_page()` function (lines 170-194), replace httpx.AsyncClient with Scrapling Fetcher:
    ```python
    # Before (lines 184-192):
    async with httpx.AsyncClient(
        headers=BROWSER_HEADERS,
        follow_redirects=True,
        timeout=10.0,
    ) as client:
        response = await client.get(url)
        if response.status_code != 200:
            return None, url
        return response.text, str(response.url)

    # After:
    def _sync_fetch_page(url):
        response = Fetcher.get(url)
        if response.status != 200:
            return None, url
        return response.text, response.url

    return await asyncio.to_thread(_sync_fetch_page, url)
    ```

    6. In `_check_robots()` function (lines 196-235), replace httpx.AsyncClient robots.txt fetch (lines 219-220):
    ```python
    # Before (lines 219-222):
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(robots_url)
        if response.status_code == 200:
            parser.parse(response.text.splitlines())

    # After:
    def _sync_fetch_robots(robots_url):
        response = Fetcher.get(robots_url)
        if response.status == 200:
            return response.text.splitlines()
        return None

    lines = await asyncio.to_thread(_sync_fetch_robots, robots_url)
    if lines:
        parser.parse(lines)
    ```

    Note: Scrapling Fetcher uses curl_cffi for TLS fingerprinting - no need for BROWSER_HEADERS.
    Note: Fetcher.get() returns Response (extends Selector) with .status (int), .text (str), .url, .headers, .body (bytes).
  </action>
  <verify>
    <automated>cd /Users/y3/radar && python -c "from src.discovery.deep_crawl import deep_crawl; print('Import OK')"</automated>
  </verify>
  <done>deep_crawl.py uses Scrapling Fetcher for all HTTP fetching, httpx import removed</done>
</task>

</tasks>

<verification>
- python -c "from src.discovery.deep_crawl import deep_crawl; print('Import OK')" passes
- grep -n "httpx" src/discovery/deep_crawl.py returns no matches
- grep -n "from scrapling import Fetcher" src/discovery/deep_crawl.py returns 1 match
- grep -n "asyncio.to_thread.*Fetcher" src/discovery/deep_crawl.py returns matches
</verification>

<success_criteria>
- src/discovery/deep_crawl.py imports Fetcher (not httpx) for page fetching
- No httpx usage remains in deep_crawl.py
- Code compiles without import errors
</success_criteria>

<output>
After completion, create `.planning/quick/260327-tpu-replace-beautifulsoup-with-scrapling-in-/260327-tpu-SUMMARY.md`
</output>
