"""Feed management operations for RSS reader.

Provides functions for adding, listing, removing, and refreshing RSS/Atom feeds.
Handles feed fetching, parsing with bozo detection, and article deduplication.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime
from src.config import get_timezone
from typing import Optional

import feedparser
import httpx

from src.db import get_connection, get_db_path
from src.models import Article, Feed
from src.crawl import is_github_blob_url
from src.github_ops import (
    get_or_create_github_repo,
    fetch_changelog_content,
    store_changelog_as_article,
    refresh_changelog,
    get_github_repo_by_owner_repo,
    RepoNotFoundError,
)

# Browser-like User-Agent header to avoid 403 bot blocks
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

logger = logging.getLogger(__name__)


class FeedNotFoundError(Exception):
    """Raised when a feed is not found in the database."""

    pass


def generate_feed_id() -> str:
    """Generate a unique ID for a new feed.

    Returns:
        A new UUID string.
    """
    return str(uuid.uuid4())


def add_github_blob_feed(url: str, github_blob: tuple[str, str, str, str]) -> Feed:
    """Add a feed from GitHub blob URL, storing changelog content as article.

    Args:
        url: The GitHub blob URL
        github_blob: Tuple of (owner, repo, branch, path) from is_github_blob_url()

    Returns:
        The created Feed object.

    Raises:
        ValueError: If content fetch fails or no github_repo could be created.
    """
    owner, repo, branch, path = github_blob
    filename = path.split('/')[-1] if '/' in path else path

    # D-04, D-06: Ensure github_repo entry exists for store_changelog_as_article()
    github_repo = get_or_create_github_repo(owner, repo)

    # D-06: Fetch content for the explicit path
    content = fetch_changelog_content(owner, repo, filename, branch)
    if not content:
        # D-07: No content -> clear error, do NOT add feed
        raise ValueError(f"Failed to fetch content from {url}")

    # Store changelog as article with repo_id association
    source_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{filename}"
    store_changelog_as_article(
        repo_id=github_repo.id,
        repo_name=github_repo.name,
        content=content,
        filename=filename,
        source_url=source_url,
    )

    # D-04, D-05: Create feed entry with GitHub URL as url
    feed_id = generate_feed_id()
    now = datetime.now(get_timezone()).isoformat()
    feed_title = f"{owner}/{repo} / {filename}"

    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Check if feed already exists
        cursor.execute("SELECT id FROM feeds WHERE url = ?", (url,))
        existing = cursor.fetchone()
        if existing:
            raise ValueError(f"Feed already exists: {url}")

        cursor.execute(
            """INSERT INTO feeds (id, name, url, etag, last_modified, last_fetched, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (feed_id, feed_title, url, None, None, now, now),
        )
        conn.commit()
    finally:
        conn.close()

    return Feed(
        id=feed_id,
        name=feed_title,
        url=url,
        etag=None,
        last_modified=None,
        last_fetched=now,
        created_at=now,
    )


def fetch_feed_content(
    url: str,
    etag: Optional[str] = None,
    last_modified: Optional[str] = None,
) -> tuple[Optional[bytes], Optional[str], Optional[str], int]:
    """Fetch feed content from URL with conditional request support.

    Args:
        url: The URL of the feed to fetch.
        etag: Optional ETag header for conditional fetching.
        last_modified: Optional Last-Modified header for conditional fetching.

    Returns:
        A tuple of (content, etag, last_modified, status_code).
        content is None if status is 304 (not modified).
        Raises httpx.RequestError or httpx.TimeoutException on network errors.
    """
    headers: dict[str, str] = {}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    # Merge browser headers with conditional headers
    request_headers = {**BROWSER_HEADERS, **headers}
    response = httpx.get(url, headers=request_headers, timeout=30.0, follow_redirects=True)

    # Handle 304 Not Modified (httpx raises on 304 after redirects)
    if response.status_code == 304:
        return None, None, None, 304

    response.raise_for_status()
    status_code = response.status_code

    # Extract headers for future conditional requests
    new_etag = response.headers.get("etag")
    new_last_modified = response.headers.get("last-modified")

    return response.content, new_etag, new_last_modified, status_code


