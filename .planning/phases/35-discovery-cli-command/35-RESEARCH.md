# Phase 35: Discovery CLI Command - Research

**Researched:** 2026-03-27
**Domain:** Click CLI async command patterns, feed discovery, BFS crawling
**Confidence:** HIGH (codebase analysis)

## Summary

Phase 35 builds a `discover <url> --discover-deep [n]` CLI command that wraps the existing `discover_feeds()` from `src.discovery`. The existing function only handles single-page discovery; the phase requires BFS crawling when depth > 1.

**Key findings:**
1. `discover_feeds()` returns `list[DiscoveredFeed]` but has no depth parameter - deep crawling needs a new implementation or extension
2. CLI pattern: async commands wrap with `uvloop.run()` at CLI entry point (not `@click.async_command()`)
3. Rich Table is used for tabular output (see `article.py` article_list pattern)
4. New command file should be `src/cli/discover.py` with import in `src/cli/__init__.py`

**Primary recommendation:** Implement deep crawling as a new function `discover_feeds_deep(url, max_depth)` that uses BFS, since modifying the existing `discover_feeds()` risks breaking callers. The CLI command calls this new function via `uvloop.run()`.

## User Constraints (from CONTEXT.md)

No CONTEXT.md exists for this phase. Phase requirement DISC-05 provides all constraints:
- `discover <url> --discover-deep [n]` — only discover feeds, do not subscribe
- Default depth=1 (current page only)
- depth=2 enables BFS crawling up to depth 2

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DISC-05 | `discover <url> --discover-deep [n]` CLI command | Wraps `discover_feeds()`; needs BFS extension for depth > 1 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| click | 8.1.x | CLI framework | Project standard (CLAUDE.md) |
| uvloop | (installed) | Async event loop | Already used in `feed.py` for async operations |
| rich | (already used) | Table/panel formatting | Used in `article.py` for table output |

### Project-Specific
| Library | Purpose | Location |
|---------|---------|----------|
| `discover_feeds()` | Single-page feed discovery | `src/discovery/__init__.py` |
| `DiscoveredFeed` | Dataclass for discovered feeds | `src/discovery/models.py` |
| `parse_link_elements()` | HTML link element parser | `src/discovery/parser.py` |
| `validate_feed()` | Feed URL validation | `src/discovery/fetcher.py` |
| `BROWSER_HEADERS` | HTTP headers for browser-like requests | `src/providers/rss_provider.py` |

## Architecture Patterns

### Recommended Project Structure
```
src/cli/
├── __init__.py      # Imports all submodules to trigger decorators
├── feed.py          # Feed management commands
├── article.py       # Article commands
└── discover.py      # NEW: Discovery command (this phase)
```

### Pattern 1: CLI Command File Structure
Each CLI command module follows this pattern:

```python
"""Discover feeds command for RSS reader CLI."""

import logging
import click
import uvloop
from rich.console import Console
from rich.table import Table

from src.cli import cli  # Import cli group

logger = logging.getLogger(__name__)

@cli.command("discover")
@click.argument("url")
@click.option("--discover-deep", default=1, type=click.IntRange(1, 10),
              help="Crawl depth for feed discovery (default: 1)")
@click.pass_context
def discover(ctx: click.Context, url: str, discover_depth: int) -> None:
    """Discover RSS/Atom/RDF feeds from a website URL.

    Examples:

      rss-reader discover example.com          Discover feeds on single page
      rss-reader discover example.com --discover-deep 2   Crawl up to depth 2
    """
    try:
        feeds = uvloop.run(_discover_async(url, discover_depth))
        _display_feeds(feeds)
    except Exception as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        logger.exception("Failed to discover feeds")
        sys.exit(1)


async def _discover_async(url: str, depth: int) -> list[DiscoveredFeed]:
    """Async implementation of feed discovery."""
    # Implementation here
    pass


def _display_feeds(feeds: list[DiscoveredFeed]) -> None:
    """Display discovered feeds using Rich table."""
    if not feeds:
        click.secho("No feeds discovered.", fg="yellow")
        return

    console = Console()
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Type", style="dim", width=8)
    table.add_column("Title", max_width=30)
    table.add_column("URL")

    for feed in feeds:
        feed_type_color = {"rss": "red", "atom": "green", "rdf": "blue"}.get(feed.feed_type, "white")
        table.add_row(
            f"[{feed_type_color}]{feed.feed_type}[/{feed_type_color}]",
            feed.title or "—",
            feed.url
        )

    console.print(table)
    click.secho(f"\nDiscovered {len(feeds)} feed(s)", fg="green")
```

