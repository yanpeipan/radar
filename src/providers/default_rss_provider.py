"""Default RSS provider - fallback only, never matches directly.

This provider is used when no other provider matches a URL.
match() returns False so it never matches URLs directly,
and priority() returns 0 so it's only tried after all other
providers have failed.
"""
from __future__ import annotations

from typing import List

from src.providers import PROVIDERS
from src.providers.base import Article, ContentProvider, Raw, TagParser


class DefaultRSSProvider:
    """Fallback RSS provider for unknown URL types.

    This provider never matches URLs directly. It is only used when
    no other provider matches a URL. The crawl() and parse() methods
    should not be called on this provider in practice.
    """

    def match(self, url: str) -> bool:
        """Never matches - only used as fallback.

        Args:
            url: URL to match (ignored).

        Returns:
            Always False - this provider is only a fallback.
        """
        return False

    def priority(self) -> int:
        """Lowest priority - only tried when all else fails.

        Returns:
            0 (lowest priority).
        """
        return 0

    def crawl(self, url: str) -> List[Raw]:
        """Not implemented - should not be called.

        This provider is only used as fallback when no other provider
        matches. If called, it indicates a bug in provider selection.

        Args:
            url: URL to crawl (ignored).

        Returns:
            Never returns - raises NotImplementedError.
        """
        raise NotImplementedError(
            "DefaultRSSProvider is fallback only and should not be called"
        )

    def parse(self, raw: Raw) -> Article:
        """Not implemented - should not be called.

        Args:
            raw: Raw content (ignored).

        Returns:
            Never returns - raises NotImplementedError.
        """
        raise NotImplementedError(
            "DefaultRSSProvider is fallback only and should not be called"
        )

    def tag_parsers(self) -> List[TagParser]:
        """Return empty list - no tag parsing for fallback.

        Returns:
            Empty list.
        """
        return []

    def parse_tags(self, article: Article) -> List[str]:
        """Return empty list - no tag parsing for fallback.

        Args:
            article: Article dict (ignored).

        Returns:
            Empty list.
        """
        return []


# Register this provider - it will be sorted last by priority()
PROVIDERS.append(DefaultRSSProvider())