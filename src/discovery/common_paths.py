"""Well-known feed URL paths for fallback probing (DISC-02)."""
from __future__ import annotations

from typing import Sequence

WELL_KNOWN_PATHS: tuple[str, ...] = (
    "/feed",
    "/feed/",
    "/rss",
    "/rss.xml",
    "/atom.xml",
    "/feed.xml",
    "/index.xml",
    # Site-specific paths for major sites that block HTML fetch (Cloudflare, etc.)
    # These are NOT standard well-known paths — they are fallbacks for sites with
    # autodiscovery links that we cannot fetch due to bot protection.
    "/news/rss.xml",  # openai.com
)

# MIME types for feed Content-Type validation (DISC-04)
FEED_CONTENT_TYPES: tuple[str, ...] = (
    "application/rss+xml",
    "application/atom+xml",
    "application/rdf+xml",
    "application/xml",
    "text/xml",
)
