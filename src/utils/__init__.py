"""Utility modules."""

from __future__ import annotations

import hashlib
import uuid


def generate_feed_id() -> str:
    """Generate a unique ID for a new feed.

    Returns:
        A new UUID string.
    """
    return str(uuid.uuid4())


def generate_article_id(entry) -> str:
    """Generate a unique article ID from a feed entry.

    Uses guid if available, falls back to link, then generates a hash
    from link and pub_date.

    Args:
        entry: A feedparser entry dict.

    Returns:
        A unique string identifier for the article.
    """
    # Try guid first
    article_id = entry.get("id")
    if article_id:
        return article_id

    # Fall back to link
    link = entry.get("link")
    if link:
        return link

    # Last resort: hash of link + pub_date
    pub_date = entry.get("published") or entry.get("updated") or ""
    hash_input = f"{link}:{pub_date}"
    return hashlib.sha256(hash_input.encode()).hexdigest()
