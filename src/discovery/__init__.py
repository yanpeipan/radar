"""Discovery service for RSS/Atom feed auto-discovery from website URLs."""
from __future__ import annotations

import asyncio
import logging
from urllib.parse import urljoin

import httpx

from src.discovery.common_paths import WELL_KNOWN_PATHS, _COMMON_FEED_SUBDIRS
from src.discovery.deep_crawl import deep_crawl
from src.discovery.fetcher import is_bozo_feed, validate_feed
from src.discovery.models import DiscoveredFeed
from src.discovery.parser import parse_link_elements
from src.providers.rss_provider import BROWSER_HEADERS

logger = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """Normalize input URL by adding scheme if missing.

    Args:
        url: Input URL which may lack scheme.

    Returns:
        URL with scheme prepended.
    """
    url = url.strip()
    if not url:
        raise ValueError("URL cannot be empty")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def probe_well_known_paths(page_url: str) -> list[str]:
    """Generate candidate feed URLs from well-known paths.

    Args:
        page_url: Base page URL to probe.

    Returns:
        List of candidate feed URLs.
    """
    # Get base URL (scheme + host)
    parsed = httpx.URL(page_url)
    base = f"{parsed.scheme}://{parsed.host}"
    if parsed.port:
        base += f":{parsed.port}"

    candidates = []

    # Root-level well-known paths (e.g., /feed, /rss.xml)
    for path in WELL_KNOWN_PATHS:
        candidates.append(base + path)

    # Common sub-directory paths with feed suffixes (e.g., /news/rss.xml, /blog/atom.xml)
    for subdir in _COMMON_FEED_SUBDIRS:
        for suffix in ("/rss.xml", "/atom.xml", "/feed.xml"):
            candidates.append(base + subdir + suffix)

    return candidates


async def validate_and_wrap(
    url: str, page_url: str, source: str
) -> DiscoveredFeed | None:
    """Validate a feed URL and wrap in DiscoveredFeed if valid.

    Args:
        url: Feed URL to validate.
        page_url: Original page URL.
        source: Discovery source ('autodiscovery' or 'well_known_path').

    Returns:
        DiscoveredFeed if valid, None otherwise.
    """
    is_valid, feed_type = await validate_feed(url)
    if not is_valid:
        return None
    return DiscoveredFeed(
        url=url,
        title=None,
        feed_type=feed_type,
        source=source,
        page_url=page_url,
    )


async def discover_feeds(url: str, max_depth: int = 1) -> list[DiscoveredFeed]:
    """Discover RSS/Atom/RDF feeds from a website URL.

    Args:
        url: Website URL to discover feeds from.
        max_depth: Maximum crawl depth (1 = current page only, 2+ = BFS crawl).

    Returns:
        List of DiscoveredFeed objects found on the page.
        Empty list if no feeds found or page cannot be fetched.
    """
    # Deep crawl for max_depth > 1
    if max_depth > 1:
        return await deep_crawl(url, max_depth)

    try:
        normalized = normalize_url(url)
    except ValueError:
        return []

    # Fetch page HTML (try even if non-200, since autodiscovery may still find feeds)
    html: str | None = None
    page_url = normalized
    try:
        async with httpx.AsyncClient(
            headers=BROWSER_HEADERS,
            follow_redirects=True,
            timeout=10.0,
        ) as client:
            response = await client.get(normalized)
            if response.status_code == 200:
                html = response.text
                page_url = str(response.url)
    except Exception as e:
        logger.debug(f"Failed to fetch page {normalized}: {e}")

    # Try autodiscovery first (only if we have HTML)
    discovered = parse_link_elements(html, page_url) if html else []

    if discovered:
        # Validate and filter autodiscovery feeds concurrently
        async def validate_one(feed: DiscoveredFeed) -> DiscoveredFeed | None:
            # Skip bozo feeds for autodiscovery
            is_bozo, _ = is_bozo_feed(feed.url)
            if is_bozo:
                return None
            is_valid, feed_type = await validate_feed(feed.url)
            if not is_valid:
                return None
            return DiscoveredFeed(
                url=feed.url,
                title=feed.title,
                feed_type=feed_type,
                source=feed.source,
                page_url=feed.page_url,
            )

        results = await asyncio.gather(*[validate_one(f) for f in discovered])
        valid_feeds = [f for f in results if f is not None]
        if valid_feeds:
            return valid_feeds

    # Fallback to well-known paths
    candidates = probe_well_known_paths(page_url)

    # Validate all candidates concurrently
    async def check_candidate(candidate: str) -> DiscoveredFeed | None:
        return await validate_and_wrap(candidate, page_url, "well_known_path")

    results = await asyncio.gather(*[check_candidate(c) for c in candidates])
    valid_feeds = [f for f in results if f is not None]

    return valid_feeds


# Public exports
__all__ = ["discover_feeds", "DiscoveredFeed", "WELL_KNOWN_PATHS", "deep_crawl"]