def fetch_feed_content_with_scrapling_fallback(
    url: str,
    etag: Optional[str] = None,
    last_modified: Optional[str] = None,
) -> tuple[Optional[bytes], Optional[str], Optional[str], int]:
    """Fetch feed content with Scrapling fallback for Cloudflare-protected feeds.

    First tries httpx, then falls back to Scrapling if 403 is returned.
    This is needed because Cloudflare may block httpx HEAD/GET requests but allow
    Scrapling's browser-like requests.

    Args:
        url: The URL of the feed to fetch.
        etag: Optional ETag header for conditional fetching.
        last_modified: Optional Last-Modified header for conditional fetching.

    Returns:
        A tuple of (content, etag, last_modified, status_code).
        content is None if status is 304 (not modified).
        Raises exception only if both httpx and Scrapling fail.
    """
    try:
        content, new_etag, new_last_modified, status_code = fetch_feed_content(
            url, etag, last_modified
        )
        return content, new_etag, new_last_modified, status_code
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            logger.info("httpx returned 403 for %s, trying Scrapling fallback", url)
            try:
                from scrapling import Fetcher
                scraper = Fetcher()
                response = scraper.get(url)
                # Scrapling returns bytes in response.body
                content = response.body
                if content:
                    logger.info("Scrapling successfully fetched %s", url)
                    return content, None, None, 200
            except ImportError:
                logger.warning("Scrapling not installed, cannot fallback for %s", url)
            except Exception as scraper_err:
                logger.error("Scrapling failed for %s: %s", url, scraper_err)
        # Re-raise if not a 403, or if Scrapling also failed
        raise
    except Exception:
        # Re-raise other exceptions
        raise


def parse_feed(
    content: bytes,
    url: str,
) -> tuple[list[dict], bool, Optional[Exception]]:
    """Parse RSS/Atom feed content using feedparser.

    Args:
        content: Raw feed content as bytes.
        url: URL of the feed (used for logging).

    Returns:
        A tuple of (entries, bozo_flag, bozo_exception).
        bozo_flag is True if the feed is malformed (but parsing still succeeded).
        bozo_exception contains the exception if bozo_flag is True.
    """
    feed = feedparser.parse(content)

    bozo_flag = feed.bozo
    bozo_exception = None

    if bozo_flag:
        bozo_exception = feed.bozo_exception
        logger.warning(
            "Malformed feed detected for %s: %s",
            url,
            bozo_exception,
        )

    entries = []
    for entry in feed.entries:
        entries.append(entry)

    return entries, bozo_flag, bozo_exception


def generate_article_id(entry: feedparser.FeedParserDict) -> str:
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


