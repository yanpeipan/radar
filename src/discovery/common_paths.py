"""Well-known feed URL paths for fallback probing (DISC-02)."""
from __future__ import annotations

from typing import Sequence

# Standard well-known feed paths (probed at domain root)
WELL_KNOWN_PATHS: tuple[str, ...] = (
    "/feed",
    "/feed/",
    "/rss",
    "/rss.xml",
    "/atom.xml",
    "/feed.xml",
    "/index.xml",
)

# Common sub-directory paths that may contain feeds (probed with feed suffixes)
# These are relative paths appended to the domain root (e.g., /news/rss.xml)
_COMMON_FEED_SUBDIRS: tuple[str, ...] = (
    "/news",
    "/blog",
    "/updates",
    "/posts",
    "/articles",
    "/feed",
)

# MIME types for feed Content-Type validation (DISC-04)
FEED_CONTENT_TYPES: tuple[str, ...] = (
    "application/rss+xml",
    "application/atom+xml",
    "application/rdf+xml",
    "application/xml",
    "text/xml",
)
