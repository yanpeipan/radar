"""Feed fetching use cases - fetch single feed or all feeds via providers."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from src.config import get_timezone
from src.db import get_connection
from src.models import Feed
from src.providers import discover_or_default
from src.utils import generate_article_id, generate_feed_id

logger = logging.getLogger(__name__)


class FeedNotFoundError(Exception):
    """Raised when a feed is not found in the database."""

    pass


def add_feed(url: str) -> Feed:
    """Add a new feed by URL.

    Uses provider.feed_meta to fetch metadata and provider.crawl to validate.

    Args:
        url: The URL of the feed to add.

    Returns:
        The created Feed object.

    Raises:
        ValueError: If the feed already exists, cannot be fetched, or has no entries.
    """
    # Discover matching providers and try each until one succeeds
    providers = discover_or_default(url)

    feed_meta = None
    entries = None
    last_error = None

    for provider in providers:
        try:
            feed_meta = provider.feed_meta(url)
            entries = provider.crawl(url)
            if entries:
                break  # Success
        except Exception as e:
            last_error = e
            continue  # Try next provider

    if feed_meta is None or entries is None:
        if last_error:
            raise ValueError(f"All providers failed: {last_error}")
        raise ValueError("No provider could fetch feed metadata")

    if not entries:
        raise ValueError("No entries found in feed")

    # Check if feed already exists
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM feeds WHERE url = ?", (url,))
        existing = cursor.fetchone()
        if existing:
            raise ValueError(f"Feed already exists: {url}")
    finally:
        conn.close()

    # Create new feed
    feed_id = generate_feed_id()
    now = datetime.now(get_timezone()).isoformat()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO feeds (id, name, url, etag, last_modified, last_fetched, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feed_id,
                feed_meta.name,
                url,
                feed_meta.etag,
                feed_meta.last_modified,
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return Feed(
        id=feed_id,
        name=feed_meta.name,
        url=url,
        etag=feed_meta.etag,
        last_modified=feed_meta.last_modified,
        last_fetched=now,
        created_at=now,
    )


def list_feeds() -> list[Feed]:
    """List all feeds with article counts.

    Returns:
        List of Feed objects with article counts available via articles_count attribute.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT f.id, f.name, f.url, f.etag, f.last_modified, f.last_fetched, f.created_at,
                   COUNT(a.id) as articles_count
            FROM feeds f
            LEFT JOIN articles a ON f.id = a.feed_id
            GROUP BY f.id
            ORDER BY f.created_at DESC
            """,
        )
        rows = cursor.fetchall()
        feeds = []
        for row in rows:
            feed = Feed(
                id=row["id"],
                name=row["name"],
                url=row["url"],
                etag=row["etag"],
                last_modified=row["last_modified"],
                last_fetched=row["last_fetched"],
                created_at=row["created_at"],
            )
            feed.articles_count = row["articles_count"]
            feeds.append(feed)
        return feeds
    finally:
        conn.close()


def get_feed(feed_id: str) -> Optional[Feed]:
    """Get a single feed by ID.

    Args:
        feed_id: The ID of the feed to retrieve.

    Returns:
        The Feed object, or None if not found.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, url, etag, last_modified, last_fetched, created_at FROM feeds WHERE id = ?",
            (feed_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return Feed(
            id=row["id"],
            name=row["name"],
            url=row["url"],
            etag=row["etag"],
            last_modified=row["last_modified"],
            last_fetched=row["last_fetched"],
            created_at=row["created_at"],
        )
    finally:
        conn.close()


def remove_feed(feed_id: str) -> bool:
    """Remove a feed and all its articles.

    Args:
        feed_id: The ID of the feed to remove.

    Returns:
        True if the feed was deleted, False if not found.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted
    finally:
        conn.close()


def fetch_one(feed_or_id: str | Feed) -> dict:
    """Fetch new articles from a single feed using provider pattern.

    Args:
        feed_or_id: The Feed object or the ID of the feed to refresh.

    Returns:
        Dict with new_articles count and optional error.

    Raises:
        FeedNotFoundError: If the feed does not exist.
    """
    if isinstance(feed_or_id, Feed):
        feed = feed_or_id
    else:
        feed = get_feed(feed_or_id)
        if not feed:
            raise FeedNotFoundError(f"Feed not found: {feed_or_id}")

    # Skip 'crawled' system feed - it has no URL to refresh
    if feed.id == "crawled":
        return {"new_articles": 0}

    # Use discover_or_default to find provider for this feed URL
    providers = discover_or_default(feed.url)
    if not providers:
        return {"new_articles": 0, "error": f"No provider for {feed.url}"}

    provider = providers[0]  # highest priority match
    provider_name = provider.__class__.__name__.replace("Provider", "")

    # Crawl using the discovered provider
    try:
        raw_items = provider.crawl(feed.url)
    except Exception as e:
        logger.error("Failed to crawl %s: %s", feed.url, e)
        return {"new_articles": 0, "error": str(e)}

    if not raw_items:
        return {"new_articles": 0}

    # Parse and store each item
    new_count = 0
    articles_needing_tags = []

    for raw in raw_items:
        article = provider.parse(raw)
        new_article = _store_article(
            feed_id=feed.id,
            article=article,
            provider_name=provider_name,
        )
        if new_article:
            new_count += 1
            # Collect for tagging after commit
            articles_needing_tags.append(
                (article.get("guid") or generate_article_id(article), article.get("title"), article.get("description"))
            )

    # Apply tag rules AFTER store to avoid nested connection writes
    from src.tag_rules import apply_rules_to_article
    for article_id, title, description in articles_needing_tags:
        try:
            matched_tags = apply_rules_to_article(article_id, title, description)
            if matched_tags:
                logger.info(f"Auto-tagged article {article_id} with: {matched_tags}")
        except Exception as e:
            logger.warning(f"Failed to apply tag rules to article {article_id}: {e}")

    return {"new_articles": new_count}


def fetch_all() -> dict:
    """Fetch new articles from all subscribed feeds.

    Returns:
        Dict with total_new, success_count, error_count, errors.
    """
    feeds = list_feeds()
    if not feeds:
        return {"total_new": 0, "success_count": 0, "error_count": 0, "errors": []}

    total_new = 0
    success_count = 0
    error_count = 0
    errors = []

    for feed_obj in feeds:
        try:
            result = fetch_one(feed_obj)
            if "error" in result and result.get("new_articles", 0) == 0:
                # Error but no articles - likely no provider
                pass
            if result.get("new_articles", 0) > 0:
                total_new += result["new_articles"]
            success_count += 1
        except Exception as e:
            error_count += 1
            errors.append(f"{feed_obj.name}: {e}")

    return {
        "total_new": total_new,
        "success_count": success_count,
        "error_count": error_count,
        "errors": errors,
    }


def _store_article(feed_id: str, article: dict, provider_name: str) -> bool:
    """Store an article with FTS5 sync.

    Args:
        feed_id: The feed ID to associate with.
        article: Article dict from provider.parse().
        provider_name: Name of provider for logging.

    Returns:
        True if new article was stored, False if duplicate or error.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Generate article ID if not provided
        article_id = article.get("guid") or generate_article_id(article)

        now = datetime.now(get_timezone()).isoformat()

        cursor.execute(
            """
            INSERT OR IGNORE INTO articles (id, feed_id, title, link, guid, pub_date, description, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article_id,
                feed_id,
                article.get("title"),
                article.get("link"),
                article.get("guid") or article_id,
                article.get("pub_date"),
                article.get("description"),
                article.get("content"),
                now,
            ),
        )
        if cursor.rowcount > 0:
            # Sync new article to FTS5
            cursor.execute(
                """
                INSERT INTO articles_fts(rowid, title, description, content)
                SELECT rowid, title, description, content FROM articles WHERE id = ?
                """,
                (article_id,),
            )
        conn.commit()
        conn.close()
        return cursor.rowcount > 0
    except Exception as e:
        logger.warning(f"Failed to store article from {provider_name}: {e}")
        return False
