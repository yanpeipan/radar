"""Provider base protocols for the plugin architecture.

Defines the ContentProvider protocol that all providers must implement.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Protocol, runtime_checkable

# Forward declarations for Article and Raw types
# Raw will be defined by concrete providers based on their crawl() return type
Article = dict  # Using dict for flexibility; concrete providers define structure
Raw = dict      # Raw crawl result


@dataclass
class CrawlResult:
    """Result of a crawl operation, including feed metadata for conditional fetching."""
    entries: List[Raw]
    etag: Optional[str] = None
    last_modified: Optional[str] = None


@runtime_checkable
class ContentProvider(Protocol):
    """Protocol for content providers (RSS, GitHub, etc.).

    All providers must implement these methods. The @runtime_checkable decorator
    allows isinstance() checks for protocol conformance.
    """

    def match(self, url: str) -> bool:
        """Return True if this provider handles the URL.

        Args:
            url: URL to check.

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

    def crawl(self, url: str) -> List[Raw]:
        """Fetch raw content from URL.

        Args:
            url: URL to crawl.

        Returns:
            List of raw content dicts to be passed to parse().
            Returns empty list if crawl fails (caller handles retry via error isolation).
        """
        ...

    async def crawl_async(self, url: str, etag: Optional[str] = None, last_modified: Optional[str] = None) -> CrawlResult:
        """Asynchronous crawl - default uses run_in_executor.

        Override this method in providers that support true async HTTP
        (e.g., RSSProvider with httpx.AsyncClient).

        Default implementation wraps the sync crawl() method in a thread pool
        executor to avoid blocking the event loop.

        Args:
            url: URL to crawl.
            etag: Optional ETag header for conditional fetching.
            last_modified: Optional Last-Modified header for conditional fetching.

        Returns:
            CrawlResult with entries and updated etag/last_modified for future
            conditional requests. Entries may be empty on crawl failure.
        """
        ...

    def parse(self, raw: Raw) -> Article:
        """Convert raw crawl result to Article.

        Args:
            raw: Raw content dict from crawl().

        Returns:
            Article dict with fields: title, link, guid, pub_date, description, content.
        """
        ...

    def feed_meta(self, url: str) -> "Feed":
        """Fetch feed metadata from URL without storing.

        Args:
            url: URL of the feed to get metadata for.

        Returns:
            Feed object with name, url, and basic metadata populated.
            Raises exception if URL cannot be fetched or parsed.
        """
        ...