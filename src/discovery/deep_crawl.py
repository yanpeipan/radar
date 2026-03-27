"""Deep BFS crawling for feed discovery with rate limiting and robots.txt compliance (DISC-07, DISC-08)."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from urllib.parse import urljoin, urlparse

import feedparser

from scrapling import Fetcher, Selector, DynamicFetcher

# Suppress scrapling 0.4.x deprecation warning logged unconditionally in DynamicFetcher.__init__
_scrapling_logger = logging.getLogger("scrapling")
_scrapling_logger.disabled = True
from robotexclusionrulesparser import RobotExclusionRulesParser

from src.discovery.common_paths import matches_feed_path_pattern, generate_feed_candidates
from src.discovery.models import DiscoveredFeed
from src.discovery.parser import parse_link_elements, resolve_url
from src.providers.rss_provider import BROWSER_HEADERS

def normalize_url_for_visit(url: str) -> str:
    """Normalize URL for visited-set tracking.

    - Remove fragments (#...)
    - Strip trailing slashes
    - Lowercase scheme + host

    Args:
        url: URL to normalize.

    Returns:
        Normalized URL string.
    """
    parsed = urlparse(url)

    # Remove fragment
    scheme_host = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"

    # Strip trailing slash from path
    path = parsed.path.rstrip('/')
    if not path:
        path = '/'

    # Reconstruct without fragment
    return f"{scheme_host}{path}"


async def _quick_validate_feed(url: str) -> tuple[bool, str | None]:
    """Quick feed validation via HEAD request only.

    Only checks HTTP 200 + Content-Type header, skipping full feed parsing.
    This is ~10x faster than validate_feed which does feedparser.parse().

    Args:
        url: The feed URL to validate.

    Returns:
        Tuple of (is_valid, feed_type).
    """
    import httpx
    FEED_TYPE_MAP = {
        'application/rss+xml': 'rss',
        'application/atom+xml': 'atom',
        'application/rdf+xml': 'rdf',
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=5.0) as client:
            response = await client.head(url)
            if response.status_code != 200:
                return False, None
            content_type = response.headers.get('content-type', '').lower()
            # Check MIME type
            for mime, ftype in FEED_TYPE_MAP.items():
                if mime in content_type:
                    return True, ftype
            # Fallback: detect from URL path for generic xml types
            if 'xml' in content_type:
                lower_url = url.lower()
                if '/rss' in lower_url or '.rss' in lower_url:
                    return True, 'rss'
                if '/atom' in lower_url:
                    return True, 'atom'
                if '/rdf' in lower_url:
                    return True, 'rdf'
            return False, None
    except Exception:
        return False, None


async def _extract_feed_title(url: str) -> str | None:
    """Extract title from a feed URL using feedparser.

    Args:
        url: Feed URL to fetch and parse.

    Returns:
        Feed title string if found, None otherwise.
    """
    try:
        # Use httpx directly since feedparser works with bytes/content
        import httpx
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            response = await client.get(url)
            if response.status_code != 200:
                return None
            feed = feedparser.parse(response.content)
            if feed.feed:
                return feed.feed.get('title')
            return None
    except Exception:
        return None


async def _probe_well_known_paths(page_url: str, html: str | None = None) -> list[DiscoveredFeed]:
    """Probe well-known feed paths on a page URL.

    Args:
        page_url: Base page URL to probe.
        html: Optional HTML content for dynamic subdirectory discovery.

    Returns:
        List of DiscoveredFeed found via well-known path probing.
    """
    # Generate candidates
    candidates = generate_feed_candidates(page_url, html)

    # Validate all candidates concurrently (was sequential - major bottleneck)
    validation_tasks = [_quick_validate_feed(c) for c in candidates]
    validation_results = await asyncio.gather(*validation_tasks)

    valid_candidates = []
    for candidate, (is_valid, feed_type) in zip(candidates, validation_results):
        if is_valid:
            valid_candidates.append((candidate, feed_type or 'rss'))

    if not valid_candidates:
        return []

    results = []
    for candidate, feed_type in valid_candidates:
        results.append(DiscoveredFeed(
            url=candidate,
            title=None,
            feed_type=feed_type,
            source='well_known_path',
            page_url=page_url,
        ))

    return results


async def _find_feed_links_on_page(html: str, page_url: str) -> list[DiscoveredFeed]:
    """Find feed links on a page using CSS selectors.

    Uses CSS attribute selectors to find links containing feed-related
    patterns (rss, feed, atom, .xml) directly on the page.

    Args:
        html: Raw HTML content.
        page_url: URL the HTML was fetched from.

    Returns:
        List of DiscoveredFeed found via CSS selector link discovery.
    """
    from urllib.parse import urlparse as _urlparse

    results = []
    page = Selector(content=html)

    # Check for <base href> override
    base_override: str | None = None
    head = page.find('head')
    if head:
        base_tag = head.find('base[href]')
        if base_tag:
            base_override = base_tag.attrib['href']

    # Use CSS selectors to find feed-like links directly
    feed_selectors = [
        'a[href*="rss"]',
        'a[href*="feed"]',
        'a[href*="atom"]',
        'a[href$=".xml"]',
    ]

    found_urls: set[str] = set()

    for selector in feed_selectors:
        for anchor in page.css(selector):
            href = anchor.attrib.get('href', '')

            # Skip non-HTTP URLs
            if not href or href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                continue

            # Resolve relative URLs
            if base_override:
                absolute = urljoin(base_override, href)
            else:
                absolute = urljoin(page_url, href)

            parsed = _urlparse(absolute)

            # Skip non-HTTP(S)
            if parsed.scheme not in ('http', 'https'):
                continue

            # Skip different hosts
            if parsed.netloc.lower() != _urlparse(page_url).netloc.lower():
                continue

            # Skip non-HTML resources (simple heuristic)
            path = parsed.path.lower()
            if any(path.endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.gif', '.css', '.js', '.ico', '.svg', '.woff', '.pdf', '.zip', '.mp3', '.mp4')):
                continue

            if absolute in found_urls:
                continue
            found_urls.add(absolute)

            # Validate via HTTP (quick HEAD + Content-Type only)
            is_valid, feed_type = await _quick_validate_feed(absolute)
            if is_valid:
                results.append(DiscoveredFeed(
                    url=absolute,
                    title=None,
                    feed_type=feed_type or 'rss',
                    source='css_selector',
                    page_url=page_url,
                ))

    return results


async def _discover_feeds_on_page(html: str, page_url: str) -> list[DiscoveredFeed]:
    """Discover feeds on a single page via autodiscovery + CSS selectors + well-known paths.

    Args:
        html: Raw HTML content.
        page_url: URL the HTML was fetched from.

    Returns:
        List of DiscoveredFeed found on the page.
    """
    # Try autodiscovery first
    discovered = parse_link_elements(html, page_url)

    if discovered:
        # Validate all feeds concurrently (was sequential validate_feed)
        val_tasks = [_quick_validate_feed(f.url) for f in discovered]
        val_results = await asyncio.gather(*val_tasks)
        valid_feeds = [
            DiscoveredFeed(
                url=f.url,
                title=f.title,
                feed_type=vt[1] or 'rss',
                source=f.source,
                page_url=f.page_url,
            )
            for f, vt in zip(discovered, val_results) if vt[0]
        ]
        if valid_feeds:
            return valid_feeds

    # Try CSS selector link discovery
    css_feeds = await _find_feed_links_on_page(html, page_url)
    if css_feeds:
        return css_feeds

    # Fallback to well-known path probing
    return await _probe_well_known_paths(page_url, html)


async def deep_crawl(start_url: str, max_depth: int = 1) -> list[DiscoveredFeed]:
    """Discover feeds using BFS crawling up to max_depth.

    Args:
        start_url: Starting URL for crawling.
        max_depth: Maximum crawl depth (1 = current page only, 2+ = BFS crawl).

    Returns:
        List of DiscoveredFeed objects found across all crawled pages.
    """
    if max_depth <= 1:
        # Single-page discovery: fetch and discover
        html = None
        page_url = start_url
        try:
            response = await asyncio.to_thread(
                Fetcher.get, start_url, headers=BROWSER_HEADERS
            )
            if response.status == 200 and response.text and len(response.text) > 100:
                html = response.text
                page_url = response.url
        except Exception:
            pass

        # Adaptive: if static fetcher got empty content, try DynamicFetcher (Playwright)
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

        if html:
            return await _discover_feeds_on_page(html, page_url)

        # Fall back to well-known path probing (handles JS-rendered pages, 403, etc.)
        return await _probe_well_known_paths(start_url)

    # Deep crawl (max_depth > 1)
    # Normalize start URL
    normalized_start = normalize_url_for_visit(start_url)

    # Probe well-known paths on start URL first (before BFS crawl)
    # This handles sites that return 403/404 on main page but have feeds at well-known paths
    start_feeds = await _probe_well_known_paths(start_url)
    if start_feeds:
        return start_feeds

    # BFS queue: (url, depth)
    queue: deque[tuple[str, int]] = deque()
    queue.append((start_url, 1))

    visited: set[str] = set()
    visited.add(normalized_start)

    # Rate limiting: last request timestamp per host
    last_request_time: dict[str, float] = {}

    # robots.txt cache: parsed robots per host
    robots_cache: dict[str, RobotExclusionRulesParser | None] = {}

    # Semaphore to limit concurrent requests (5 concurrent)
    semaphore = asyncio.Semaphore(5)

    # All discovered feeds
    all_feeds: list[DiscoveredFeed] = []

    def get_host(url: str) -> str:
        """Extract host from URL."""
        return urlparse(url).netloc.lower()

    async def _fetch_page(url: str) -> tuple[str | None, str]:
        """Fetch a page and return (html, final_url)."""
        async with semaphore:
            host = get_host(url)

            # Rate limiting: 2 seconds per host
            now = time.time()
            if host in last_request_time:
                sleep_time = max(0, 2.0 - (now - last_request_time[host]))
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
            last_request_time[host] = time.time()

            try:
                response = await asyncio.to_thread(
                    Fetcher.get, url, headers=BROWSER_HEADERS
                )
                if response.status != 200:
                    return None, url
                return response.text, response.url
            except Exception:
                return None, url

    async def _check_robots(url: str, depth: int) -> bool:
        """Check if robots.txt allows crawling a URL.

        Only checks when depth > 1 (lazy mode).

        Args:
            url: URL to check.
            depth: Current crawl depth.

        Returns:
            True if crawling is allowed, False otherwise.
        """
        if depth <= 1:
            # Depth 1 is like normal browser - don't check robots.txt
            return True

        host = get_host(url)

        if host not in robots_cache:
            # Fetch and parse robots.txt
            robots_url = f"{urlparse(url).scheme.lower()}://{host}/robots.txt"
            parser = RobotExclusionRulesParser()
            try:
                response = await asyncio.to_thread(Fetcher.get, robots_url)
                if response.status == 200:
                    parser.parse(response.text.splitlines())
                else:
                    # No robots.txt - permissive
                    parser = None
            except Exception:
                parser = None
            robots_cache[host] = parser

        parser = robots_cache[host]
        if parser is None:
            # No robots.txt - allow crawling
            return True

        return parser.can_fetch(url, user_agent='*')

    def _extract_links(html: str, page_url: str, base_host: str) -> list[str]:
        """Extract internal links from HTML.

        Args:
            html: Raw HTML content.
            page_url: URL the HTML was fetched from.
            base_host: Host to restrict links to (same-domain).

        Returns:
            List of absolute URLs found on the page that may be feed URLs.
        """
        links = []
        page = Selector(content=html)

        # Check for <base href> override
        base_override: str | None = None
        head = page.find('head')
        if head:
            base_tag = head.find('base[href]')
            if base_tag:
                base_override = base_tag.attrib['href']

        # Use CSS selectors to find feed-like links directly
        # Look for hrefs containing: rss, feed, atom in the path
        feed_selectors = [
            'a[href*="rss"]',
            'a[href*="feed"]',
            'a[href*="atom"]',
            'a[href$=".xml"]',
        ]

        for selector in feed_selectors:
            for anchor in page.css(selector):
                href = anchor.attrib['href']

                # Skip non-HTTP URLs
                if not href or href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                    continue

                # Resolve relative URLs
                if base_override:
                    absolute = urljoin(base_override, href)
                else:
                    absolute = urljoin(page_url, href)

                parsed = urlparse(absolute)

                # Skip non-HTTP(S)
                if parsed.scheme not in ('http', 'https'):
                    continue

                # Skip different hosts
                if parsed.netloc.lower() != base_host:
                    continue

                # Skip non-HTML resources (simple heuristic)
                path = parsed.path.lower()
                if any(path.endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.gif', '.css', '.js', '.ico', '.svg', '.woff', '.pdf', '.zip', '.mp3', '.mp4')):
                    continue

                # Validate path ends with feed-like pattern using matches_feed_path_pattern (fallback validation)
                if not matches_feed_path_pattern(path):
                    continue

                if absolute not in links:
                    links.append(absolute)

        return links

    # Process queue with BFS
    while queue:
        url, depth = queue.popleft()

        if depth > max_depth:
            continue

        # Check robots.txt (only if depth > 1)
        if not await _check_robots(url, depth):
            continue

        # Fetch page
        html, final_url = await _fetch_page(url)
        if html is None:
            continue

        # Normalize final URL for visited check
        normalized_final = normalize_url_for_visit(final_url)
        if normalized_final in visited:
            continue
        visited.add(normalized_final)

        # Extract links for next depth
        base_host = get_host(final_url)

        # Discover feeds on current page
        page_feeds = await _discover_feeds_on_page(html, final_url)
        all_feeds.extend(page_feeds)

        # Queue internal links for next depth
        if depth < max_depth:
            links = _extract_links(html, final_url, base_host)
            for link in links:
                normalized_link = normalize_url_for_visit(link)
                if normalized_link not in visited:
                    visited.add(normalized_link)
                    queue.append((link, depth + 1))

    # Deduplicate feeds by URL
    seen: set[str] = set()
    unique_feeds: list[DiscoveredFeed] = []
    for feed in all_feeds:
        if feed.url not in seen:
            seen.add(feed.url)
            unique_feeds.append(feed)

    return unique_feeds
