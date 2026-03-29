---
phase: 45-discovery-core-architecture
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/providers/__init__.py
  - src/providers/base.py
  - src/providers/rss_provider.py
  - src/discovery/deep_crawl.py
autonomous: true
requirements:
  - ARCH-01
  - ARCH-02
  - ARCH-03
  - API-02
  - API-03

must_haves:
  truths:
    - "providers.discover() calls feed_meta() not parse_feed() to validate feeds"
    - "deep_crawl() performs URL discovery only; all feed validation delegated to providers.discover()"
    - "providers.discover() returns only unique feeds by URL (deduplicated)"
    - "All returned DiscoveredFeed have valid=True (provider confirmed handleable)"
  artifacts:
    - path: "src/providers/__init__.py"
      provides: "providers.discover() using feed_meta() pattern"
      contains: "provider.feed_meta("
    - path: "src/providers/base.py"
      provides: "ContentProvider.feed_meta() protocol method"
      contains: "def feed_meta"
    - path: "src/providers/rss_provider.py"
      provides: "RSSProvider.feed_meta() implementation returning FeedMetaData or None"
      contains: "def feed_meta"
    - path: "src/discovery/deep_crawl.py"
      provides: "deep_crawl() delegates validation to providers.discover()"
      contains: "providers_discover"
  key_links:
    - from: "src/providers/__init__.py::discover()"
      to: "src/providers/rss_provider.py::RSSProvider.feed_meta()"
      via: "provider.feed_meta() call"
    - from: "src/discovery/deep_crawl.py::deep_crawl()"
      to: "src/providers/__init__.py::discover()"
      via: "providers_discover(start_url, response, ...)"
---

<objective>
Refactor discovery architecture so providers.discover() uses feed_meta() pattern and all validation is provider-delegated.
</objective>

<context>
@src/providers/__init__.py
@src/providers/base.py
@src/providers/rss_provider.py
@src/discovery/deep_crawl.py
@src/models.py
@.planning/REQUIREMENTS.md

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From src/models.py:
```python
@dataclass
class FeedMetaData:
    """Provider-specific metadata for a feed."""
    selectors: Optional[list[str]] = None
```

```python
@dataclass
class DiscoveredFeed:
    url: str
    title: Optional[str]
    feed_type: str  # 'rss', 'atom', or 'rdf'
    source: str  # 'autodiscovery', 'well_known_path', etc.
    page_url: str  # Original page URL
    valid: bool = False  # Default to False, validated feeds set True
```

From src/providers/base.py (existing protocol):
```python
def parse_feed(self, url: str, response: "Response" = None) -> "DiscoveredFeed":
    """Validate URL is a feed and return as DiscoveredFeed. Raises exception if invalid."""
    ...

def discover(self, url: str, response: "Response" = None, depth: int = 1) -> List["DiscoveredFeed"]:
    """Discover feed URLs from a page. Returns unverified candidates (valid=False)."""
    ...
```

Key distinction:
- parse_feed() RAISES on invalid feeds (used in crawl path after match() confirms)
- feed_meta() returns None on invalid feeds (used in discover path for non-throwing validation)
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add feed_meta() to providers and update providers.discover()</name>
  <files>src/providers/base.py, src/providers/rss_provider.py, src/providers/__init__.py</files>
  <action>
    **Step 1:** Add `feed_meta()` method to `ContentProvider` protocol in `src/providers/base.py`:
    ```python
    def feed_meta(self, url: str, response: "Response" = None) -> "FeedMetaData | None":
        """Get feed metadata without raising on failure.

        Args:
            url: URL of the feed to get metadata for.
            response: Pre-fetched HTTP response (may be None).

        Returns:
            FeedMetaData if URL is a valid feed, None if invalid or fetch fails.
            Does NOT raise exceptions.
        """
        ...
    ```

    **Step 2:** Add `feed_meta()` implementation to `RSSProvider` in `src/providers/rss_provider.py`:
    ```python
    def feed_meta(self, url: str, response: "Response" = None) -> "FeedMetaData | None":
        """Get feed metadata without raising on failure.

        Uses feedparser.parse() to validate feed and extract title.
        Returns None if feed cannot be fetched or parsed (does not raise).

        Returns:
            FeedMetaData if valid feed, None otherwise.
        """
        from scrapling import Fetcher
        try:
            if response is None:
                response = Fetcher.get(url, headers=BROWSER_HEADERS)
            parsed = feedparser.parse(response.body)
            if not parsed.feed:
                return None
            return FeedMetaData()
        except Exception:
            return None
    ```

    **Step 3:** Update `providers.discover()` in `src/providers/__init__.py` to use `feed_meta()`:
    - Replace `provider.parse_feed(url, response)` with `provider.feed_meta(url, response)`
    - Change exception handling to check for None: `if discovered is None: continue`
    - When feed_meta returns FeedMetaData, construct DiscoveredFeed with valid=True
    - Remove the try/except around feed_meta since it doesn't raise
  </action>
  <verify>
    <automated>cd /Users/y3/radar && python -c "
