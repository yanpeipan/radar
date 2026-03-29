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
from src.providers.base import Article, ContentProvider, CrawlResult, Raw
from src.discovery.models import DiscoveredFeed

if TYPE_CHECKING:
    from scrapling.engines.toolbelt.custom import Response

logger = logging.getLogger(__name__)

# Thread-safe context variable for feed title (avoids instance state race conditions)
_feed_title_var: ContextVar[str | None] = ContextVar("feed_title", default=None)

# Browser-like User-Agent header to avoid 403 bot blocks
from src.constants import BROWSER_HEADERS


def _quick_validate_feed_sync(url: str) -> tuple[bool, str | None]:
    """Quick feed validation via HEAD request only (synchronous).

    Only checks HTTP 200 + Content-Type header, skipping full feed parsing.

    Args:
        url: The feed URL to validate.

    Returns:
        Tuple of (is_valid, feed_type).
    """
    from scrapling import Fetcher
    try:
        response = Fetcher.get(url, headers=BROWSER_HEADERS)
        if response.status != 200:
            return False, None
        content_type = response.headers.get('content-type', '').lower()
        if any(ft in content_type for ft in ('rss', 'atom', 'rdf', 'xml')):
            feed_type = 'rss' if 'rss' in content_type else 'atom' if 'atom' in content_type else 'rdf'
            return True, feed_type
        return False, None
    except Exception:
        return False, None


def fetch_feed_content(
    url: str,
    etag: Optional[str] = None,
    last_modified: Optional[str] = None,
) -> tuple[Optional[bytes], Optional[str], Optional[str], int]:
    """Fetch feed content from URL with conditional request support.

    Args:
        url: The URL of the feed to fetch.
        etag: Optional ETag header for conditional fetching.
        last_modified: Optional Last-Modified header for conditional fetching.

    Returns:
        A tuple of (content, etag, last_modified, status_code).
        content is None if status is 304 (not modified).
    """
    from scrapling import Fetcher

    headers: dict[str, str] = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    # Merge browser headers with conditional headers
    request_headers = {**BROWSER_HEADERS, **headers}
    response = Fetcher.get(url, headers=request_headers)

    # Handle 304 Not Modified
    if response.status == 304:
        return None, None, None, 304

    status_code = response.status

    # Extract headers for future conditional requests
    new_etag = response.headers.get("etag")
    new_last_modified = response.headers.get("last-modified")

    return response.body, new_etag, new_last_modified, status_code


async def fetch_feed_content_async(
    url: str,
    etag: Optional[str] = None,
    last_modified: Optional[str] = None,
) -> tuple[Optional[bytes], Optional[str], Optional[str], int]:
    """Fetch feed content asynchronously with conditional request support.

    Args:
        url: The URL of the feed to fetch.
        etag: Optional ETag header for conditional fetching.
        last_modified: Optional Last-Modified header for conditional fetching.

    Returns:
        A tuple of (content, etag, last_modified, status_code).
        content is None if status is 304 (not modified).
    """
    import asyncio
    from scrapling import Fetcher

    headers: dict[str, str] = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    request_headers = {**BROWSER_HEADERS, **headers}
    response = await asyncio.to_thread(Fetcher.get, url, headers=request_headers)

    if response.status == 304:
        return None, None, None, 304

    new_etag = response.headers.get("etag")
    new_last_modified = response.headers.get("last-modified")

    return response.body, new_etag, new_last_modified, response.status


def parse_feed(
    content: bytes,
    url: str,
) -> tuple[list, bool, Optional[Exception]]:
    """Parse RSS/Atom feed content using feedparser.

    Args:
        content: Raw feed content as bytes.
        url: URL of the feed (used for logging).

    Returns:
        A tuple of (entries, bozo_flag, bozo_exception).
        bozo_flag is True if the feed is malformed (but parsing still succeeded).
        bozo_exception contains the exception if bozo_flag is True.
    """
    feed = feedparser.parse(content)

    bozo_flag = feed.bozo
    bozo_exception = None

    if bozo_flag:
        bozo_exception = feed.bozo_exception
        logger.warning(
            "Malformed feed detected for %s: %s",
            url,
            bozo_exception,
        )

    entries = []
    for entry in feed.entries:
        entries.append(entry)

    return entries, bozo_flag, bozo_exception


