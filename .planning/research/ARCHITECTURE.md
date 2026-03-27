# Architecture Research: Feed Auto-Discovery

**Domain:** RSS reader CLI with automatic feed discovery
**Project:** v1.9 Automatic Discovery Feed
**Researched:** 2026-03-27
**Confidence:** HIGH

## Executive Summary

Feed auto-discovery allows users to provide a website URL instead of a direct feed URL, and the system automatically finds associated RSS/Atom/RDF feeds. This is orthogonal to the existing Provider plugin architecture -- providers fetch and parse content from known feed URLs, while a new Discovery module locates feed URLs on web pages.

**Key insight:** Discovery is a URL -> [URLs] transformation that does not fit the crawl/parse pattern of ContentProvider Protocol. It belongs in a separate service module, not as a provider plugin.

## How Discovery Integrates with Existing Architecture

### Existing Architecture Layers

```
CLI Layer (src/cli/)
    feed.py, article.py
         ↓
Application Layer (src/application/)
    feed.py, fetch.py
         ↓
Provider Layer (src/providers/)
    RSSProvider, GitHubReleaseProvider
    Protocol: ContentProvider (match, crawl, crawl_async, parse, feed_meta)
         ↓
Storage Layer (src/storage/)
    sqlite.py - SQLite operations
```

### Why Discovery is NOT a New Provider

The Provider plugin pattern (ContentProvider Protocol) is designed for:
- Fetching content from a known URL
- Parsing that content into articles
- Returning metadata about the feed

Discovery is different: given a website URL (non-feed), find associated feed URLs. This is a unidirectional transformation (URL -> [URLs]) that does not fit the crawl/parse pattern.

**Discovery is a separate service module**, not a provider. It produces feed URLs that can then be passed to existing `add_feed()` flow.

## Recommended Project Structure

```
src/
├── discovery/                  # NEW: Feed auto-discovery module
│   ├── __init__.py
│   ├── parser.py              # HTML link element parsing
│   ├── fetcher.py             # HTTP fetching with robots.txt
│   ├── common_paths.py        # Common feed path heuristics
│   └── models.py              # DiscoveredFeed dataclass
├── providers/
│   ├── ...
│   └── ...
└── ...
```

## New Components

### 1. DiscoveredFeed Model (src/discovery/models.py)

```python
@dataclass
class DiscoveredFeed:
    """Represents a feed discovered from a website URL."""
    url: str                  # The feed URL
    title: Optional[str]      # Feed title (from <link> title attribute or feed itself)
    feed_type: str            # "rss", "atom", "rdf"
    source: str               # How discovered: "link_element", "common_path", "well_known"
    page_url: str             # The original page URL that yielded this feed
```

### 2. Discovery Service (src/discovery/__init__.py)

```python
async def discover_feeds(
    url: str,
    depth: int = 1,
    follow_common_paths: bool = True,
    respect_robots_txt: bool = False,
) -> List[DiscoveredFeed]:
    """
    Discover feed URLs from a website URL.

    Args:
        url: Website URL to scan for feeds.
        depth: Crawl depth (1 = same page only, 2+ = follow internal links).
        follow_common_paths: Also try common feed paths (/feed, /rss, etc.).
        respect_robots_txt: If True, check robots.txt before fetching.

    Returns:
        List of DiscoveredFeed objects.
    """
```

### 3. HTML Link Element Parser (src/discovery/parser.py)

Standard HTML `<head>` parsing for `<link>` elements:

```python
def parse_link_elements(html: bytes, page_url: str) -> List[DiscoveredFeed]:
    """Extract feed URLs from <link> elements in HTML <head>.

    Finds links like:
    - <link rel="alternate" type="application/rss+xml" href="...">
    - <link rel="alternate" type="application/atom+xml" href="...">
    - <link rel="alternate" type="application/rdf+xml" href="...">
    """
```

Feed types mapped from Content-Type:
- `application/rss+xml` -> RSS 2.0
- `application/atom+xml` -> Atom 1.0
- `application/rdf+xml` -> RDF/RSS 1.0
- `application/xml`, `text/xml` -> ambiguous, need to fetch and parse to confirm

### 4. Common Paths Heuristic (src/discovery/common_paths.py)

Many sites put feeds at predictable locations:

