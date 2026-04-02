"""Data models for RSS reader using Pydantic.

Defines Pydantic models for Feed, Article, and FeedMetaData entities
with runtime validation.
"""

from __future__ import annotations

import json
import re
from contextlib import suppress
from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class FeedType(Enum):
    """Enum for feed types, used to route to the correct provider."""

    RSS = "rss"
    GITHUB_RELEASE = "github_release"
    TAVILY = "tavily"
    GITHUB_TRENDING = "github_trending"
    NITTER = "nitter"


class FeedMetaData(BaseModel):
    """Provider-specific metadata for a feed.

    Attributes:
        selectors: Optional list of path prefix filters for WebpageProvider.
        feed_type: Optional feed type ('rss', 'atom', 'rdf', 'webpage', 'github_release').
    """

    model_config = ConfigDict(extra="forbid")

    selectors: list[str] | None = None
    feed_type: str | None = None

    def to_json(self) -> str | None:
        """Serialize to JSON string, excluding None values (backward compat)."""
        data = self.model_dump(exclude_none=True)
        return json.dumps(data) if data else None


# Custom URL pattern that validates URL format
# Accepts HTTP/HTTPS URLs and special feed identifiers (x:, search:, tavily:, nitter:, github:, gh:, etc.)
UrlPattern = re.compile(
    r"^(https?://[^\s]+$|"  # http:// or https:// followed by non-whitespace
    r"(?:x|search|tavily|nitter|github|gh|rss|atom|rdf|webpage):.*)$",  # special identifiers (allow empty)
    re.IGNORECASE,
)


class Feed(BaseModel):
    """Represents an RSS or Atom feed source.

    Attributes:
        id: Unique identifier for the feed.
        name: Display name of the feed.
        url: URL of the feed (validated for URL format, stored as string).
        etag: ETag header value for conditional fetching.
        modified_at: Last-Modified header value for conditional fetching.
        fetched_at: ISO timestamp of last successful fetch.
        created_at: ISO timestamp when feed was added.
        metadata: JSON string with provider-specific data, or FeedMetaData object.
            When assigned a FeedMetaData object, it is serialized to JSON string.
            When accessed, it returns the stored string (backward compat with storage layer).
            Use metadata_parsed property to get typed FeedMetaData object.
        weight: Feed weight for semantic search ranking (default 0.3, range 0-1).
    """

    model_config = ConfigDict(
        extra="allow"
    )  # Allow dynamic attributes like articles_count

    id: str
    name: str = Field(max_length=200)
    url: str  # Stored as string, validated via field_validator
    created_at: str
    etag: str | None = None
    modified_at: str | None = None
    fetched_at: str | None = None
    metadata: str | FeedMetaData | None = None  # Stored as JSON string for DB compat
    weight: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not UrlPattern.match(v):
            raise ValueError(f"Invalid URL format: {v!r}")
        return v

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: str | FeedMetaData | None) -> str | None:
        """Validate metadata is valid JSON if provided."""
        if v is None:
            return v
        if isinstance(v, str):
            # Try to validate as FeedMetaData JSON
            with suppress(Exception):
                FeedMetaData.model_validate_json(v)
        elif isinstance(v, FeedMetaData):
            # Convert FeedMetaData to JSON string
            return v.to_json()
        return v

    @property
    def metadata_parsed(self) -> FeedMetaData | None:
        """Access metadata as a parsed FeedMetaData object (lazy migration)."""
        if self.metadata is None:
            return None
        return FeedMetaData.model_validate_json(self.metadata)


class Article(BaseModel):
    """Represents an article or item from a feed.

    Attributes:
        id: Unique identifier for the article.
        feed_id: ID of the feed this article belongs to.
        title: Title of the article (max 500 chars).
        link: URL link to the full article (validated for URL format).
        guid: Global unique identifier from the feed (used for dedup).
        published_at: Publication date from the feed.
        description: Short description or summary.
        content: Full content or body.
        created_at: ISO timestamp when article was stored.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    feed_id: str
    guid: str
    created_at: str
    title: str | None = Field(default=None, max_length=500)
    link: str | None = None  # Stored as string for DB compatibility
    published_at: str | None = None
    description: str | None = None
    content: str | None = None

    @field_validator("link")
    @classmethod
    def validate_link(cls, v: str | None) -> str | None:
        """Validate link URL format if provided."""
        if v is None:
            return v
        if not UrlPattern.match(v):
            raise ValueError(f"Invalid URL format: {v!r}")
        return v