class RSSProvider:
    """Content provider for RSS and Atom feeds.

    Uses HTTP HEAD request to detect RSS/Atom content types,
    then fetches and parses the full feed content.
    """

    def __init__(self) -> None:
        pass

    @property
    def feed_title(self) -> str | None:
        """Return the feed title from the last crawl() call in this context, or None."""
        return _feed_title_var.get()

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

    def crawl(self, url: str) -> List[Raw]:
        """Fetch and parse RSS/Atom feed content.

        Args:
            url: URL of the feed to crawl.

        Returns:
            List of feedparser entry dicts, or empty list on error.
        """
        _feed_title_var.set(None)
        try:
            content, etag, last_modified, status_code = fetch_feed_content(url)
            if content is None:
                logger.warning("RSS feed %s returned 304 Not Modified", url)
                return []

            # Parse full feed to get feed-level metadata (title)
            parsed = feedparser.parse(content)
            if parsed.feed:
                _feed_title_var.set(parsed.feed.get("title"))

            entries, bozo_flag, bozo_exception = parse_feed(content, url)
            if bozo_flag and bozo_exception:
                logger.warning("Malformed feed at %s: %s", url, bozo_exception)

            logger.debug("RSSProvider.crawl(%s) returned %d entries", url, len(entries))
            return entries
        except Exception as e:
            # Check for 403 status for Cloudflare-protected feeds
            error_str = str(e)
            if "403" in error_str:
                # Fallback to Scrapling for Cloudflare-protected feeds
                logger.info("Got 403 for %s, trying Scrapling fallback", url)
                return self._crawl_with_scrapling(url)
            logger.error("RSSProvider.crawl(%s) failed: %s", url, e)
            return []
        except Exception as e:
            logger.error("RSSProvider.crawl(%s) failed: %s", url, e)
            return []

    async def crawl_async(self, url: str, etag: Optional[str] = None, last_modified: Optional[str] = None) -> CrawlResult:
        """Fetch and parse RSS/Atom feed content asynchronously.

        Uses asyncio.to_thread with scrapling Fetcher for HTTP, with feedparser.parse()
        and parse_feed() running in a thread pool executor to avoid blocking.

        Args:
            url: URL of the feed to crawl.
            etag: Optional ETag header for conditional fetching.
            last_modified: Optional Last-Modified header for conditional fetching.

        Returns:
            CrawlResult with entries and updated etag/last_modified.
        """
        import asyncio

        _feed_title_var.set(None)
        try:
            content, new_etag, new_last_modified, status_code = await fetch_feed_content_async(
                url, etag=etag, last_modified=last_modified
            )
            if content is None:
                logger.info("RSS feed %s returned 304 Not Modified", url)
                return CrawlResult(entries=[], etag=etag, last_modified=last_modified)

            # Parse in thread pool to avoid blocking event loop
            loop = asyncio.get_running_loop()
            parsed = await loop.run_in_executor(None, feedparser.parse, content)

            if parsed.feed:
                _feed_title_var.set(parsed.feed.get("title"))

            entries, bozo_flag, bozo_exception = await loop.run_in_executor(
                None, parse_feed, content, url
            )
            if bozo_flag and bozo_exception:
                logger.warning("Malformed feed at %s: %s", url, bozo_exception)

            logger.debug("RSSProvider.crawl_async(%s) returned %d entries", url, len(entries))
            return CrawlResult(entries=entries, etag=new_etag, last_modified=new_last_modified)
        except Exception as e:
            error_str = str(e)
            if "403" in error_str:
                logger.info("Got 403 for %s, trying Scrapling fallback", url)
                return await self._crawl_with_scrapling_async(url)
            logger.error("RSSProvider.crawl_async(%s) failed: %s", url, e)
            return CrawlResult(entries=[])

    def _crawl_with_scrapling(self, url: str) -> CrawlResult:
        """Fetch RSS feed using Scrapling to bypass Cloudflare protection.

        Args:
            url: URL of the feed to crawl.

        Returns:
            CrawlResult with entries (no etag/last_modified from Scrapling).
        """
        try:
            from scrapling import Fetcher

            response = Fetcher.get(url)

            # Scrapling returns bytes in response.body
            content = response.body
            if not content:
                logger.warning("Scrapling returned empty content for %s", url)
                return CrawlResult(entries=[])

            # Parse full feed to get feed-level metadata (title)
            parsed = feedparser.parse(content)
            if parsed.feed:
                _feed_title_var.set(parsed.feed.get("title"))

            entries, bozo_flag, bozo_exception = parse_feed(content, url)
            if bozo_flag and bozo_exception:
                logger.warning("Malformed feed at %s (Scrapling): %s", url, bozo_exception)

            logger.debug("RSSProvider._crawl_with_scrapling(%s) returned %d entries", url, len(entries))
            return CrawlResult(entries=entries)
        except ImportError:
            logger.warning("Scrapling not installed, skipping Cloudflare fallback for %s", url)
            return CrawlResult(entries=[])
        except Exception as e:
            logger.error("RSSProvider._crawl_with_scrapling(%s) failed: %s", url, e)
            return CrawlResult(entries=[])

    async def _crawl_with_scrapling_async(self, url: str) -> CrawlResult:
        """Async wrapper for Scrapling fallback using asyncio.to_thread().

        Args:
            url: URL of the feed to crawl.

        Returns:
            CrawlResult with entries.
        """
        import asyncio

        return await asyncio.to_thread(self._crawl_with_scrapling, url)

    def parse(self, raw: Raw) -> Article:
        """Convert feedparser entry to Article dict.

        Args:
            raw: Feedparser entry dict.

        Returns:
            Article dict with title, link, guid, pub_date, description, content.
        """
        from src.utils import generate_article_id

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
        content = None
        if hasattr(raw, "content") and raw.content:
            content = raw.content[0].value if raw.content else None
        elif hasattr(raw, "summary_detail") and hasattr(raw.summary_detail, "value"):
            content = raw.summary_detail.value

        return Article(
            title=title,
            link=link,
            guid=guid,
            pub_date=pub_date,
            description=description,
            content=content,
        )

    def parse_feed(self, url: str, response: "Response" = None) -> "DiscoveredFeed":
        """Validate URL is an RSS/Atom feed and return as DiscoveredFeed.

        Args:
            url: URL of the feed to validate.
            response: Pre-fetched HTTP response (may be None).

        Returns:
            DiscoveredFeed with valid=True if URL is a valid RSS/Atom feed.

        Raises:
            ValueError: If feed cannot be fetched or parsed.
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
        except Exception as e:
            raise ValueError(f"Failed to fetch feed metadata: {e}")

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
        from src.discovery.models import DiscoveredFeed
        from src.discovery.common_paths import generate_feed_candidates, matches_feed_path_pattern

        feeds: List[DiscoveredFeed] = []

        # If response is a feed type, return it as validated
        if response:
            content_type = response.headers.get('content-type', '') or ""
            if any(ft in content_type for ft in ('rss', 'atom', 'rdf', 'xml')):
                return [DiscoveredFeed(
                    url=url,
                    title=None,
                    feed_type='rss' if 'rss' in content_type else 'atom' if 'atom' in content_type else 'rdf',
                    source='RSSProvider',
                    page_url=url,
                    valid=True,
                )]

        # Parse HTML page for feed discovery
        html = None
        if response:
            try:
                # Use response.body to get HTML content (response.text may be empty for some fetchers)
                if response.body:
                    html = response.body.decode('utf-8', errors='replace') if isinstance(response.body, bytes) else str(response.body)
            except Exception:
                pass

        if not html:
            return feeds

        # Parse <link rel="alternate"> tags
        from scrapling import Selector
        page = Selector(content=html)

        # Check for <base href> override
        base_override: str | None = None
        head = page.find('head')
        if head:
            base_tag = head.find('base[href]')
            if base_tag:
                base_override = base_tag.attrib['href']

        # Find feed link tags
        for link_tag in page.css('link[rel="alternate"]'):
            href = link_tag.attrib.get('href', '')
            if not href:
                continue

            # Resolve relative URLs
            if base_override:
                absolute = urljoin(base_override, href)
            else:
                absolute = urljoin(url, href)

            # Validate it looks like a feed
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
                valid=False,  # Unverified - caller will validate
            ))

        # CSS selector-based link discovery for finding feed links on page
        # This finds <a href*="rss">, <a href*="feed">, <a href*="atom">, <a href$=".xml">
        feed_selectors = [
            'a[href*="rss"]',
            'a[href*="feed"]',
            'a[href*="atom"]',
            'a[href$=".xml"]',
        ]

        found_urls: set = set()
        for selector in feed_selectors:
            try:
                for anchor in page.css(selector):
                    href = anchor.attrib.get('href', '')
                    if not href:
                        continue

                    # Resolve relative URLs
                    if base_override:
                        absolute = urljoin(base_override, href)
                    else:
                        absolute = urljoin(url, href)

                    parsed = urlparse(absolute)

                    # Skip different hosts
                    if parsed.netloc.lower() != urlparse(url).netloc.lower():
                        continue

                    if absolute in found_urls:
                        continue
                    found_urls.add(absolute)

                    # Validate path matches feed pattern
                    path = parsed.path.lower()
                    if not matches_feed_path_pattern(path):
                        continue

                    feeds.append(DiscoveredFeed(
                        url=absolute,
                        title=None,
                        feed_type='rss',
                        source='RSSProvider',
                        page_url=url,
                        valid=False,  # Unverified - caller will validate
                    ))
            except Exception:
                # CSS selector may fail for some pages
                continue

        # Probe well-known paths in parallel and only add validated ones
        if depth == 1:
            well_known_feeds = _probe_well_known_paths(url, html)
            feeds.extend(well_known_feeds)

        return feeds


def _probe_well_known_paths(url: str, html: str | None) -> list["DiscoveredFeed"]:
    """Probe well-known feed paths on a page URL and validate them in parallel.

    Args:
        url: Base page URL to probe.
        html: Optional HTML content for subdirectory discovery.

    Returns:
        List of DiscoveredFeed found via well-known path probing (only validated ones).
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from src.discovery.common_paths import generate_feed_candidates

    candidates = generate_feed_candidates(url, html)
    if not candidates:
        return []

    results: list[DiscoveredFeed] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_candidate = {executor.submit(_quick_validate_feed_sync, c): c for c in candidates}
        for future in as_completed(future_to_candidate):
            is_valid, feed_type = future.result()
            if is_valid:
                candidate = future_to_candidate[future]
                results.append(DiscoveredFeed(
                    url=candidate,
                    title=None,
                    feed_type=feed_type or 'rss',
                    source='RSSProvider',
                    page_url=url,
                    valid=True,
                ))
    return results

# Register this provider - it will be sorted by priority() after all modules load
PROVIDERS.append(RSSProvider())