```python
COMMON_FEED_PATHS = [
    "/feed",
    "/feed/",
    "/rss",
    "/rss.xml",
    "/atom.xml",
    "/feed.xml",
    "/index.xml",
    "/blog/feed",
    "/posts/feed",
    "/feed/rss",
    "/api/feed",
]

async def try_common_paths(base_url: str) -> List[DiscoveredFeed]:
    """Try fetching common feed paths to discover feeds."""
```

### 5. Depth-Aware Crawler (src/discovery/fetcher.py)

For depth > 1, crawl internal links:

```python
async def discover_with_depth(
    url: str,
    depth: int,
    seen_urls: Set[str],
) -> List[DiscoveredFeed]:
    """Crawl website up to specified depth, collecting feed URLs."""
    # BFS with depth limit
    # Only follow same-domain links
    # Track visited URLs to avoid cycles
```

## Data Flow

### Flow 1: `feed add <url> --discover`

```
CLI: feed add <url> --discover --depth=1
    ↓
Application Layer: add_feed_with_discovery(url, depth)
    ↓
Discovery Service: discover_feeds(url, depth=1)
    ↓
  - Fetch HTML from url
  - parse_link_elements() → DiscoveredFeed[]
  - if no feeds found + follow_common_paths:
      try_common_paths(url) → DiscoveredFeed[]
    ↓
Return list of DiscoveredFeed
    ↓
CLI presents feeds to user OR (if --automatic) auto-subscribes all
    ↓
For each selected feed_url:
    add_feed(feed_url) → existing flow
```

### Flow 2: `discover <url>` (new command)

```
CLI: discover <url> --depth=1
    ↓
Discovery Service: discover_feeds(url, depth=1)
    ↓
Return list of DiscoveredFeed
    ↓
CLI displays table of found feeds with:
    - URL
    - Title
    - Type
    - Source
```

## CLI Integration

### New Command: `discover`

```python
@cli.command("discover")
@click.argument("url")
@click.option("--depth", default=1, type=click.IntRange(1, 5), help="Crawl depth (default: 1)")
@click.option("--automatic", is_flag=True, help="Auto-subscribe all discovered feeds")
@click.pass_context
def discover(ctx: click.Context, url: str, depth: int, automatic: bool) -> None:
    """Discover RSS/Atom feeds from a website URL.

    Examples:

      rss-reader discover https://example.com
      rss-reader discover https://example.com --depth=2
      rss-reader discover https://example.com --automatic
    """
```

### Modified Command: `feed add`

```python
@feed.command("add")
@click.argument("url")
@click.option("--discover/--no-discover", default=True, help="Auto-discover feeds (default: on)")
@click.option("--depth", default=1, type=click.IntRange(1, 5), help="Discovery depth when --discover")
@click.option("--automatic", is_flag=True, help="Subscribe to all discovered feeds without prompting")
@click.pass_context
def feed_add(ctx: click.Context, url: str, discover: bool, depth: int, automatic: bool) -> None:
    """Add a new feed by URL.

    If URL is a website (not a feed), automatically discovers associated feeds.
    Use --no-discover to add as direct feed URL.
    """
```

## Integration Points

### Integration with Existing Layer: Application (Minimal Change)

The discovery module is called from the CLI layer. It produces feed URLs that the CLI passes to existing `add_feed()`. No changes to Provider or Storage layers required.

```python
# src/application/feed.py (additions)

def add_feed_with_discovery(url: str, depth: int = 1) -> List[Feed]:
    """Add feed(s) from URL with auto-discovery.

    If URL is a direct feed URL, behaves like add_feed().
    If URL is a website, discovers and adds all associated feeds.

    Returns:
        List of added Feed objects.
    """
    from src.discovery import discover_feeds

    # First try as direct feed (existing behavior)
    providers = discover_or_default(url)
    if providers:
        try:
            feed = add_feed(url)
            return [feed]
        except ValueError:
            pass  # Not a direct feed, try discovery

    # Auto-discovery path
    discovered = discover_feeds(url, depth=depth)
    if not discovered:
        raise ValueError(f"No feeds found at {url}")

    added_feeds = []
    for d in discovered:
        try:
            feed = add_feed(d.url)
            added_feeds.append(feed)
        except ValueError as e:
            if "already exists" in str(e):
                continue  # Skip already-subscribed feeds
            raise

    return added_feeds
```

### Integration with Existing Layer: Providers (No Change)

