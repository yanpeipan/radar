# Phase 37: Deep Crawling — Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>

## Task Boundary

Refactor `src/discovery/common_paths.py` to remove hardcoded `_SUBDIR_NAMES` and `_SUBGRID_PATTERNS`, replacing with CSS selector-based dynamic subdirectory discovery from page links. Also refactor `matches_feed_path_pattern()` from regex to CSS selector approach in `_extract_links()`.

**Current problems:**
- `_SUBDIR_NAMES = ("feed", "rss", "blog", "news", "atom", "feeds")` is a closed list — misses sites with feeds at `/podcast/rss.xml`, `/newsletter/feed.xml`, etc.
- `matches_feed_path_pattern()` uses regex `re.compile(r"^/[^/]+/rss\.xml$")` — works but inconsistent with Scrapling CSS selector pattern used elsewhere in discovery.
- `_SUBGRID_PATTERNS` depends on `_SUBDIR_NAMES` — both should be replaced.

</domain>

<decisions>

## Implementation Decisions

### Subdirectory Discovery Approach
- **Remove `_SUBDIR_NAMES`** — replaced by dynamic extraction from page `<a href>` links using CSS selectors.
- **Algorithm:** Fetch page → extract all `a[href]` → parse paths → identify subdirectory candidates that contain feed-like patterns (e.g., `/blog/rss.xml`) → use discovered subdirs to generate feed candidates.
- **Implementation location:** `generate_feed_candidates()` in `common_paths.py` will accept optional `html` parameter, or create new function `_discover_feed_subdirs(html, base)` that uses `Selector(content=html).css('a[href]')`.

### Feed Path Matching
- **Remove `matches_feed_path_pattern()` regex approach** — replaced by CSS selector filtering directly on anchor elements.
- **`_extract_links()` change:** Instead of `page.css('a[href]')` then `if matches_feed_path_pattern(path)`, use CSS selector that finds feed-like links directly: `page.css('a[href*="rss"]')`, `page.css('a[href*="feed"]')`, `page.css('a[href*="atom"]')`, etc. — then extract and validate the href path.
- **Keep `_FEED_PATH_PATTERNS` regex as fallback** for raw path validation if needed.

### Remove `_SUBGRID_PATTERNS`
- **`_SUBGRID_PATTERNS`** — hardcoded subdirectory path templates `("/{subdir}/rss.xml", etc.` — removed, replaced by dynamic subdirectory extraction.
- **`generate_feed_candidates()` no longer uses `_SUBDIR_NAMES` or `_SUBGRID_PATTERNS`** — generates candidates from discovered subdirectories.

### Root Path Patterns
- **`_ROOT_PATH_PATTERNS`** — keep as-is. Root-level paths like `/feed`, `/rss.xml` are standard and don't need dynamic discovery.

### Integration Point
- Both `generate_feed_candidates()` and `_extract_links()` use CSS selector-based subdir discovery.
- `generate_feed_candidates()`: dynamic subdirs from page links → generate feed URL candidates
- `_extract_links()`: CSS selector finds feed-like `<a href>` elements directly → no regex path matching needed

</decisions>

<specifics>

## Specific Ideas

- Use Scrapling `Selector(content=html).css('a[href*="rss"]')` etc. to find feed links — extract `href` attribute and construct feed URL candidates
- In `generate_feed_candidates()`: first try dynamic subdir extraction, fall back to `_ROOT_PATH_PATTERNS` if page fetch fails
- Feed URL pattern detection: look for `href` values ending in `.xml`, `/rss`, `/feed`, `/atom` etc.
- Subdirectory extraction: parse path from `a[href]` links, deduplicate, filter to feed-like subdirs

## Files to Modify
- `src/discovery/common_paths.py`: remove `_SUBDIR_NAMES`, `_SUBGRID_PATTERNS`; refactor `generate_feed_candidates()` with CSS selector approach
- `src/discovery/deep_crawl.py`: refactor `_extract_links()` to use CSS selector-based feed link discovery instead of regex filtering

## Scrapling CSS Selector Examples (from official docs)
```python
# Get href attribute
link = page.css('a::attr(href)').get()
# Or cleaner:
href = anchor.attrib['href']

# Links containing 'feed' in href
links = page.css('a[href*="feed"]')

# Links ending in .xml
links = page.css('a[href$=".xml"]')
```

</specifics>

<canonical_refs>

No external specs — requirements fully captured in decisions above.

</canonical_refs>
