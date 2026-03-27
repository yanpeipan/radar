"""HTML link element parser for feed autodiscovery (DISC-01, DISC-03)."""
from __future__ import annotations

from typing import Optional
from urllib.parse import urljoin

from scrapling import Selector

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


def extract_feed_type(content_type: str) -> str | None:
    """Extract feed type from Content-Type string.

    Args:
        content_type: Content-Type header value.

    Returns:
        'rss', 'atom', 'rdf' or None if not a feed type.
    """
    ct_lower = content_type.lower()
    if 'rss' in ct_lower:
        return 'rss'
    if 'atom' in ct_lower:
        return 'atom'
    if 'rdf' in ct_lower:
        return 'rdf'
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
    base_href: str | None = base_tag.attrib.get('href') if base_tag else None

    # Find all <link> tags in <head> with rel="alternate"
    for link in head.css('link[rel="alternate"]'):
        href = link.attrib.get('href')
        if not href:
            continue

        link_type = link.attrib.get('type', '')
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

    return feeds
