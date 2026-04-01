"""Tavily real-time search provider.

Handles search:keyword and tavily:keyword pseudo-URLs for real-time web search
via Tavily AI. Priority is 400 (highest) since search queries should be
evaluated first.

Usage:
    feedship feed add search:AI news
    feedship feed add tavily:machine learning
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.application.config import _get_settings
from src.discovery.models import DiscoveredFeed
from src.providers import PROVIDERS
from src.providers.base import Article, FetchedResult

if TYPE_CHECKING:
    from scrapling.engines.toolbelt.custom import Response

    from src.models import Feed, FeedType

import tavily  # noqa: E402

logger = logging.getLogger(__name__)


class TavilyProvider:
    """Content provider for Tavily real-time search.

    Detects search:keyword or tavily:keyword URLs and fetches results
    using the Tavily AI search API.
    """

    def match(
        self, url: str, response: Response = None, feed_type: FeedType = None
    ) -> bool:
        """Check if URL is a Tavily search URL.

        Args:
            url: URL to check (e.g., 'search:AI' or 'tavily:news').
            response: Optional HTTP response (ignored - URL-only matching).
            feed_type: Optional FeedType to restrict matching.

        Returns:
            True if URL starts with 'search:' or 'tavily:'.
        """
        from src.models import FeedType

        # If feed_type is specified and is not TAVILY, reject
        if feed_type is not None and feed_type != FeedType.TAVILY:
            return False

        # URL-only matching for performance
        return url.startswith("search:") or url.startswith("tavily:")

    def priority(self) -> int:
        """Return provider priority.

        Returns:
            400 - highest priority. Search queries must be handled first.
        """
        return 400

    def fetch_articles(self, feed: Feed) -> FetchedResult:
        """Fetch search results from Tavily API.

        Args:
            feed: Feed object containing url with search keyword.

        Returns:
            FetchedResult with articles list.
        """
        # Extract keyword from URL first (no import needed)
        keyword = self._extract_keyword(feed.url)
        if not keyword:
            logger.error("TavilyProvider: No keyword found in URL %s", feed.url)
            return FetchedResult(articles=[])

        # Get configuration
        settings = _get_settings()
        api_key = settings.get("tavily.api_key")
        if not api_key:
            logger.error(
                "TavilyProvider: No API key configured. "
                "Set TAVILY_API_KEY environment variable or tavily.api_key in config.yaml"
            )
            return FetchedResult(articles=[])

        search_depth = settings.get("tavily.default_search_depth", "advanced")
        max_results = settings.get("tavily.default_max_results", 10)

        try:
            # Call sync function directly - caller wraps with asyncio.to_thread()
            articles = self._sync_search(api_key, keyword, search_depth, max_results)
            return FetchedResult(articles=articles)
        except Exception as e:
            logger.error("TavilyProvider.fetch_articles(%s) failed: %s", feed.url, e)
            return FetchedResult(articles=[])

    def _sync_search(
        self, api_key: str, keyword: str, search_depth: str, max_results: int
    ) -> list[Article]:
        """Synchronous search using Tavily SDK (runs in thread pool).

        Args:
            api_key: Tavily API key.
            keyword: Search keyword.
            search_depth: 'basic' or 'advanced'.
            max_results: Maximum number of results (1-20).

        Returns:
            List of Article dicts.
        """
        client = tavily.TavilyClient(api_key=api_key)
        response = client.search(
            query=keyword,
            search_depth=search_depth,
            max_results=max_results,
        )

        articles = []
        for result in response.get("results", []):
            article = Article(
                title=result.get("title"),
                link=result.get("url"),
                guid=result.get("url"),  # Use URL as unique identifier
                published_at=None,  # Search results don't have published dates
                description=result.get("description"),
                content=result.get("content"),
                tags=",".join(result.get("categories", []))
                if result.get("categories")
                else "",
                category="",
            )
            articles.append(article)

        logger.debug(
            "TavilyProvider._sync_search(%s) returned %d articles",
            keyword,
            len(articles),
        )
        return articles

    def _extract_keyword(self, url: str) -> str | None:
        """Extract search keyword from Tavily URL.

        Args:
            url: URL like 'search:AI' or 'tavily:news'

        Returns:
            Extracted keyword or None if invalid format.
        """
        if url.startswith("search:"):
            return url[7:].strip()  # Remove 'search:' prefix
        elif url.startswith("tavily:"):
            return url[7:].strip()  # Remove 'tavily:' prefix
        return None

    def parse_feed(self, url: str, response: Response = None) -> DiscoveredFeed:
        """Validate Tavily search URL and return as DiscoveredFeed.

        Args:
            url: Tavily search URL (e.g., 'search:AI').
            response: Unused for Tavily (API provides validation).

        Returns:
            DiscoveredFeed with valid=True if URL has a keyword.
        """
        keyword = self._extract_keyword(url)
        if not keyword:
            return DiscoveredFeed(
                url=url,
                title=None,
                feed_type="tavily",
                source=f"provider_{self.__class__.__name__}",
                page_url=url,
                valid=False,
            )

        return DiscoveredFeed(
            url=url,
            title=f"Search: {keyword}",
            feed_type="tavily",
            source=f"provider_{self.__class__.__name__}",
            page_url=url,
            valid=True,
        )

    def discover(
        self, url: str, response: Response = None, depth: int = 1
    ) -> list[DiscoveredFeed]:
        """Discover feed URLs - Tavily search doesn't need discovery.

        Args:
            url: Current page URL.
            response: Pre-fetched HTTP response (may be None).
            depth: Current crawl depth.

        Returns:
            Empty list - search URLs are directly parsed.
        """
        return []


# Register this provider - highest priority (400)
PROVIDERS.append(TavilyProvider())
