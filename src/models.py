"""Data models for RSS reader.

Defines dataclasses for Feed and Article entities.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FeedType(Enum):
    """Enum for feed types, used to route to the correct provider."""

    RSS = "rss"
    GITHUB_RELEASE = "github_release"


@dataclass
class Feed:
    """Represents an RSS or Atom feed source.

    Attributes:
        id: Unique identifier for the feed.
        name: Display name of the feed.
        url: URL of the feed.
        etag: ETag header value for conditional fetching.
        modified_at: Last-Modified header value for conditional fetching.
        fetched_at: ISO timestamp of last successful fetch.
        created_at: ISO timestamp when feed was added.
        metadata: JSON string with provider-specific data (e.g., github_token).
    """

    id: str
    name: str
    url: str
    created_at: str
    etag: str | None = None
    modified_at: str | None = None
    fetched_at: str | None = None
    metadata: str | None = None  # JSON string with provider-specific data
    weight: float | None = None  # Feed weight for semantic search ranking (default 0.3)


@dataclass
class FeedMetaData:
    """Provider-specific metadata for a feed.

    Attributes:
        selectors: Optional list of path prefix filters for WebpageProvider.
        feed_type: Optional feed type ('rss', 'atom', 'rdf', 'webpage', 'github_release').
    """

    selectors: list[str] | None = None
    feed_type: str | None = None

    def to_json(self) -> str:
        """Serialize to JSON string, excluding None values."""
        import json

        data = {k: v for k, v in self.__dict__.items() if v is not None}
        return json.dumps(data) if data else None


@dataclass
class Article:
    """Represents an article or item from a feed.

    Attributes:
        id: Unique identifier for the article.
        feed_id: ID of the feed this article belongs to.
        title: Title of the article.
        link: URL link to the full article.
        guid: Global unique identifier from the feed (used for dedup).
        published_at: Publication date from the feed.
        description: Short description or summary.
        content: Full content or body.
        created_at: ISO timestamp when article was stored.
    """

    id: str
    feed_id: str
    guid: str
    created_at: str
    title: str | None = None
    link: str | None = None
    published_at: str | None = None
    description: str | None = None
    content: str | None = None
