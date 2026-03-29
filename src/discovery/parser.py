"""HTML link element parser for feed autodiscovery (DISC-01, DISC-03)."""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin, urlparse

from scrapling import Selector
from trafilatura.feeds import FEED_TYPES, BLACKLIST, LINK_VALIDATION_RE

from src.discovery.models import DiscoveredFeed


def resolve_url(page_url: str, href: str, base_href: str | None = None) -> str:
    """Resolve a relative URL to an absolute URL.

    Args:
        page_url: The original page URL.
        href: The href attribute value (may be relative or absolute).
        base_href: Optional <base href> override from page head.

    Returns:
        Absolute URL string.
    """
    if base_href:
        return urljoin(base_href, href)
    return urljoin(page_url, href)


# Comprehensive feed MIME types (from trafilatura)
# FEED_TYPES contains all known feed MIME types
_FEED_TYPE_KEYWORDS = ('atom', 'rdf', 'rss', 'json')  # ordered priority


def extract_feed_type(content_type: str) -> str | None:
    """Extract feed type from Content-Type string.

    Args:
        content_type: Content-Type header value.

    Returns:
        'rss', 'atom', 'rdf', 'json' or None if not a feed type.
    """
    ct_lower = content_type.lower()
    # Check if content_type matches any known feed MIME type from trafilatura
    if any(ft in ct_lower for ft in FEED_TYPES):
        # Determine feed type from MIME type keywords
        for keyword in _FEED_TYPE_KEYWORDS:
            if keyword in ct_lower:
                return keyword if keyword != 'rdf' else 'rdf'
    return None


def parse_link_elements(html: str, page_url: str) -> list[DiscoveredFeed]:
    """Parse HTML for autodiscovery <link> tags in <head>.

    Args:
        html: Raw HTML content of the page.
        page_url: The URL the HTML was fetched from (for URL resolution).

    Returns:
        List of DiscoveredFeed objects found via autodiscovery.
    """
    feeds: list[DiscoveredFeed] = []

    page = Selector(content=html)

    # Find <head> element
    head = page.find('head')
    if not head:
        return feeds

    # Check for <base href=""> override in <head>
    base_tag = head.find('base[href]')
    base_href: str | None = base_tag.attrib['href'] if base_tag else None

    # Find all <link> tags in <head> with rel="alternate"
    for link in head.css('link[rel="alternate"]'):
        href = link.attrib['href']
        if not href:
            continue

        link_type = link.attrib.get('type') or ''
        feed_type = extract_feed_type(link_type)
        if not feed_type:
            continue

        # Resolve URL (handles relative URLs and base href override)
        absolute_url = resolve_url(page_url, href, base_href)

        # Extract title if present
        title: Optional[str] = link.attrib.get('title')

        feeds.append(DiscoveredFeed(
            url=absolute_url,
            title=title,
            feed_type=feed_type,
            source='autodiscovery',
            page_url=page_url,
        ))

    # Trafilatura fallback: if no <link> tags found, try <a href> with regex
    if not feeds:
        page_netloc = urlparse(page_url).netloc.lower()
        for anchor in page.css('a[href]'):
            href = anchor.attrib.get('href', '')
            if not href or href.startswith(('javascript:', 'mailto:', '#')):
                continue
            # Check if URL matches feed pattern
            if LINK_VALIDATION_RE.search(href.lower()):
                absolute_url = resolve_url(page_url, href, base_href)
                # Blacklist /comments/ paths
                if BLACKLIST.search(absolute_url):
                    continue
                # Skip external domains
                if urlparse(absolute_url).netloc.lower() != page_netloc:
                    continue
                # Extract text content as potential title
                anchor_text = anchor.text
                title = anchor_text.strip() if anchor_text else None
                feeds.append(DiscoveredFeed(
                    url=absolute_url,
                    title=title,
                    feed_type='rss',  # best guess, validated later
                    source='autodiscovery_fallback',
                    page_url=page_url,
                ))

    return feeds
