"""RSS provider for RSS and Atom feeds.

Handles feed fetching and parsing for standard RSS/Atom feeds.
Priority is 50 (higher than DefaultProvider at 0, lower than GitHubReleaseProvider at 200).
"""
from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import List, Optional

import feedparser
import httpx

from src.providers import PROVIDERS
from src.providers.base import Article, ContentProvider, Raw, TagParser
from src.tags import chain_tag_parsers

logger = logging.getLogger(__name__)

# Thread-safe context variable for feed title (avoids instance state race conditions)
_feed_title_var: ContextVar[str | None] = ContextVar("feed_title", default=None)

# Browser-like User-Agent header to avoid 403 bot blocks
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


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
        Raises httpx.RequestError or httpx.TimeoutException on network errors.
    """
    headers: dict[str, str] = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    # Merge browser headers with conditional headers
    request_headers = {**BROWSER_HEADERS, **headers}
    response = httpx.get(url, headers=request_headers, timeout=30.0, follow_redirects=True)

    # Handle 304 Not Modified (httpx raises on 304 after redirects)
    if response.status_code == 304:
        return None, None, None, 304

    response.raise_for_status()
    status_code = response.status_code

    # Extract headers for future conditional requests
    new_etag = response.headers.get("etag")
    new_last_modified = response.headers.get("last-modified")

    return response.content, new_etag, new_last_modified, status_code


async def fetch_feed_content_async(
    client: httpx.AsyncClient,
    url: str,
    etag: Optional[str] = None,
    last_modified: Optional[str] = None,
) -> tuple[Optional[bytes], Optional[str], Optional[str], int]:
    """Fetch feed content asynchronously with conditional request support.

    Args:
        client: Active httpx.AsyncClient instance.
        url: The URL of the feed to fetch.
        etag: Optional ETag header for conditional fetching.
        last_modified: Optional Last-Modified header for conditional fetching.

    Returns:
        A tuple of (content, etag, last_modified, status_code).
        content is None if status is 304 (not modified).
        Raises httpx.HTTPStatusError on HTTP errors.
    """
    headers: dict[str, str] = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    request_headers = {**BROWSER_HEADERS, **headers}
    response = await client.get(
        url,
        headers=request_headers,
        timeout=30.0,
        follow_redirects=True
    )

    if response.status_code == 304:
        return None, None, None, 304

    response.raise_for_status()
    new_etag = response.headers.get("etag")
    new_last_modified = response.headers.get("last-modified")

    return response.content, new_etag, new_last_modified, response.status_code


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

    def match(self, url: str) -> bool:
        """Check if URL points to RSS/Atom feed via Content-Type header.

        Args:
            url: URL to check.

        Returns:
            True if URL returns application/rss+xml, application/atom+xml,
            or application/xml Content-Type. Also returns True for 403 errors
            to allow fallback to Scrapling for Cloudflare-protected feeds.
        """
        import httpx

        try:
            response = httpx.head(url, timeout=10.0, follow_redirects=True)
            # Check for 403 - Cloudflare may block HEAD but allow GET with Scrapling
            if response.status_code == 403:
                logger.debug("RSSProvider.match(%s) got 403 on HEAD, allowing match for crawl fallback", url)
                return True
            content_type = response.headers.get("content-type", "").lower()
            # Check for RSS/Atom content types
            if "application/rss" in content_type:
                return True
            if "application/atom" in content_type:
                return True
            # Also accept generic XML types for feeds
            if "application/xml" in content_type or "text/xml" in content_type:
                return True
            return False
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                # 403 on HEAD doesn't mean it's not a feed (Cloudflare may block HEAD but allow GET)
                # Return True to allow crawl() to try with Scrapling fallback
                logger.debug("RSSProvider.match(%s) got 403 on HEAD, allowing match for crawl fallback", url)
                return True
            logger.debug("RSSProvider.match(%s) failed with HTTP error: %s", url, e)
            return False
        except Exception as e:
            logger.debug("RSSProvider.match(%s) failed: %s", url, e)
            return False

    def priority(self) -> int:
        """Return provider priority.

        Returns:
            50 - higher than DefaultProvider (0), lower than GitHubReleaseProvider (200).
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
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                # Fallback to Scrapling for Cloudflare-protected feeds
                logger.info("httpx returned 403 for %s, trying Scrapling fallback", url)
                return self._crawl_with_scrapling(url)
            logger.error("RSSProvider.crawl(%s) HTTP error: %s", url, e)
            return []
        except Exception as e:
            logger.error("RSSProvider.crawl(%s) failed: %s", url, e)
            return []

    async def crawl_async(self, url: str) -> List[Raw]:
        """Fetch and parse RSS/Atom feed content asynchronously.

        Uses httpx.AsyncClient for true async HTTP, with feedparser.parse()
        and parse_feed() running in a thread pool executor to avoid blocking.

        Args:
            url: URL of the feed to crawl.

        Returns:
            List of feedparser entry dicts, or empty list on error.
        """
        import asyncio

        _feed_title_var.set(None)
        try:
            async with httpx.AsyncClient() as client:
                content, etag, last_modified, status_code = await fetch_feed_content_async(
                    client, url
                )
                if content is None:
                    logger.warning("RSS feed %s returned 304 Not Modified", url)
                    return []

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
                return entries
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                logger.info("httpx returned 403 for %s, trying Scrapling fallback", url)
                return await self._crawl_with_scrapling_async(url)
            logger.error("RSSProvider.crawl_async(%s) HTTP error: %s", url, e)
            return []
        except Exception as e:
            logger.error("RSSProvider.crawl_async(%s) failed: %s", url, e)
            return []

    def _crawl_with_scrapling(self, url: str) -> List[Raw]:
        """Fetch RSS feed using Scrapling to bypass Cloudflare protection.

        Args:
            url: URL of the feed to crawl.

        Returns:
            List of feedparser entry dicts, or empty list on error.
        """
        try:
            from scrapling import Fetcher

            response = Fetcher.get(url)

            # Scrapling returns bytes in response.body
            content = response.body
            if not content:
                logger.warning("Scrapling returned empty content for %s", url)
                return []

            # Parse full feed to get feed-level metadata (title)
            parsed = feedparser.parse(content)
            if parsed.feed:
                _feed_title_var.set(parsed.feed.get("title"))

            entries, bozo_flag, bozo_exception = parse_feed(content, url)
            if bozo_flag and bozo_exception:
                logger.warning("Malformed feed at %s (Scrapling): %s", url, bozo_exception)

            logger.debug("RSSProvider._crawl_with_scrapling(%s) returned %d entries", url, len(entries))
            return entries
        except ImportError:
            logger.warning("Scrapling not installed, skipping Cloudflare fallback for %s", url)
            return []
        except Exception as e:
            logger.error("RSSProvider._crawl_with_scrapling(%s) failed: %s", url, e)
            return []

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

    def tag_parsers(self) -> List[TagParser]:
        """Return tag parsers for this provider.

        Returns:
            Empty list - tag parsers are loaded separately in Plan 02.
        """
        return []

    def feed_meta(self, url: str) -> "Feed":
        """Fetch feed metadata via lightweight GET request.

        Args:
            url: URL of the feed to get metadata for.

        Returns:
            Feed object with name populated from feed title.

        Raises:
            ValueError: If feed cannot be fetched or parsed.
        """
        from src.models import Feed
        from src.application.config import get_timezone
        from datetime import datetime

        try:
            # Lightweight fetch with short timeout - just need title
            response = httpx.get(
                url,
                headers=BROWSER_HEADERS,
                timeout=5.0,
                follow_redirects=True
            )
            response.raise_for_status()

            # Parse just enough to get feed title
            parsed = feedparser.parse(response.content)
            title = parsed.feed.get("title") if parsed.feed else url

            # Get headers for future conditional requests
            etag = response.headers.get("etag")
            last_modified = response.headers.get("last-modified")

            now = datetime.now(get_timezone()).isoformat()

            return Feed(
                id="",
                name=title,
                url=url,
                etag=etag,
                last_modified=last_modified,
                last_fetched=now,
                created_at=now,
            )
        except Exception as e:
            raise ValueError(f"Failed to fetch feed metadata: {e}")

    def parse_tags(self, article: Article) -> List[str]:
        """Parse tags for an article using all loaded tag parsers.

        Args:
            article: Article dict with title, description, etc.

        Returns:
            List of tag names from all tag parsers (union, deduped).
        """
        return chain_tag_parsers(article)


# Register this provider - it will be sorted by priority() after all modules load
PROVIDERS.append(RSSProvider())