### Pattern 2: Async CLI Wrapper
The codebase uses `uvloop.run()` at CLI entry point, NOT `@click.async_command()`:

```python
# From feed.py line 197
result = uvloop.run(fetch_one_async_by_id(feed_id))

# From feed.py line 206
total_new, success_count, error_count, errors = uvloop.run(
    _fetch_with_progress(fetch_ids_async(ids, concurrency), len(ids), ...)
)
```

### Pattern 3: Rich Table for Feed Display
From `article.py` lines 54-72:

```python
from rich.console import Console
from rich.table import Table

console = Console()
table = Table(show_header=True, header_style="bold magenta")
table.add_column("ID", style="dim", width=8 if not verbose else 36)
table.add_column("Title")
table.add_column("Source", max_width=20)
table.add_column("Date", max_width=10)

for article in articles:
    table.add_row(id_display, title[:50], source[:20], pub_date[:10])
console.print(table)
```

### Pattern 4: Error Display
From `feed.py` lines 57-63:

```python
# Success case
click.secho(f"{prefix}Fetched {total_new} articles from {success_count} feed(s)", fg="green")

# Error case
click.secho(f"Error: Failed to fetch feeds: {e}", err=True, fg="red")

# No results case
click.secho("No feeds subscribed yet. Use 'feed add <url>' to add one.", fg="yellow")
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async event loop | `@click.async_command()` | `uvloop.run()` wrapper | Project convention; `feed.py` uses this pattern |
| HTML parsing | Custom regex | `BeautifulSoup` + `lxml` | Already used in `parse_link_elements()` |
| Feed validation | Custom HEAD requests | `validate_feed()` from `fetcher.py` | Already implemented and tested |
| BFS crawling | Custom URL frontier | `asyncio.Queue` for BFS | Standard async pattern, respects concurrency |

## Common Pitfalls

### Pitfall 1: Forgetting to normalize URLs before crawling
**What goes wrong:** Crawling `example.com` without normalization misses schemes and redirects.
**Why it happens:** `discover_feeds()` calls `normalize_url()` internally, but new deep crawling may skip this.
**How to avoid:** Call `normalize_url()` at the start of the async discovery function.

### Pitfall 2: No cycle detection in BFS
**What goes wrong:** Pages link to each other causing infinite crawling.
**Why it happens:** BFS keeps track of visited URLs.
**How to avoid:** Use a `set()` for visited URLs and check before enqueueing.

### Pitfall 3: Fetching the same feed URL multiple times
**What goes wrong:** Same feed may appear on multiple pages.
**Why it happens:** No deduplication across discovery paths.
**How to avoid:** Use a `set()` for seen feed URLs, skip if already discovered.

### Pitfall 4: Too many concurrent requests
**What goes wrong:** Site blocks crawler or local resource exhaustion.
**Why it happens:** BFS fans out quickly on link-heavy pages.
**How to avoid:** Use `asyncio.Semaphore` to limit concurrency (e.g., 5 concurrent page fetches).

### Pitfall 5: Missing timeout on page fetches
**What goes wrong:** Hanging on slow/stalled connections.
**Why it happens:** Default `httpx` timeouts may be too long.
**How to avoid:** Set `timeout=10.0` for page fetches (same as `discover_feeds()`).

## Code Examples

### BFS Deep Discovery (new function)

```python
async def discover_feeds_deep(url: str, max_depth: int = 1) -> list[DiscoveredFeed]:
    """Discover feeds using BFS crawling up to max_depth.

    Args:
        url: Starting URL to discover feeds from.
        max_depth: Maximum crawl depth (1 = current page only, 2 = +linked pages, etc.)

    Returns:
        List of unique DiscoveredFeed objects found.
    """
    from src.discovery import normalize_url, parse_link_elements, validate_feed
    from src.providers.rss_provider import BROWSER_HEADERS

    all_feeds: list[DiscoveredFeed] = []
    seen_feed_urls: set[str] = set()
    visited_pages: set[str] = set()

    # Queue items: (url, depth)
    queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()
    await queue.put((normalize_url(url), 0))

    # Semaphore to limit concurrent fetches
    semaphore = asyncio.Semaphore(5)

    async with httpx.AsyncClient(headers=BROWSER_HEADERS, follow_redirects=True, timeout=10.0) as client:
        while not queue.empty():
            page_url, depth = await queue.get()

            if depth > max_depth:
                continue
            if page_url in visited_pages:
                continue
            visited_pages.add(page_url)

            async def fetch_page(url: str) -> tuple[str | None, str]:
                async with semaphore:
                    try:
                        response = await client.get(url)
                        return response.text, str(response.url)
                    except Exception as e:
                        logger.debug(f"Failed to fetch {url}: {e}")
                        return None, url

            html, final_url = await fetch_page(page_url)
            if not html:
                continue

            # Parse feeds on this page
            discovered = parse_link_elements(html, final_url)

            # Validate and dedupe feeds
            for feed in discovered:
                if feed.url in seen_feed_urls:
                    continue
                is_valid, feed_type = await validate_feed(feed.url)
                if is_valid:
                    seen_feed_urls.add(feed.url)
                    all_feeds.append(DiscoveredFeed(
                        url=feed.url,
                        title=feed.title,
                        feed_type=feed_type,
                        source=f"autodiscovery (depth {depth})",
                        page_url=final_url,
                    ))

            # Enqueue linked pages if not at max depth
            if depth < max_depth:
                # Extract <a href> links from HTML for further crawling
                # (Implementation would use BeautifulSoup to find links)
                pass

    return all_feeds
