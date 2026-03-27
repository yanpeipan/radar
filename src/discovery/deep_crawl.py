"""Deep BFS crawling for feed discovery with rate limiting and robots.txt compliance (DISC-07, DISC-08)."""
from __future__ import annotations

import asyncio
import time
from collections import deque
from urllib.parse import urljoin, urlparse

import httpx
from scrapling import Selector
from robotexclusionrulesparser import RobotExclusionRulesParser

from src.discovery.common_paths import matches_feed_path_pattern, generate_feed_candidates
from src.discovery.fetcher import validate_feed
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


async def _probe_well_known_paths(page_url: str) -> list[DiscoveredFeed]:
    """Probe well-known feed paths on a page URL.

    Args:
        page_url: Base page URL to probe.

    Returns:
        List of DiscoveredFeed found via well-known path probing.
    """
    results = []

    # Generate candidates using pattern-based approach
    candidates = generate_feed_candidates(page_url)

    for candidate in candidates:
        is_valid, feed_type = await validate_feed(candidate)
        if is_valid:
            results.append(DiscoveredFeed(
                url=candidate,
                title=None,
                feed_type=feed_type,
                source='well_known_path',
                page_url=page_url,
            ))

    return results


async def _discover_feeds_on_page(html: str, page_url: str) -> list[DiscoveredFeed]:
    """Discover feeds on a single page via autodiscovery + well-known paths.

    Args:
        html: Raw HTML content.
        page_url: URL the HTML was fetched from.

    Returns:
        List of DiscoveredFeed found on the page.
    """
    # Try autodiscovery first
    discovered = parse_link_elements(html, page_url)

    if discovered:
        # Validate each feed
        valid_feeds = []
        for feed in discovered:
            is_valid, feed_type = await validate_feed(feed.url)
            if is_valid:
                valid_feeds.append(DiscoveredFeed(
                    url=feed.url,
                    title=feed.title,
                    feed_type=feed_type,
                    source=feed.source,
                    page_url=feed.page_url,
                ))
        if valid_feeds:
            return valid_feeds

    # Fallback to well-known path probing
    return await _probe_well_known_paths(page_url)


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
        try:
            async with httpx.AsyncClient(
                headers=BROWSER_HEADERS,
                follow_redirects=True,
                timeout=10.0,
            ) as client:
                response = await client.get(start_url)
                if response.status_code == 200:
                    html = response.text
                    page_url = str(response.url)
                    return await _discover_feeds_on_page(html, page_url)
                # Non-200: fall through to well-known path probing
        except Exception:
            pass

        # Fall back to well-known path probing (handles sites that return 403, etc.)
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
                async with httpx.AsyncClient(
                    headers=BROWSER_HEADERS,
                    follow_redirects=True,
                    timeout=10.0,
                ) as client:
                    response = await client.get(url)
                    if response.status_code != 200:
                        return None, url
                    return response.text, str(response.url)
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
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(robots_url)
                    if response.status_code == 200:
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
            List of absolute URLs found on the page.
        """
        links = []
        page = Selector(content=html)

        # Check for <base href> override
        base_override: str | None = None
        head = page.find('head')
        if head:
            base_tag = head.find('base[href]')
            if base_tag:
                base_override = base_tag.attrib.get('href')

        # Find all <a href=""> tags
        for anchor in page.css('a[href]'):
            href = anchor.attrib.get('href')

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

            # Only follow links that match feed path patterns (BFS focused on feed discovery)
            if not matches_feed_path_pattern(path):
                continue

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
