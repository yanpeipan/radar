from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LinkSelector:
    """Represents a CSS path selector with example link info.

    Attributes:
        path: The path prefix (e.g., '/news/').
        link: An example full URL matching this selector.
        text: The text content of the example link.
        count: Number of links matching this selector.
    """
    path: str
    link: str
    text: str
    count: int


@dataclass
class DiscoveredResult:
    """Result of a feed discovery operation.

    Attributes:
        url: The URL that was searched for feeds.
        max_depth: The maximum crawl depth used.
        feeds: List of discovered feeds.
        selectors: Dict mapping path prefix to Selector with path, link, text, count (for max_depth=1).
    """
    url: str
    max_depth: int
    feeds: list["DiscoveredFeed"] = field(default_factory=list)
    selectors: dict[str, LinkSelector] = field(default_factory=dict)


@dataclass
class DiscoveredFeed:
    """Represents a discovered RSS/Atom/RDF feed from a website URL.

    Attributes:
        url: Absolute URL of the discovered feed.
        title: Title of the feed if available from autodiscovery link, else None.
        feed_type: Feed type string ('rss', 'atom', 'rdf') detected from type attribute.
        source: How the feed was discovered ('autodiscovery' or 'well_known_path').
        page_url: The original page URL where this feed was discovered.
    """
    url: str
    title: Optional[str]
    feed_type: str  # 'rss', 'atom', or 'rdf'
    source: str  # 'autodiscovery' or 'well_known_path'
    page_url: str  # Original page URL