from src.providers import discover
from src.models import FeedMetaData

# Test that feed_meta exists on providers
from src.providers import get_all_providers
for p in get_all_providers():
    assert hasattr(p, 'feed_meta'), f'{p.__class__.__name__} missing feed_meta'
    meta = p.feed_meta('https://example.com/feed')
    # feed_meta should return None for invalid URL, not raise
    assert meta is None or isinstance(meta, FeedMetaData)

# Test providers.discover uses feed_meta (should not raise on invalid feeds)
feeds = discover('https://example.com/not-a-feed')
print(f'Discover returned {len(feeds)} feeds for invalid URL (should be 0)')
assert len(feeds) == 0, 'Should return empty list for invalid URL'
print('PASS: providers.discover() uses feed_meta pattern correctly')
"</automated>
  </verify>
  <done>
    providers.discover() calls feed_meta() (not parse_feed()) to validate feeds; returns only valid=True feeds deduplicated by URL
  </done>
</task>

<task type="auto">
  <name>Task 2: Simplify deep_crawl() to delegate validation to providers</name>
  <files>src/discovery/deep_crawl.py</files>
  <action>
    Simplify `deep_crawl()` so it performs URL discovery only; all feed validation delegated to `providers.discover()`:

    **For max_depth <= 1 path (lines ~369-385):**
    - Remove the `try/except` block with inline validation
    - After fetching response, call `providers_discover(start_url, response, depth=1, discover=auto_discover)`
    - Return DiscoveredResult with feeds directly from providers_discover (already validated, valid=True)
    - If providers_discover returns empty or exception, return empty DiscoveredResult

    **For max_depth > 1 path (BFS crawl, lines ~387-586):**
    - Keep the BFS loop structure for URL discovery
    - In the BFS loop, `page_feeds = providers_discover(final_url, response, depth, discover=auto_discover)` already delegates validation
    - Remove the `_probe_well_known_paths()` call before BFS (providers handles this)
    - Remove `_extract_links()` path validation check `if not matches_feed_path_pattern(path)` - just collect all feed-like links
    - The deduplication at the end is still useful (providers_discover deduplicates per page, final pass deduplicates across all pages)

    **Remove unused methods from deep_crawl.py:**
    - `_quick_validate_feed()` - no longer used
    - `_probe_well_known_paths()` - providers handles this
    - `_find_feed_links_on_page()` - no longer used
    - `_discover_feeds_on_page()` - no longer used
    - `_validate_and_extract_title()` - no longer used

    **Key constraint:** deep_crawl does URL discovery (CSS selectors, BFS link extraction). providers.discover() does all validation.
  </action>
  <verify>
    <automated>cd /Users/y3/radar && python -c "
import asyncio
from src.discovery.deep_crawl import deep_crawl
from src.providers import discover as providers_discover

# Verify providers_discover returns valid feeds (not valid=False)
async def test():
    # Test with a known feed URL
    feeds = await deep_crawl('https://example.com', max_depth=1)
    print(f'deep_crawl returned {len(feeds.feeds)} feeds')
    for f in feeds.feeds:
        print(f'  - {f.url} valid={f.valid}')
        assert f.valid == True, f'Expected valid=True, got {f.valid}'
    print('PASS: deep_crawl returns only valid=True feeds')

asyncio.run(test())
"</automated>
  </verify>
  <done>
    deep_crawl() performs URL discovery only; all feed validation delegated to providers.discover(); returns only valid=True feeds
  </done>
</task>

</tasks>

<verification>
**Overall phase checks:**
1. `providers.discover()` calls `feed_meta()` (not `parse_feed()`) - verified by Task 1 test
2. `providers.discover()` returns only unique feeds by URL - verified by `seen` set in code
3. `deep_crawl()` returns only `valid=True` feeds - verified by Task 2 test
4. No `DiscoveredFeed` with `valid=False` reaches consumer - all sources set `valid=True`
</verification>

<success_criteria>
1. `providers.discover()` calls `provider.feed_meta()` (not `provider.parse_feed()`) for validation
2. `providers.discover()` returns feeds with `valid=True` only (no `valid=False` feeds)
3. `deep_crawl()` delegates ALL feed validation to `providers.discover()`
4. `providers.discover()` returns feeds deduplicated by URL
5. All `DiscoveredFeed.valid=True` means provider confirmed handleable
</success_criteria>

<output>
After completion, create `.planning/phases/045-discovery-core-architecture/045-01-SUMMARY.md`
</output>
