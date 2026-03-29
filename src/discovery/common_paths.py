"""Well-known feed URL paths for fallback probing (DISC-02)."""
from __future__ import annotations

import re
from typing import Sequence

# Root-level well-known paths for candidate generation
_ROOT_PATH_PATTERNS = (
    "/feed",
    "/feed/",
    "/rss",
    "/rss.xml",
    "/atom.xml",
    "/feed.xml",
    "/index.xml",
)

def generate_feed_candidates(base_url: str, _html: str | None = None) -> list[str]:
    """Generate candidate feed URLs from base URL.

    If html is provided, uses dynamic subdirectory discovery from page links.
    Otherwise falls back to root-level patterns only.

    Args:
        base_url: Base URL to generate candidates from (e.g., 'https://example.com').
        html: Optional HTML content for dynamic subdirectory discovery.

    Returns:
        List of candidate feed URLs including root-level and subdirectory paths.
    """
    from urllib.parse import urlparse
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if parsed.port:
        base += f":{parsed.port}"

    candidates = []

    # Root-level candidates (always included)
    for path in _ROOT_PATH_PATTERNS:
        candidates.append(base + path)

    return candidates


# Regex patterns for feed-related URL paths
# These replace both WELL_KNOWN_PATHS and _COMMON_FEED_SUBDIRS
# Each pattern matches URL paths that may be feed URLs
_FEED_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Root-level: /feed, /feed/, /feed.xml, /feed.xml/, /rss, /rss.xml, /atom.xml, /feed.xml, /index.xml
    re.compile(r"^/feed/?\.?xml$"),
    re.compile(r"^/feed/?$"),
    re.compile(r"^/rss\.?xml$"),
    re.compile(r"^/rss$"),
    re.compile(r"^/atom\.xml$"),
    re.compile(r"^/feed\.xml$"),
    re.compile(r"^/index\.xml$"),
    # Subdirectory-level: /{anything}/rss.xml, /{anything}/atom.xml, /{anything}/feed.xml
    re.compile(r"^/[^/]+/rss\.xml$"),
    re.compile(r"^/[^/]+/atom\.xml$"),
    re.compile(r"^/[^/]+/feed\.xml$"),
)


def matches_feed_path_pattern(path: str) -> bool:
    """Check if a URL path matches any feed path pattern.

    Args:
        path: URL path to check (e.g., '/news/rss.xml', '/feed').

    Returns:
        True if the path matches any feed-related pattern.
    """
    return any(p.match(path) for p in _FEED_PATH_PATTERNS)


# Feed MIME types from trafilatura (DISC-04)
from trafilatura.feeds import FEED_TYPES

FEED_CONTENT_TYPES: tuple[str, ...] = tuple(FEED_TYPES)
