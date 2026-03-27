"""Data models for RSS reader.

Defines dataclasses for Feed and Article entities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Feed:
    """Represents an RSS or Atom feed source.

    Attributes:
        id: Unique identifier for the feed.
        name: Display name of the feed.
        url: URL of the feed.
        etag: ETag header value for conditional fetching.
        last_modified: Last-Modified header value for conditional fetching.
        last_fetched: ISO timestamp of last successful fetch.
        created_at: ISO timestamp when feed was added.
        metadata: JSON string with provider-specific data (e.g., github_token).
    """

    id: str
    name: str
    url: str
    created_at: str
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    last_fetched: Optional[str] = None
    metadata: Optional[str] = None  # JSON string with provider-specific data


@dataclass
class Article:
    """Represents an article or item from a feed.

    Attributes:
        id: Unique identifier for the article.
        feed_id: ID of the feed this article belongs to.
        title: Title of the article.
        link: URL link to the full article.
        guid: Global unique identifier from the feed (used for dedup).
        pub_date: Publication date from the feed.
        description: Short description or summary.
        content: Full content or body.
        created_at: ISO timestamp when article was stored.
    """

    id: str
    feed_id: str
    guid: str
    created_at: str
    title: Optional[str] = None
    link: Optional[str] = None
    pub_date: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
