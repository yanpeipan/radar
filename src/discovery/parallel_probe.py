"""Parallel feed path probing with asyncio and adaptive expansion.

This module provides concurrent probing of well-known feed paths using asyncio,
with quality-based selection to find the best feed URL.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import feedparser

from src.discovery.common_paths import _SUB_DIRECTORY_PATTERNS
from src.discovery.models import DiscoveredFeed
from src.utils.scraping_utils import async_fetch_with_fallback

if TYPE_CHECKING:
    from scrapling.engines.toolbelt.custom import Response

logger = logging.getLogger(__name__)

_ROOT_PATHS = (
    "/feed",
    "/feed/",
    "/rss",
    "/rss.xml",
    "/atom.xml",
    "/feed.xml",
    "/index.xml",
)


def _build_root_candidates(base_url: str) -> list[str]:
    """Build root-level candidate feed URLs.

    Args:
        base_url: Base URL (e.g., 'https://example.com').

    Returns:
        List of candidate URLs for root-level paths.
    """
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if parsed.port:
        base += f":{parsed.port}"

    return [base + path for path in _ROOT_PATHS]


def _build_subdir_candidates(base_url: str) -> list[str]:
    """Build subdirectory-level candidate feed URLs.

    Args:
        base_url: Base URL (e.g., 'https://example.com').

    Returns:
        List of candidate URLs for subdirectory-level paths.
    """
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if parsed.port:
        base += f":{parsed.port}"

    return [base + path for path in _SUB_DIRECTORY_PATTERNS]


async def _probe_one(url: str) -> DiscoveredFeed | None:
    """Probe a single feed URL.

    Args:
        url: Feed URL to probe.

    Returns:
        DiscoveredFeed if valid feed found, None otherwise.
    """
    try:
        response = await async_fetch_with_fallback(url, timeout=30)
        if response is None:
            return None
        # Skip 429 rate limit without retry (per D-02, D-05)
        if response.status == 429:
            return None
        # Other non-200 responses treated as no feed (per D-06)
        if response.status != 200:
            return None
        return await _validate_feed(url, response)
    except Exception:
        return None


async def _validate_feed(url: str, response: Response) -> DiscoveredFeed | None:
    """Validate feed content and create DiscoveredFeed.

    Args:
        url: Feed URL.
        response: HTTP response with feed content.

    Returns:
        DiscoveredFeed if valid feed, None otherwise.
    """
    try:
        raw_content = (
            response.body
            if hasattr(response, "body")
            else getattr(response, "html_content", "")
        )
        if isinstance(raw_content, bytes):
            raw_content = raw_content.decode("utf-8", errors="replace")
        parsed = feedparser.parse(raw_content)

        # A valid feed must have entries
        if not parsed.entries:
            return None

        # Detect feed type from content
        feed_type = "rss"
        if hasattr(parsed, "version"):
            version = str(parsed.version).lower()
            if "atom" in version:
                feed_type = "atom"
            elif "rdf" in version:
                feed_type = "rdf"

        title = parsed.feed.get("title") if parsed.feed else None
        entry_count = len(parsed.entries)

        return DiscoveredFeed(
            url=url,
            title=title,
            feed_type=feed_type,
            source="well_known_path",  # Per D-08
            page_url=url,
            valid=True,
            metadata=entry_count,  # Store entry count for quality scoring
        )
    except Exception:
        return None


def _score_feed(feed: DiscoveredFeed) -> tuple[int, int, int]:
    """Score a feed for quality selection.

    Args:
        feed: DiscoveredFeed to score.

    Returns:
        Tuple of (type_score, entry_count, -url_length) for sorting.
        RSS 2.0 = 2, Atom = 1 (higher is better).
        More entries preferred.
        Shorter URL preferred as tiebreaker.
    """
    # RSS 2.0 = 2, Atom = 1, RDF = 1
    type_score = 2 if feed.feed_type == "rss" else 1
    # Entry count from metadata
    entry_count = getattr(feed, "metadata", 0) or 0
    # URL length as tiebreaker (shorter = more likely root)
    url_length = len(feed.url)
    return (type_score, entry_count, -url_length)


async def probe_feed_paths_parallel(
    url: str, html: str | None = None
) -> list[DiscoveredFeed]:
    """Probe well-known feed paths concurrently with adaptive expansion.

    Probes root-level paths first (8 candidates). If no feed found,
    probes subdirectory-level paths (12 candidates). Returns highest
    quality feeds (RSS 2.0 > Atom, more entries preferred).

    Args:
        url: Base page URL to probe.
        html: Optional HTML content (unused, kept for API compatibility).

    Returns:
        List of DiscoveredFeed found via parallel path probing.
    """
    # Build root candidates (8 paths)
    root_candidates = _build_root_candidates(url)

    # Probe root paths concurrently
    root_results = await asyncio.gather(*[_probe_one(u) for u in root_candidates])
    valid_root_feeds = [r for r in root_results if r is not None]

    # If root feeds found, skip subdirectory probing (per D-03)
    if valid_root_feeds:
        all_valid = valid_root_feeds
    else:
        # No root feeds, probe subdirectory paths (12 paths)
        subdir_candidates = _build_subdir_candidates(url)
        subdir_results = await asyncio.gather(
            *[_probe_one(u) for u in subdir_candidates]
        )
        all_valid = [r for r in subdir_results if r is not None]

    # If no valid feeds found, return empty
    if not all_valid:
        return []

    # Quality-based selection (per D-04): wait all probes, return best
    # Score each feed
    scored = [(f, _score_feed(f)) for f in all_valid]
    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    # Return all with highest score (they are equally good)
    top_score = scored[0][1]
    best_feeds = [f for f, s in scored if s == top_score]

    return best_feeds
