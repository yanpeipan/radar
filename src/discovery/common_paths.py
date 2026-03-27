"""Well-known feed URL paths for fallback probing (DISC-02)."""
from __future__ import annotations

import re
from typing import Sequence

# Subdirectory names for wildcard pattern substitution (for candidate generation)
_SUBDIR_NAMES = ("feed", "rss", "blog", "news", "atom", "feeds")

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

# Subdirectory patterns for candidate generation (use {subdir} placeholder)
_SUBGRID_PATTERNS = (
    "/{subdir}/rss.xml",
    "/{subdir}/atom.xml",
    "/{subdir}/feed.xml",
)


def generate_feed_candidates(base_url: str) -> list[str]:
    """Generate candidate feed URLs from base URL using well-known path patterns.

    Args:
        base_url: Base URL to generate candidates from (e.g., 'https://example.com').

    Returns:
        List of candidate feed URLs including root-level and subdirectory paths.
    """
    # Parse base URL to extract scheme + host + port
    from urllib.parse import urlparse
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if parsed.port:
        base += f":{parsed.port}"

    candidates = []

    # Root-level candidates
    for path in _ROOT_PATH_PATTERNS:
        candidates.append(base + path)

    # Subdirectory candidates
    for pattern in _SUBGRID_PATTERNS:
        for subdir in _SUBDIR_NAMES:
            candidates.append(base + pattern.format(subdir=subdir))

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


# MIME types for feed Content-Type validation (DISC-04)
FEED_CONTENT_TYPES: tuple[str, ...] = (
    "application/rss+xml",
    "application/atom+xml",
    "application/rdf+xml",
    "application/xml",
    "text/xml",
)