Providers remain unchanged. Discovery produces feed URLs, providers consume them.

### Integration with Existing Layer: Storage (No Change)

Storage layer unchanged. Feeds are stored via existing `add_feed()`.

## Depth Configuration

| Depth | Behavior | Use Case |
|-------|----------|----------|
| 1 | Parse only the given page's HTML | Simple sites with feeds linked in homepage |
| 2 | Also scan linked pages (same domain) | Sites with feeds in subdirectories |
| 3+ | BFS crawl with cycle detection | Complex sites with feeds behind multiple clicks |

**Recommendation:** Default depth=1. Deeper discovery increases HTTP requests and latency.

## Crawler Behavior at Each Depth

### Depth 1 (Same Page Only)

1. Fetch HTML from URL
2. Parse `<head>` for `<link type="application/*+xml">`
3. Try common paths: `/feed`, `/rss`, `/atom.xml`
4. Return DiscoveredFeed[]

### Depth 2+ (Multi-Page Crawl)

1. Do depth 1
2. Parse HTML for internal links (`<a href>` on same domain)
3. BFS queue: unvisited links
4. For each link up to depth limit:
   - Fetch HTML
   - Parse for link elements
   - Extract more internal links
5. Deduplicate and return all DiscoveredFeed[]

## Anti-Patterns to Avoid

### Anti-Pattern 1: Discovery as Provider

**What people try:** Force discovery into ContentProvider protocol by creating a provider that returns feed URLs instead of articles.

**Why it's wrong:** Providers are built for URL -> Articles. Discovery is URL -> [URLs]. Different input/output shapes. The Protocol methods (crawl, parse) don't map to discovery semantics.

**Do this instead:** New discovery service module outside provider system.

### Anti-Pattern 2: Discovery Inside feed_add()

**What people try:** Put discovery logic directly in `add_feed()` function.

**Why it's wrong:** Violates single responsibility. `add_feed()` should only handle adding a known feed URL.

**Do this instead:** Discovery is a separate concern. CLI layer decides whether to call discovery, then calls `add_feed()` for results.

### Anti-Pattern 3: Infinite Crawling

**What people try:** Depth without limit, following all links.

**Why it's wrong:** Cycles, huge HTTP load, potential for getting banned.

**Do this instead:** Hard depth limit (default 1, max 5). Track visited URLs. Respect rate limiting.

## Build Order

### Phase 1: Discovery Module Core (do first)
- Create `src/discovery/` package
- Create `src/discovery/models.py` - DiscoveredFeed dataclass
- Create `src/discovery/parser.py` - HTML link element parsing
- Create `src/discovery/common_paths.py` - common feed path heuristics
- Create `src/discovery/__init__.py` - `discover_feeds()` function for depth=1
- Test: verify parser extracts link elements correctly

### Phase 2: CLI Integration
- Add `discover` CLI command (read-only discovery)
- Add `--discover` and `--depth` options to `feed add`
- Add `--automatic` option for auto-subscribe
- Test: `discover <url>` shows found feeds

### Phase 3: Application Layer Integration
- Add `add_feed_with_discovery()` in `src/application/feed.py`
- Wire `feed add --discover` to call new function
- Test: `feed add <website_url>` discovers and adds feeds

### Phase 4: Depth > 1 Support
- Add `src/discovery/fetcher.py` - BFS crawler with depth limit
- Extend `discover_feeds()` to support `depth > 1`
- Add cycle detection and URL deduplication
- Test: depth=2 discovers feeds from subdirectories

## Sources

- [feedparser PyPI](https://pypi.org/project/feedparser/) — Feed parsing library (HIGH confidence)
- [RSS 2.0 Specification](https://cyber.harvard.edu/rss/rss.html) — RSS 2.0 syndication format (HIGH confidence)
- [Atom Publishing Protocol RFC 5023](https://datatracker.ietf.org/doc/html/rfc5023) — Atom feed format (HIGH confidence)
- [HTML5 Specification - link element](https://html.spec.whatwg.org/multipage/semantics.html#the-link-element) — link element parsing (HIGH confidence)
- [Robots.txt specification](https://www.robotstxt.org/robotstxt.html) — robots.txt parsing (HIGH confidence)

---

*Architecture research for: Feed Auto-Discovery (v1.9)*
*Researched: 2026-03-27*
