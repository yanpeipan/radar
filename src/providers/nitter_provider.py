"""Nitter RSS provider for Twitter/X via Nitter instances.

Handles nitter:username pseudo-URLs for fetching tweets via Nitter RSS feeds.
No Twitter API authentication required.

Usage:
    feedship feed add nitter:elonmusk
    feedship feed add nitter:barackobama
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import feedparser

from src.application.config import _get_settings
from src.discovery.models import DiscoveredFeed
from src.providers import PROVIDERS
from src.providers.base import Article, FetchedResult

if TYPE_CHECKING:
    from scrapling.engines.toolbelt.custom import Response

    from src.models import Feed, FeedType

logger = logging.getLogger(__name__)

# Browser-like User-Agent header to avoid 403 bot blocks
from src.constants import BROWSER_HEADERS  # noqa: E402


class NitterProvider:
    """Content provider for Twitter/X tweets via Nitter RSS.

    Detects nitter:username URLs and fetches tweets using Nitter instances
    with automatic fallback when the default instance fails.
    """

    def match(
        self, url: str, response: Response = None, feed_type: FeedType = None
    ) -> bool:
        """Check if URL is a Nitter pseudo-URL.

        Args:
            url: URL to check (e.g., 'nitter:elonmusk').
            response: Optional HTTP response (ignored - URL-only matching).
            feed_type: Optional FeedType to restrict matching.

        Returns:
            True if URL starts with 'nitter:'.
        """
        from src.models import FeedType

        # If feed_type is specified and is not RSS or NITTER, reject
        if feed_type is not None and feed_type not in (FeedType.RSS, FeedType.NITTER):
            return False

        # Match nitter: pseudo-URLs and https://x.com/ twitter.com URLs
        if url.startswith(("nitter:", "twitter:", "x:")):
            return True

        # Also match https://x.com/username and https://twitter.com/username
        import re

        return bool(
            re.match(r"https://(?:x|twitter)\.com/([^/?]+)/?", url, re.IGNORECASE)
        )

    def priority(self) -> int:
        """Return provider priority.

        Returns:
            150 - lower than RSSProvider (200), so RSS tries first.
        """
        return 150

    def fetch_articles(self, feed: Feed) -> FetchedResult:
        """Fetch tweets from Nitter RSS feed.

        Args:
            feed: Feed object containing url with username.

        Returns:
            FetchedResult with articles list.
        """
        username = self._extract_username(feed.url)
        if not username:
            logger.error("NitterProvider: No username found in URL %s", feed.url)
            return FetchedResult(articles=[])

        # Try fetching from instances with fallback
        rss_url, instance_used = self._get_rss_url_with_fallback(username)
        if not rss_url:
            logger.error(
                "NitterProvider: All Nitter instances failed for username %s", username
            )
            return FetchedResult(articles=[])

        try:
            articles = self._fetch_and_parse(rss_url, username, instance_used)
            logger.debug(
                "NitterProvider.fetch_articles(%s) returned %d articles",
                feed.url,
                len(articles),
            )
            return FetchedResult(articles=articles)
        except Exception as e:
            logger.error("NitterProvider.fetch_articles(%s) failed: %s", feed.url, e)
            return FetchedResult(articles=[])

    def _extract_username(self, url: str) -> str | None:
        """Extract username from nitter:/twitter:/x: URL or https://x.com/ URL.

        Args:
            url: URL like 'nitter:elonmusk', 'twitter:@elonmusk', 'x:elonmusk',
                 or 'https://x.com/elonmusk'

        Returns:
            Extracted username without @ prefix, or None if invalid.
        """
        # Handle nitter:/twitter:/x: pseudo-URLs
        for prefix in ("nitter:", "twitter:", "x:"):
            if url.startswith(prefix):
                username = url[len(prefix) :].strip()
                if username.startswith("@"):
                    username = username[1:]
                return username if username else None

        # Handle https://x.com/username and https://twitter.com/username
        import re

        match = re.match(r"https://(?:x|twitter)\.com/([^/?]+)/?", url, re.IGNORECASE)
        if match:
            username = match.group(1)
            if username.startswith("@"):
                username = username[1:]
            return username if username else None

        return None

    def _get_rss_url_with_fallback(
        self, username: str
    ) -> tuple[str | None, str | None]:
        """Build RSS URL with instance fallback.

        Args:
            username: Twitter username (without @).

        Returns:
            Tuple of (RSS URL, instance URL used) or (None, None) if all failed.
        """
        settings = _get_settings()
        default_instance = settings.get("nitter.default_instance")
        instances = settings.get("nitter.instances", [])

        # Build ordered list: default first, then others (skip duplicates)
        tried_instances = []
        if default_instance:
            tried_instances.append(default_instance)
        for instance in instances:
            if instance not in tried_instances:
                tried_instances.append(instance)

        for instance in tried_instances:
            rss_url = f"{instance}/{username}/rss"
            logger.debug(
                "NitterProvider: Trying instance %s for username %s", instance, username
            )
            # Verify the RSS URL is accessible
            from src.utils.scraping_utils import fetch_with_fallback

            try:
                response = fetch_with_fallback(
                    rss_url, headers=BROWSER_HEADERS, timeout=30
                )
                if response and response.status == 200:
                    logger.info(
                        "NitterProvider: Successfully fetched from %s", instance
                    )
                    return rss_url, instance
            except Exception as e:
                logger.warning("NitterProvider: Instance %s failed: %s", instance, e)
                continue

        return None, None

    def _fetch_and_parse(
        self, rss_url: str, username: str, instance: str
    ) -> list[Article]:
        """Fetch and parse Nitter RSS feed.

        Args:
            rss_url: Full RSS feed URL.
            username: Twitter username for author field.
            instance: Nitter instance URL used.

        Returns:
            List of Article dicts.
        """
        from src.utils.scraping_utils import fetch_with_fallback

        response = fetch_with_fallback(rss_url, headers=BROWSER_HEADERS, timeout=30)
        if not response or response.status != 200:
            return []

        content = response.body
        feed = feedparser.parse(content)

        # Log bozo (malformed feed) warnings
        if feed.bozo:
            feed_url = getattr(feed.feed, "href", None) or getattr(
                feed, "url", "unknown"
            )
            logger.warning(
                "NitterProvider: Malformed feed detected: %s (feed: %s)",
                feed.bozo_exception,
                feed_url,
            )

        articles = []
        for raw in feed.entries:
            # Extract title (tweet text, truncated to 200 chars)
            title = raw.get("title") or ""
            if len(title) > 200:
                title = title[:200] + "..."

            # Extract link (original Twitter URL)
            # Nitter entries have link pointing to the nitter instance, not twitter.com
            # We need to extract the actual Twitter URL from entry.id or transform the link
            link = raw.get("link") or ""

            # Transform nitter instance URL to twitter.com URL if needed
            if "nitter.net" in link or "nitter.privacydev.net" in link:
                # Extract the status path and convert to twitter.com
                # e.g., https://nitter.privacydev.net/elonmusk/status/1234567890
                #     -> https://twitter.com/elonmusk/status/1234567890
                link = self._nitter_url_to_twitter(link)

            # Extract guid (twitter status URL for deduplication)
            # Try entry.id first which is usually the twitter.com status URL
            guid = raw.get("id") or link
            # If guid is still a nitter URL, transform it
            if "nitter" in guid:
                guid = self._nitter_url_to_twitter(guid)

            # Extract published_at using struct_time
            published_at = None
            if hasattr(raw, "published_parsed") and isinstance(
                raw.published_parsed, tuple
            ):
                published_at = time.strftime("%Y-%m-%d %H:%M:%S", raw.published_parsed)
            elif hasattr(raw, "updated_parsed") and isinstance(
                raw.updated_parsed, tuple
            ):
                published_at = time.strftime("%Y-%m-%d %H:%M:%S", raw.updated_parsed)
            else:
                published_at = raw.get("published") or raw.get("updated")

            # Extract description (same as title for tweets)
            description = raw.get("description") or title

            # Extract author
            author = f"@{username}"

            articles.append(
                Article(
                    title=title,
                    link=link,
                    guid=guid,
                    published_at=published_at,
                    description=description,
                    content=None,  # Tweets don't have separate content
                    author=author,
                    tags="",
                    category="",
                )
            )

        return articles

    def _nitter_url_to_twitter(self, nitter_url: str) -> str:
        """Convert a Nitter instance URL to twitter.com URL.

        Args:
            nitter_url: URL from Nitter instance.

        Returns:
            Equivalent twitter.com URL.
        """
        # Replace nitter instance domain with twitter.com
        import re

        # Pattern: https://nitter.instance/username/status/1234567890
        # Transform to: https://twitter.com/username/status/1234567890
        pattern = r"https?://[^/]+/([^/]+)/status/(\d+)"
        match = re.match(pattern, nitter_url)
        if match:
            username, status_id = match.groups()
            return f"https://twitter.com/{username}/status/{status_id}"

        # Fallback: just replace the domain
        if "nitter.privacydev.net" in nitter_url:
            return nitter_url.replace("nitter.privacydev.net", "twitter.com")
        elif "nitter.net" in nitter_url:
            return nitter_url.replace("nitter.net", "twitter.com")

        return nitter_url

    def parse_feed(self, url: str, response: Response = None) -> DiscoveredFeed:
        """Validate nitter: URL and return as DiscoveredFeed.

        Args:
            url: Nitter pseudo-URL (e.g., 'nitter:elonmusk', 'x:elonmusk').
            response: Unused for Nitter (URL-only validation).

        Returns:
            DiscoveredFeed with valid=True if URL has a valid username.
        """
        # Check if URL looks like a twitter.com URL and suggest nitter: alternative
        if self._looks_like_twitter_url(url):
            # Return invalid feed with helpful message in title
            return DiscoveredFeed(
                url=url,
                title=f"Use 'x:{self._extract_twitter_username(url)}' instead of '{url}'",
                feed_type="rss",
                source=f"provider_{self.__class__.__name__}",
                page_url=url,
                valid=False,
            )

        username = self._extract_username(url)
        if not username:
            return DiscoveredFeed(
                url=url,
                title=None,
                feed_type="rss",
                source=f"provider_{self.__class__.__name__}",
                page_url=url,
                valid=False,
            )

        # Normalize to x: format for storage
        normalized_url = f"x:{username}"

        return DiscoveredFeed(
            url=normalized_url,
            title=f"Nitter: {username}",
            feed_type="rss",
            source=f"provider_{self.__class__.__name__}",
            page_url=url,
            valid=True,
        )

    def _looks_like_twitter_url(self, url: str) -> bool:
        """Check if URL looks like a twitter.com URL.

        Args:
            url: URL to check.

        Returns:
            True if URL appears to be a twitter.com URL.
        """
        return "twitter.com" in url.lower() or "x.com" in url.lower()

    def _extract_twitter_username(self, url: str) -> str | None:
        """Extract username from twitter.com URL.

        Args:
            url: twitter.com URL (e.g., 'https://twitter.com/elonmusk').

        Returns:
            Username without @ prefix, or None if not found.
        """
        import re

        # Pattern: twitter.com/username or x.com/username
        pattern = r"(?:twitter|x)\.com/([^/?]+)"
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            username = match.group(1)
            # Remove @ prefix if present
            if username.startswith("@"):
                username = username[1:]
            return username
        return None

    def discover(
        self, url: str, response: Response = None, depth: int = 1
    ) -> list[DiscoveredFeed]:
        """Discover feed URLs - Nitter doesn't need page discovery.

        Args:
            url: Current page URL (unused).
            response: Pre-fetched HTTP response (unused).
            depth: Current crawl depth (unused).

        Returns:
            Empty list - nitter: URLs are directly parsed.
        """
        return []


# Register this provider - priority 150 (lower than RSSProvider at 200)
PROVIDERS.append(NitterProvider())