```

### CLI Command Registration (in `src/cli/__init__.py`)

```python
# Add this import to src/cli/__init__.py:
from src.cli import discover  # noqa: F401
```

### Output Format for Discovered Feeds

```
Type  | Title                     | URL
------+---------------------------+------------------------------------------
atom  | Main Feed                 | https://example.com/feed/atom.xml
rss   | RSS 2.0                   | https://example.com/feed/rss.xml
rdf   | —                         | https://example.com/rdf

Discovered 3 feed(s)
```

### Error Output

```
Error: Failed to discover feeds: Connection timeout
```

```
No feeds discovered.
```

## Open Questions

1. **Should deep crawling extract ALL <a href> links or only same-domain links?**
   - What we know: Current `discover_feeds()` only does autodiscovery + well-known paths
   - What's unclear: Whether crawling should stay on same domain or follow external links
   - Recommendation: Same-domain only to avoid spider traps and irrelevant content

2. **Should we use the existing `discover_feeds()` or create new `discover_feeds_deep()`?**
   - What we know: `discover_feeds()` is imported by other modules
   - What's unclear: Whether any external code calls `discover_feeds()` directly
   - Recommendation: Create new `discover_feeds_deep()` function to avoid breaking existing callers

3. **How to extract links from HTML for crawling?**
   - What we know: `parse_link_elements()` uses BeautifulSoup
   - What's unclear: Whether to reuse link extraction logic
   - Recommendation: Create a helper `extract_links(html, base_url)` similar to `parse_link_elements()`

## Environment Availability

> Step 2.6: SKIPPED (no external dependencies - all required tools already in project)

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.6+ | All | ✓ | 3.13.x | — |
| httpx | Discovery HTTP | ✓ | 0.27.x | — |
| BeautifulSoup4 + lxml | HTML parsing | ✓ | 4.12.x / 5.x | — |
| uvloop | Async wrapper | ✓ | (installed) | — |
| click | CLI | ✓ | 8.1.x | — |
| rich | Table output | ✓ | (installed) | — |

## Sources

### Primary (HIGH confidence)
- `src/discovery/__init__.py` - Existing `discover_feeds()` implementation
- `src/discovery/models.py` - `DiscoveredFeed` dataclass definition
- `src/discovery/parser.py` - `parse_link_elements()` for feed discovery
- `src/discovery/fetcher.py` - `validate_feed()` for feed validation
- `src/cli/feed.py` - CLI patterns: `uvloop.run()`, progress bars, error handling
- `src/cli/article.py` - Rich Table patterns for output formatting
- `src/cli/__init__.py` - CLI group registration pattern

### Secondary (MEDIUM confidence)
- CLAUDE.md - Project tech stack (click, httpx, BeautifulSoup4, uvloop)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries are project standards
- Architecture: HIGH - Clear patterns from existing codebase
- Pitfalls: MEDIUM - BFS patterns are standard but crawling edge cases may emerge

**Research date:** 2026-03-27
**Valid until:** 2026-04-26 (30 days - stable domain)
