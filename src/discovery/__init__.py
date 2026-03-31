"""Discovery service for RSS/Atom feed auto-discovery from website URLs."""

from __future__ import annotations

import logging

from src.discovery.common_paths import generate_feed_candidates
from src.discovery.parallel_probe import probe_feed_paths_parallel
from src.discovery.deep_crawl import deep_crawl
from src.discovery.models import DiscoveredFeed, DiscoveredResult, LinkSelector

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
    """Generate candidate feed URLs from well-known root paths.

    Args:
        page_url: Base page URL to probe.

    Returns:
        List of candidate feed URLs.
    """
    return generate_feed_candidates(page_url)


async def discover_feeds(
    url: str, max_depth: int = 1, auto_discover: bool = True
) -> DiscoveredResult:
    """Discover RSS/Atom/RDF feeds from a website URL.

    Args:
        url: Website URL to discover feeds from.
        max_depth: Maximum crawl depth (1 = current page only, 2+ = BFS crawl).
        auto_discover: Whether to run auto-discovery (default: True).

    Returns:
        DiscoveredResult containing list of DiscoveredFeed objects found.
        For max_depth=1, selectors contains link path prefix counts.
    """
    # Single-page discovery: delegate to deep_crawl (handles subdirectory probing)
    return await deep_crawl(url, max_depth, auto_discover)


# Public exports
__all__ = [
    "discover_feeds",
    "DiscoveredFeed",
    "DiscoveredResult",
    "LinkSelector",
    "deep_crawl",
    "normalize_url",
    "probe_well_known_paths",
    "probe_feed_paths_parallel",
]
