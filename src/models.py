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


@dataclass
class GitHubRepo:
    """Represents a monitored GitHub repository.

    Attributes:
        id: Unique identifier for the repo entry.
        name: Display name (derived from repo name).
        owner: GitHub owner (user or organization).
        repo: Repository name.
        last_fetched: ISO timestamp of last API check.
        last_tag: Last seen release tag (for change detection).
        created_at: ISO timestamp when repo was added.
    """
    id: str
    name: str
    owner: str
    repo: str
    created_at: str
    last_fetched: Optional[str] = None
    last_tag: Optional[str] = None


@dataclass
class GitHubRelease:
    """Represents a GitHub release.

    Attributes:
        id: Unique identifier for the release.
        repo_id: ID of the parent GitHubRepo.
        tag_name: Version tag (e.g., "v1.2.3").
        name: Release title (often same as tag_name).
        body: Release notes in markdown.
        html_url: URL to the release page.
        published_at: ISO timestamp of release publication.
        created_at: ISO timestamp when release was stored.
    """
    id: str
    repo_id: str
    tag_name: str
    html_url: str
    published_at: Optional[str] = None
    name: Optional[str] = None
    body: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class Tag:
    """Represents an article tag.

    Attributes:
        id: Unique identifier for the tag.
        name: Display name of the tag (unique).
        created_at: ISO timestamp when tag was created.
    """
    id: str
    name: str
    created_at: str


@dataclass
class ArticleTagLink:
    """Represents a link between an article and a tag."""
    article_id: str
    tag_id: str
    created_at: str