def add_feed(url: str) -> Feed:
    """Add a new feed by URL.

    Fetches and parses the feed to validate the URL and extract metadata.

    Args:
        url: The URL of the feed to add.

    Returns:
        The created Feed object.

    Raises:
        ValueError: If the feed already exists or cannot be parsed.
    """
    # D-01, D-02, D-03: Detect GitHub blob URL and route to changelog flow
    github_blob = is_github_blob_url(url)
    if github_blob:
        return add_github_blob_feed(url, github_blob)

    # Fetch and parse the feed first to validate
    try:
        content, etag, last_modified, status_code = fetch_feed_content(url)
    except (httpx.RequestError, httpx.HTTPError, httpx.TimeoutException, OSError) as e:
        raise ValueError(f"Failed to fetch feed: {e}") from e

    if content is None:
        # 304 means feed hasn't changed, but we still need content to parse
        raise ValueError("Feed not modified (unexpected)")

    entries, bozo_flag, bozo_exception = parse_feed(content, url)

    if not entries and not bozo_flag:
        raise ValueError("No entries found in feed and feed appears valid")

    # Use feed title from parsing, or extract from URL if missing
    feed_title = None
    if hasattr(feedparser, "parse"):
        # Re-parse to get feed-level metadata
        parsed = feedparser.parse(content)
        feed_title = parsed.feed.get("title") if parsed.feed else None

    if not feed_title:
        feed_title = url

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
            (feed_id, feed_title, url, etag, last_modified, now, now),
        )
        conn.commit()
    finally:
        conn.close()

    return Feed(
        id=feed_id,
        name=feed_title,
        url=url,
        etag=etag,
        last_modified=last_modified,
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


def refresh_feed(feed_id: str) -> dict:
    """Refresh a feed to fetch new articles.

    Args:
        feed_id: The ID of the feed to refresh.

    Returns:
        Dict with new_articles count, updated_etag, updated_last_modified.

    Raises:
        FeedNotFoundError: If the feed does not exist.
    """
    feed = get_feed(feed_id)
    if not feed:
        raise FeedNotFoundError(f"Feed not found: {feed_id}")

    # Skip 'crawled' system feed - it has no URL to refresh
    if feed.id == "crawled":
        return {"new_articles": 0, "updated_etag": None, "updated_last_modified": None}

    # D-09: Detect GitHub blob URL and call refresh_changelog(repo_id)
    github_blob = is_github_blob_url(feed.url)
    if github_blob:
        owner, repo, branch, path = github_blob
        # Look up github_repo to get repo_id
        github_repo = get_github_repo_by_owner_repo(owner, repo)
        if not github_repo:
            return {"error": f"GitHub repo {owner}/{repo} not found"}
        result = refresh_changelog(github_repo.id)
        # Add new_articles count for CLI feedback
        if result.get("article_id"):
            result["new_articles"] = 1
        else:
            result["new_articles"] = 0
        return result

    try:
        content, etag, last_modified, status_code = fetch_feed_content_with_scrapling_fallback(
            feed.url,
            etag=feed.etag,
            last_modified=feed.last_modified,
        )
    except (httpx.RequestError, httpx.HTTPError, httpx.TimeoutException, OSError) as e:
        logger.error("Failed to refresh feed %s: %s", feed_id, e)
        return {
            "new_articles": 0,
            "updated_etag": feed.etag,
            "updated_last_modified": feed.last_modified,
            "error": str(e),
        }

    # Handle 304 Not Modified
    if content is None:
        logger.info("Feed %s not modified since last fetch", feed_id)
        return {
            "new_articles": 0,
            "updated_etag": feed.etag,
            "updated_last_modified": feed.last_modified,
        }

    entries, bozo_flag, bozo_exception = parse_feed(content, feed.url)

    new_articles = 0
    new_article_ids = []  # Track new articles for FTS5 sync
    articles_needing_tags = []  # Collect (article_id, title, description) tuples for tagging after commit
    now = datetime.now(get_timezone()).isoformat()

    conn = get_connection()
    try:
        cursor = conn.cursor()

        for entry in entries:
            article_id = generate_article_id(entry)

            # Extract entry fields
            title = entry.get("title")
            link = entry.get("link")
            guid = article_id
            pub_date = entry.get("published") or entry.get("updated")

            # Get description
            description = None
            if hasattr(entry, "description"):
                description = entry.description
            elif hasattr(entry, "summary"):
                description = entry.summary

            # Get content
            content_val = None
            if hasattr(entry, "content") and entry.content:
                content_val = entry.content[0].value if entry.content else None
            elif hasattr(entry, "summary_detail"):
                content_val = entry.summary_detail.value if hasattr(entry.summary_detail, "value") else None

            try:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO articles (id, feed_id, title, link, guid, pub_date, description, content, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (article_id, feed_id, title, link, guid, pub_date, description, content_val, now),
                )
                if cursor.rowcount > 0:
                    new_articles += 1
                    new_article_ids.append(article_id)
                    # Collect for tagging after commit to avoid nested connection writes
                    articles_needing_tags.append((article_id, title, description))
            except Exception as e:
                logger.warning("Failed to insert article %s: %s", article_id, e)

        # Sync new articles to FTS5
        for article_id in new_article_ids:
            cursor.execute(
                """
                INSERT INTO articles_fts(rowid, title, description, content)
                SELECT rowid, title, description, content FROM articles WHERE id = ?
                """,
                (article_id,),
            )

        # Update feed metadata
        cursor.execute(
            """
            UPDATE feeds SET etag = ?, last_modified = ?, last_fetched = ?
            WHERE id = ?
            """,
            (etag, last_modified, now, feed_id),
        )
        conn.commit()
    finally:
        conn.close()

    # Apply tag rules AFTER commit to avoid "database is locked" from nested connections
    # during the uncommitted transaction window
    from src.tag_rules import apply_rules_to_article
    for article_id, title, description in articles_needing_tags:
        try:
            matched_tags = apply_rules_to_article(article_id, title, description)
            if matched_tags:
                logger.info(f"Auto-tagged article {article_id} with: {matched_tags}")
        except Exception as e:
            logger.warning(f"Failed to apply tag rules to article {article_id}: {e}")

    return {
        "new_articles": new_articles,
        "updated_etag": etag,
        "updated_last_modified": last_modified,
    }
