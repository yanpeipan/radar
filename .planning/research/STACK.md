# Stack Research: Feed Auto-Discovery

**Domain:** RSS/Atom feed auto-discovery from website URLs
**Project:** v1.9 Automatic Discovery Feed (RSS reader CLI)
**Researched:** 2026-03-27
**Confidence:** HIGH

## Executive Summary

**No new library dependencies are required.** The existing stack already contains all necessary components for feed auto-discovery:
- `httpx` for HTTP fetching
- `BeautifulSoup4` for HTML link tag parsing
- `feedparser` for feed validation
- `urllib.parse` (stdlib) for URL resolution

Feed auto-discovery is implemented as custom logic using existing infrastructure, not a specialized library.

---

## Recommended Stack (Additions Only)

### No New Dependencies Required

| Component | Existing Version | Status | Notes |
|-----------|------------------|--------|-------|
| httpx | 0.28.x | SUFFICIENT | Async HTTP client for fetching HTML pages |
| BeautifulSoup4 | 4.12.x | SUFFICIENT | Parse `<link>` tags in HTML `<head>` |
| feedparser | 6.0.x | SUFFICIENT | Validate discovered feeds by parsing |
| urllib.parse | (stdlib) | SUFFICIENT | URL resolution (urljoin) for relative links |

### Optional: If Faster HTML Parsing Needed

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lxml | 6.0.x | Faster HTML parser backend | Already installed as BeautifulSoup backend; pass `features="lxml"` to BeautifulSoup for speed |

---

## Feed Auto-Discovery Implementation Pattern

### 1. HTML Link Tag Discovery

Use BeautifulSoup to find `<link>` tags in `<head>`:

```python
from bs4 import BeautifulSoup
import httpx

async def discover_feeds_from_html(url: str) -> list[str]:
    """Extract feed URLs from <link> tags in HTML <head>."""
    feed_types = {
        "application/rss+xml": "RSS",
        "application/atom+xml": "Atom",
        "application/rdf+xml": "RDF",
    }

    feeds = []
    response = await httpx.AsyncClient().get(url, timeout=10.0)
    soup = BeautifulSoup(response.text, features="lxml")

    for link in soup.find_all("link"):
        rel = link.get("rel", [])
        link_type = link.get("type", "")
        href = link.get("href", "")

        # Check if this is a feed link
        if "alternate" in rel and link_type in feed_types:
            # Resolve relative URLs
            from urllib.parse import urljoin
            feed_url = urljoin(url, href)
            feeds.append(feed_url)

    return feeds
```

### 2. Common Feed URL Patterns

Try well-known feed paths when no `<link>` tags found:

```python
COMMON_FEED_PATHS = [
    "/feed", "/feed/", "/rss", "/rss.xml", "/atom.xml",
    "/feed.xml", "/index.xml", "/blog/feed", "/feeds",
    "/rss/feed", "/atom/feed", "/feed/rss", "/api/feed",
]

async def try_common_feed_paths(base_url: str) -> list[str]:
    """Try common feed URL patterns."""
    from urllib.parse import urljoin

    discovered = []
    for path in COMMON_FEED_PATHS:
        feed_url = urljoin(base_url, path)
        # Validate by attempting to parse
        if await validate_feed(feed_url):
            discovered.append(feed_url)
    return discovered
```

### 3. Website Hierarchy Crawling (Optional, Depth-Limited)

