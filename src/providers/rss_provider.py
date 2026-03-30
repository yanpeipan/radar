"""RSS provider for RSS and Atom feeds.

Handles feed fetching and parsing for standard RSS/Atom feeds.
Priority is 50 (higher than DefaultProvider at 0, lower than GitHubReleaseProvider at 200).
"""
from __future__ import annotations

import asyncio
import logging
from contextvars import ContextVar
from typing import Any, List, Optional, TYPE_CHECKING
from urllib.parse import urljoin, urlparse

import xml.etree.ElementTree as ET

import feedparser
from trafilatura import fetch_url

from src.providers import PROVIDERS
from src.providers.base import Article, ContentProvider, FetchedResult, Raw
from src.discovery.models import DiscoveredFeed

if TYPE_CHECKING:
    from scrapling.engines.toolbelt.custom import Response

logger = logging.getLogger(__name__)

# Browser-like User-Agent header to avoid 403 bot blocks
from src.constants import BROWSER_HEADERS


class RSSProvider:
    """Content provider for RSS and Atom feeds.

    Uses HTTP HEAD request to detect RSS/Atom content types,
    then fetches and parses the full feed content.
    """

    def __init__(self) -> None:
        pass

    def _fetch_feed_content_sync(
        self,
        url: str,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
    ) -> "Response":
        """Fetch feed content synchronously with conditional request support.

        Args:
            url: The URL of the feed to fetch.
            etag: Optional ETag header for conditional fetching.
            last_modified: Optional Last-Modified header for conditional fetching.

        Returns:
            Response object. Caller should check response.status == 304 for not modified.
        """
        from scrapling import Fetcher

        headers: dict[str, str] = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        # Merge browser headers with conditional headers
        request_headers = {**BROWSER_HEADERS, **headers}
        # Use increased retries (5) and retry delay (2s) to handle intermittent TLS errors
        # that can occur with certain hosts through HTTP proxies
        response = Fetcher.get(
            url,
            headers=request_headers,
            retries=5,
            retry_delay=2,
            timeout=30,
        )
        return response

    def match(self, url: str, response: "Response" = None) -> bool:
        """Check if URL points to RSS/Atom feed via Content-Type header.

        Args:
            url: URL to check.
            response: Optional HTTP response from discovery phase.
                If provided, uses content_type from response directly (no new request).
                If None, only uses URL pattern matching (no new request).

        Returns:
            True if URL returns application/rss+xml, application/atom+xml,
            or application/xml Content-Type. Also returns True for 403 errors
            to allow fallback to Scrapling for Cloudflare-protected feeds.
        """
        if response:
            # 403 triggers Cloudflare fallback - allow crawl
            if response.status == 403:
                return True
            # Use response content-type directly (discovery already fetched)
            content_type = response.headers.get('content-type', '') or ""
            if "application/rss" in content_type or "application/atom" in content_type:
                return True
            if "application/xml" in content_type or "text/xml" in content_type:
                return True
            # Also match HTML pages to enable feed discovery on webpages
            # This allows RSSProvider to discover feeds on pages like openai.com
            if "text/html" in content_type:
                return True
            return False

        # When response is None, match HTTP URLs to allow feed discovery on any page
        # This enables RSSProvider to discover feeds on webpages like openai.com
        if url.startswith("http"):
            return True
        return False

    def priority(self) -> int:
        """Return provider priority.

        Returns:
            200 - higher than WebpageProvider (100), lower than GitHubReleaseProvider (300).
            RSS/Atom feeds should be handled by this provider before falling through
            to the generic WebpageProvider.
        """
        return 50

    def fetch_articles(self, feed: Feed) -> FetchedResult:
        """Fetch and parse RSS/Atom feed content.

        Args:
            feed: Feed object containing url and optional etag/last_modified.

        Returns:
            FetchedResult with articles and updated etag/last_modified.
        """
        try:
            response = self._fetch_feed_content_sync(feed.url, feed.etag, feed.last_modified)
            if response.status == 304:
                logger.info("RSS feed %s returned 304 Not Modified", feed.url)
                return FetchedResult(articles=[], etag=feed.etag, last_modified=feed.last_modified)

            articles = self.parse_articles(response)
            logger.debug("RSSProvider.fetch_articles(%s) returned %d entries", feed.url, len(articles))
            return FetchedResult(
                articles=articles,
                etag=response.headers.get("etag"),
                last_modified=response.headers.get("last-modified"),
            )
        except Exception as e:
            logger.error("RSSProvider.fetch_articles(%s) failed: %s", feed.url, e)
            return FetchedResult(articles=[])

    def parse_articles(self, response: "Response") -> List[Article]:
        """Parse RSS/Atom feed content and convert to Article dicts.

        Args:
            response: Response object from _fetch_feed_content_sync.

        Returns:
            List of Article dicts.
        """
        from src.utils import generate_article_id

        content = response.body
        feed = feedparser.parse(content)

        # Log bozo (malformed feed) warnings
        if feed.bozo:
            logger.warning("Malformed feed detected: %s", feed.bozo_exception)

        articles = []
        for raw in feed.entries:
            # Extract title
            title = raw.get("title")

            # Extract link
            link = raw.get("link")

            # Generate article ID (guid)
            guid = generate_article_id(raw)

            # Extract pub_date (published or updated)
            pub_date = raw.get("published") or raw.get("updated")

            # Extract description
            description = None
            if hasattr(raw, "description"):
                description = raw.description
            elif hasattr(raw, "summary"):
                description = raw.summary

            # Extract content
            content_val = None
            if hasattr(raw, "content") and raw.content:
                content_val = raw.content[0].value if raw.content else None
            elif hasattr(raw, "summary_detail") and hasattr(raw.summary_detail, "value"):
                content_val = raw.summary_detail.value

            articles.append(Article(
                title=title,
                link=link,
                guid=guid,
                pub_date=pub_date,
                description=description,
                content=content_val,
            ))
        return articles

    def parse_feed(self, url: str, response: "Response" = None) -> "DiscoveredFeed":
        """Validate URL is an RSS/Atom feed and return as DiscoveredFeed.

        Args:
            url: URL of the feed to validate.
            response: Pre-fetched HTTP response (may be None).

        Returns:
            DiscoveredFeed with valid=True if URL is a valid RSS/Atom feed,
            valid=False if validation fails.
        """
        from scrapling import Fetcher

        try:
            # Use pre-fetched response if available
            if response is None:
                response = Fetcher.get(url, headers=BROWSER_HEADERS)

            # Parse just enough to get feed title
            parsed = feedparser.parse(response.body)
            title = parsed.feed.get("title") if parsed.feed else None

            return DiscoveredFeed(
                url=url,
                title=title,
                feed_type="rss",
                source=f"provider_{self.__class__.__name__}",
                page_url=url,
                valid=True,
            )
        except Exception:
            return DiscoveredFeed(
                url=url,
                title=None,
                feed_type="rss",
                source=f"provider_{self.__class__.__name__}",
                page_url=url,
                valid=False,
            )

    def discover(self, url: str, response: "Response" = None, depth: int = 1) -> List["DiscoveredFeed"]:
        """Discover feed URLs from a page.

        Args:
            url: Current page URL.
            response: Pre-fetched HTTP response (may be None).
            depth: Current crawl depth (1 = initial URL, can make HTTP requests;
                   >1 = BFS deeper, should use response only if available).

        Returns:
            List of discovered DiscoveredFeed (unverified, validation happens in caller).
        """
        feeds: List["DiscoveredFeed"] = []

        # Phase 1: If response is a feed type, return it as validated
        feed_result = self._check_feed_content_type(url, response)
        if feed_result is not None:
            return [feed_result]

        # Phase 2: Parse HTML page
        from src.utils.scraping_utils import parse_html_body, find_base_href
        html = parse_html_body(response)
        if not html:
            return feeds

        # Phase 3: Find <link rel="alternate"> tags
        from scrapling import Selector
        page = Selector(content=html)
        base_override = find_base_href(page)
        feeds.extend(self._find_link_alternate_tags(page, url, base_override))

        # Phase 4: CSS selector-based link discovery
        feeds.extend(self._find_css_selector_links(page, url, base_override))

        # Phase 5: Probe well-known paths (only at depth 1)
        if depth == 1:
            feeds.extend(_probe_well_known_paths(url, html))

        return feeds

    def _check_feed_content_type(self, url: str, response: "Response" = None) -> "DiscoveredFeed | None":
        """Check if response Content-Type indicates a feed.

        Args:
            url: Page URL.
            response: HTTP response.

        Returns:
            DiscoveredFeed if Content-Type is feed type, None otherwise.
        """
        if not response:
            return None

        from src.discovery.models import DiscoveredFeed
        content_type = response.headers.get('content-type', '') or ""
        if any(ft in content_type for ft in ('rss', 'atom', 'rdf', 'xml')):
            feed_type = 'rss' if 'rss' in content_type else 'atom' if 'atom' in content_type else 'rdf'
            return DiscoveredFeed(
                url=url,
                title=None,
                feed_type=feed_type,
                source='RSSProvider',
                page_url=url,
                valid=True,
            )
        return None

    def _find_link_alternate_tags(self, page: "Selector", url: str, base_override: str | None = None) -> list["DiscoveredFeed"]:
        """Find <link rel="alternate"> tags pointing to feeds.

        Args:
            page: Parsed HTML page.
            url: Page URL for resolving relative URLs.
            base_override: Optional base href override.

        Returns:
            List of discovered feeds from link tags.
        """
        from src.discovery.models import DiscoveredFeed
        from src.discovery.common_paths import matches_feed_path_pattern

        feeds: List["DiscoveredFeed"] = []
        for link_tag in page.css('link[rel="alternate"]'):
            href = link_tag.attrib.get('href', '')
            if not href:
                continue

            absolute = urljoin(base_override, href) if base_override else urljoin(url, href)
            parsed = urlparse(absolute)
            path = parsed.path.lower()
            if not matches_feed_path_pattern(path):
                continue

            feeds.append(DiscoveredFeed(
                url=absolute,
                title=link_tag.attrib.get('title'),
                feed_type='rss',
                source='RSSProvider',
                page_url=url,
                valid=False,
            ))
        return feeds

    def _find_css_selector_links(self, page: "Selector", url: str, base_override: str | None = None) -> list["DiscoveredFeed"]:
        """Find feed links via CSS selectors (a[href*="rss"], a[href*="feed"], etc).

        Args:
            page: Parsed HTML page.
            url: Page URL for resolving relative URLs and host comparison.
            base_override: Optional base href override.

        Returns:
            List of discovered feeds from CSS selector links.
        """
        from src.discovery.models import DiscoveredFeed
        from src.discovery.common_paths import matches_feed_path_pattern

        feed_selectors = [
            'a[href*="rss"]',
            'a[href*="feed"]',
            'a[href*="atom"]',
            'a[href$=".xml"]',
        ]

        feeds: List["DiscoveredFeed"] = []
        found_urls: set = set()
        page_host = urlparse(url).netloc.lower()

        for selector in feed_selectors:
            try:
                for anchor in page.css(selector):
                    href = anchor.attrib.get('href', '')
                    if not href:
                        continue

                    absolute = urljoin(base_override, href) if base_override else urljoin(url, href)
                    parsed = urlparse(absolute)

                    # Skip different hosts
                    if parsed.netloc.lower() != page_host:
                        continue
                    if absolute in found_urls:
                        continue
                    found_urls.add(absolute)

                    path = parsed.path.lower()
                    if not matches_feed_path_pattern(path):
                        continue

                    feeds.append(DiscoveredFeed(
                        url=absolute,
                        title=None,
                        feed_type='rss',
                        source='RSSProvider',
                        page_url=url,
                        valid=False,
                    ))
            except Exception:
                continue
        return feeds


def _probe_well_known_paths(url: str, html: str | None) -> list["DiscoveredFeed"]:
    """Probe well-known feed paths on a page URL and validate them in parallel.

    Args:
        url: Base page URL to probe.
        html: Optional HTML content for subdirectory discovery.

    Returns:
        List of DiscoveredFeed found via well-known path probing (only validated ones).
    """
    import asyncio
    from src.discovery.common_paths import generate_feed_candidates

    candidates = generate_feed_candidates(url, html)
    if not candidates:
        return []

    async def _validate_one(candidate: str) -> DiscoveredFeed | None:
        try:
            return await asyncio.to_thread(RSSProvider().parse_feed, candidate, None)
        except Exception:
            return None

    async def _validate_all() -> list[DiscoveredFeed]:
        results = await asyncio.gather(*[_validate_one(c) for c in candidates])
        return [r for r in results if r is not None]

    return asyncio.run(_validate_all())

# Register this provider - it will be sorted by priority() after all modules load
PROVIDERS.append(RSSProvider())
