"""Provider base protocols for the plugin architecture.

Defines the ContentProvider protocol that all providers must implement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from scrapling.engines.toolbelt.custom import Response

    from src.discovery.models import DiscoveredFeed
    from src.models import Feed, FeedType

# Forward declarations for Article and Raw types
# Raw will be defined by concrete providers based on their crawl() return type
Article = dict  # Using dict for flexibility; concrete providers define structure
Raw = dict  # Raw crawl result


@dataclass
class FetchedResult:
    """Result of a fetch operation, including feed metadata for conditional fetching."""

    articles: list[Article]
    etag: str | None = None
    modified_at: str | None = None


@runtime_checkable
class ContentProvider(Protocol):
    """Protocol for content providers (RSS, GitHub, etc.).

    Key invariant: match() with response=None MUST be URL-only matching.
    When response is None, match() should NOT make any HTTP requests.
    This enables fast provider selection without network overhead.

    All providers must implement these methods. The @runtime_checkable decorator
    allows isinstance() checks for protocol conformance.
    """

    def match(
        self, url: str, response: Response = None, feed_type: FeedType = None
    ) -> bool:
        """Return True if this provider handles the URL.

        Args:
            url: URL to check.
            response: Optional HTTP response from discovery phase.
                If None, provider should not make HTTP requests - only use URL
                for matching (URL-only mode). This is critical for performance
                and to avoid unnecessary network calls during provider selection.
            feed_type: Optional FeedType to restrict matching to specific type.
                If None, provider should use its default matching logic.

        Returns:
            True if this provider can handle the URL, False otherwise.
        """
        ...

    def priority(self) -> int:
        """Return provider priority for ordering.

        Higher values are tried first. Default RSS provider returns 0.

        Returns:
            Integer priority value. Higher = tried first.
        """
        ...

    def fetch_articles(self, feed: Feed) -> FetchedResult:
        """Fetch and parse content from Feed.

        Args:
            feed: Feed object containing url and optional etag/modified_at.

        Returns:
            FetchedResult with articles list and updated etag/modified_at.
        """
        ...

    def parse_feed(self, url: str, response: Response = None) -> DiscoveredFeed:
        """Validate URL is a feed and return as DiscoveredFeed.

        IMPORTANT: This method raises an exception if the URL cannot be validated.
        Only call parse_feed() after match() has confirmed this provider handles the URL.

        Args:
            url: URL of the feed to parse metadata for.
            response: Pre-fetched HTTP response (may be None).

        Returns:
            DiscoveredFeed with valid=True if URL is a valid feed.

        Raises:
            ValueError: If URL cannot be fetched or parsed as a valid feed.
            Exception: Other exceptions may be raised for network errors, etc.
        """
        ...

    def discover(
        self, url: str, response: Response = None, depth: int = 1
    ) -> list[DiscoveredFeed]:
        """Discover feed URLs from a page.

        Args:
            url: Current page URL.
            response: Pre-fetched HTTP response (may be None).
            depth: Current crawl depth (1 = initial, can make HTTP requests;
                   >1 = BFS deeper, should use response only if available).

        Returns:
            List of discovered DiscoveredFeed (unverified, validation happens in caller).
        """
        ...
