"""RSS provider for RSS and Atom feeds.

Handles feed fetching and parsing for standard RSS/Atom feeds.
Priority is 50 (higher than DefaultRSSProvider at 0, lower than GitHubProvider at 100).
"""
from __future__ import annotations

import logging
from typing import List

from src.providers import PROVIDERS
from src.providers.base import Article, ContentProvider, Raw, TagParser

logger = logging.getLogger(__name__)


class RSSProvider:
    """Content provider for RSS and Atom feeds.

    Uses HTTP HEAD request to detect RSS/Atom content types,
    then fetches and parses the full feed content.
    """

    def match(self, url: str) -> bool:
        """Check if URL points to RSS/Atom feed via Content-Type header.

        Args:
            url: URL to check.

        Returns:
            True if URL returns application/rss+xml, application/atom+xml,
            or application/xml Content-Type.
        """
        import httpx

        try:
            response = httpx.head(url, timeout=10.0, follow_redirects=True)
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
        except Exception as e:
            logger.debug("RSSProvider.match(%s) failed: %s", url, e)
            return False

    def priority(self) -> int:
        """Return provider priority.

        Returns:
            50 - higher than DefaultRSSProvider (0), lower than GitHubProvider (100).
        """
        return 50

    def crawl(self, url: str) -> List[Raw]:
        """Fetch and parse RSS/Atom feed content.

        Args:
            url: URL of the feed to crawl.

        Returns:
            List of feedparser entry dicts, or empty list on error.
        """
        from src.feeds import fetch_feed_content, parse_feed

        try:
            content, etag, last_modified, status_code = fetch_feed_content(url)
            if content is None:
                logger.warning("RSS feed %s returned 304 Not Modified", url)
                return []

            entries, bozo_flag, bozo_exception = parse_feed(content, url)
            if bozo_flag and bozo_exception:
                logger.warning("Malformed feed at %s: %s", url, bozo_exception)

            logger.debug("RSSProvider.crawl(%s) returned %d entries", url, len(entries))
            return entries
        except Exception as e:
            logger.error("RSSProvider.crawl(%s) failed: %s", url, e)
            return []

    def parse(self, raw: Raw) -> Article:
        """Convert feedparser entry to Article dict.

        Args:
            raw: Feedparser entry dict.

        Returns:
            Article dict with title, link, guid, pub_date, description, content.
        """
        from src.feeds import generate_article_id

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

    def parse_tags(self, article: Article) -> List[str]:
        """Parse tags for an article.

        Args:
            article: Article dict.

        Returns:
            Empty list - chaining is implemented in Plan 02 via chain_tag_parsers.
        """
        return []


# Register this provider - it will be sorted by priority() after all modules load
PROVIDERS.append(RSSProvider())