```python
async def crawl_site_for_feeds(
    url: str,
    max_depth: int = 1,
    max_pages: int = 20,
) -> list[str]:
    """Crawl site hierarchy to find feed links.

    Args:
        url: Starting URL
        max_depth: Maximum crawl depth (1 = same page + links on it)
        max_pages: Maximum pages to crawl
    """
    from urllib.parse import urljoin, urlparse

    visited = set()
    feeds = []

    async def crawl_page(page_url: str, depth: int):
        if depth > max_depth or len(visited) >= max_pages:
            return

        if page_url in visited:
            return
        visited.add(page_url)

        # Get feeds from this page
        page_feeds = await discover_feeds_from_html(page_url)
        feeds.extend(page_feeds)

        if depth >= max_depth:
            return

        # Extract links to same domain for further crawling
        try:
            response = await httpx.AsyncClient().get(page_url, timeout=10.0)
            soup = BeautifulSoup(response.text, features="lxml")
            base_domain = urlparse(url).netloc

            for a_tag in soup.find_all("a", href=True):
                link = urljoin(page_url, a_tag["href"])
                parsed = urlparse(link)
                if parsed.netloc == base_domain:
                    await crawl_page(link, depth + 1)
        except Exception:
            pass

    await crawl_page(url, 0)
    return list(set(feeds))  # Deduplicate
```

---

## Integration with Existing Architecture

### Provider Integration Point

The existing `ProviderRegistry` and `discover_or_default()` pattern should be extended:

1. **New `DiscoveryProvider`** (priority: 10, lower than RSSProvider 50)
   - Matches website URLs (not feed URLs)
   - `crawl_async()` returns discovered feeds (not articles)
   - Called before RSSProvider when user provides a website URL

2. **Discovery logic lives in `src/application/discovery.py`**
   - `discover_feeds(url: str) -> list[Feed]`
   - Uses existing httpx async client
   - Uses existing BeautifulSoup parsing
   - Uses existing feedparser validation

### CLI Integration

```
feed add <url> --discover    # Discover feeds, prompt to subscribe
discover <url>               # Just discover, list feeds
feed add <url> --automatic   # Discover and subscribe all without prompting
```

---

## Alternatives Considered

| Approach | Recommendation | Rationale |
|----------|---------------|-----------|
| feedfinder2 library | NOT RECOMMENDED | Abandoned (0.0.4, no recent updates), duplicates existing functionality |
| Custom implementation with existing libs | RECOMMENDED | Leverages existing stack, full control, no new dependencies |
| Scrapy crawler | OVERKILL | Heavy framework, not needed for feed discovery |
| Playwright for all pages | NOT NEEDED | Basic HTML parsing sufficient for `<link>` tag discovery |

---

## What NOT to Add

| Library | Why Avoid | Use Instead |
|---------|-----------|-------------|
| feedfinder2 | Abandoned, unmaintained, provides no advantage | Custom implementation with BeautifulSoup + feedparser |
| Scrapy | Heavy dependency, overkill for feed discovery | Simple async crawling with httpx + BeautifulSoup |
| Selenium | Browser automation overhead | Scrapling (already in stack) for JS-rendered pages |
| new-ews / other feed libraries | Niche, not well-maintained | feedparser (already in stack) handles all feed types |

---

## Version Recommendations

| Library | Current | Recommended | Notes |
|---------|---------|-------------|-------|
| httpx | 0.28.x | 0.28.x (latest) | Already on latest |
| BeautifulSoup4 | 4.12.3 | 4.12.3+ | Upgrade to 4.14.x for bug fixes if issues arise |
| feedparser | 6.0.12 | 6.0.12 (latest) | Already on latest |
| lxml | 6.0.2 | 6.0.2+ (latest 6.0.x) | Already installed, use as BS4 backend |

---

## Sources

- **feedparser 6.0.x documentation** — Universal feed parser supporting RSS 0.9x-2.0, Atom 0.3/1.0, CDF, RDF (HIGH confidence)
- **BeautifulSoup4 documentation** — HTML parsing with `<link>` tag navigation (HIGH confidence)
- **httpx documentation** — Async HTTP client with timeout and redirect support (HIGH confidence)
- **Feed auto-discovery standard** — `<link rel="alternate">` tags in HTML `<head>` per W3C spec (HIGH confidence)
- **Common feed URL patterns** — Industry standard paths: /feed, /rss, /atom.xml, /feed.xml, /index.xml (MEDIUM confidence - established convention)

---

*Stack research for: v1.9 Automatic Discovery Feed*
*Researched: 2026-03-27*
