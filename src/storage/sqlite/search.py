"""FTS5 full-text search for articles.

Provides FTS5-based article search with BM25 ranking, date filtering,
and feed/group filtering.
"""

from __future__ import annotations

import logging
import math

from src.storage.sqlite.conn import get_db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_fts_where_clause(
    query: str,
    feed_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    on: list[str] | None = None,
    groups: list[str] | None = None,
    tz=None,
) -> tuple[str, list]:
    """Assemble WHERE clause parts and params for FTS5 search.

    Args:
        query: FTS5 search query string.
        feed_id: Optional feed ID to filter by.
        since: Optional start date (inclusive), format YYYY-MM-DD.
        until: Optional end date (inclusive), format YYYY-MM-DD.
        on: Optional list of specific dates to match.
        groups: Optional list of feed groups to filter by (OR semantics).
        tz: Timezone from get_timezone().

    Returns:
        Tuple of (where_sql string, [params list]).
    """
    where_parts = ["articles_fts MATCH ?"]
    params = [query]

    if feed_id:
        where_parts.append("a.feed_id = ?")
        params.append(feed_id)

    # Date filtering (using timestamp comparison)
    if since:
        where_parts.append("a.published_at >= ?")
        params.append(_date_to_timestamp(since, tz))
    if until:
        where_parts.append("a.published_at <= ?")
        params.append(_date_to_timestamp_end(until, tz))
    if on:
        on_timestamps = [_date_to_timestamp(d, tz) for d in on]
        placeholders = ",".join("?" * len(on_timestamps))
        where_parts.append(f"a.published_at IN ({placeholders})")
        params.extend(on_timestamps)

    if groups:
        placeholders = ",".join("?" * len(groups))
        where_parts.append(f'f."group" IN ({placeholders})')
        params.extend(groups)

    where_sql = " AND ".join(where_parts)
    return where_sql, params


def _date_to_timestamp(date_str: str, tz) -> int:
    """Convert YYYY-MM-DD to Unix timestamp at start of day in timezone."""
    from datetime import datetime

    dt = datetime.strptime(date_str, "%Y-%m-%d")
    dt = dt.replace(tzinfo=tz)
    return int(dt.timestamp())


def _date_to_timestamp_end(date_str: str, tz) -> int:
    """Convert YYYY-MM-DD to Unix timestamp at end of day (23:59:59) in timezone."""
    from datetime import datetime

    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tz)
    dt = dt.replace(hour=23, minute=59, second=59)
    return int(dt.timestamp())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def search_articles_fts(
    query: str,
    limit: int = 20,
    feed_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    on: list[str] | None = None,
    groups: list[str] | None = None,
) -> list:
    """Search articles using FTS5 full-text search.

    Args:
        query: Search query string.
        limit: Maximum number of results.
        feed_id: Optional feed ID to filter by.
        since: Optional start date (inclusive), format YYYY-MM-DD.
        until: Optional end date (inclusive), format YYYY-MM-DD.
        on: Optional list of specific dates to match.
        groups: Optional list of feed groups to filter by (OR semantics).

    Returns:
        List of ArticleListItem objects ranked by BM25 score.
    """
    from src.application.articles import ArticleListItem
    from src.application.config import get_bm25_factor, get_timezone

    if not query or not query.strip():
        return []

    tz = get_timezone()

    # Build WHERE clause for date filtering (using timestamp comparison)
    date_conditions = []
    date_params = []
    if since:
        date_conditions.append("a.published_at >= ?")
        date_params.append(_date_to_timestamp(since, tz))
    if until:
        date_conditions.append("a.published_at <= ?")
        date_params.append(_date_to_timestamp_end(until, tz))
    if on:
        on_timestamps = [_date_to_timestamp(d, tz) for d in on]
        placeholders = ",".join("?" * len(on_timestamps))
        date_conditions.append(f"a.published_at IN ({placeholders})")
        date_params.extend(on_timestamps)
    date_clause = " AND ".join(date_conditions) if date_conditions else None

    with get_db() as conn:
        cursor = conn.cursor()
        if feed_id:
            where_parts = ["articles_fts MATCH ?", "a.feed_id = ?"]
            params = [query, feed_id]
            if date_clause:
                where_parts.append(date_clause)
                params.extend(date_params)
            if groups:
                placeholders = ",".join("?" * len(groups))
                where_parts.append(f'f."group" IN ({placeholders})')
                params.extend(groups)
            where_sql = " AND ".join(where_parts)
            cursor.execute(  # nosec B608
                f"""
                SELECT a.id, a.feed_id, f.name as feed_name,
                       a.title, a.link, a.guid, a.published_at, a.description,
                       bm25(articles_fts, 2.0, 1.0, 0.5) as bm25_score
                FROM articles_fts
                JOIN articles a ON articles_fts.rowid = a.rowid
                JOIN feeds f ON a.feed_id = f.id
                WHERE {where_sql}
                ORDER BY bm25(articles_fts, 2.0, 1.0, 0.5)
                LIMIT ?
                """,
                [*params, limit],
            )
        else:
            if groups:
                placeholders = ",".join("?" * len(groups))
                groups_clause = f'f."group" IN ({placeholders})'
                if date_clause:
                    cursor.execute(  # nosec B608
                        f"""
                        SELECT a.id, a.feed_id, f.name as feed_name,
                               a.title, a.link, a.guid, a.published_at, a.description,
                               bm25(articles_fts, 2.0, 1.0, 0.5) as bm25_score
                        FROM articles_fts
                        JOIN articles a ON articles_fts.rowid = a.rowid
                        JOIN feeds f ON a.feed_id = f.id
                        WHERE articles_fts MATCH ? AND {date_clause} AND {groups_clause}
                        ORDER BY bm25(articles_fts, 2.0, 1.0, 0.5)
                        LIMIT ?
                        """,
                        [query, *date_params, *groups, limit],
                    )
                else:
                    cursor.execute(  # nosec B608
                        f"""
                        SELECT a.id, a.feed_id, f.name as feed_name,
                               a.title, a.link, a.guid, a.published_at, a.description,
                               bm25(articles_fts, 2.0, 1.0, 0.5) as bm25_score
                        FROM articles_fts
                        JOIN articles a ON articles_fts.rowid = a.rowid
                        JOIN feeds f ON a.feed_id = f.id
                        WHERE articles_fts MATCH ? AND {groups_clause}
                        ORDER BY bm25(articles_fts, 2.0, 1.0, 0.5)
                        LIMIT ?
                        """,
                        [query, *groups, limit],
                    )
            elif date_clause:
                cursor.execute(  # nosec B608
                    f"""
                    SELECT a.id, a.feed_id, f.name as feed_name,
                           a.title, a.link, a.guid, a.published_at, a.description,
                           bm25(articles_fts, 2.0, 1.0, 0.5) as bm25_score
                    FROM articles_fts
                    JOIN articles a ON articles_fts.rowid = a.rowid
                    JOIN feeds f ON a.feed_id = f.id
                    WHERE articles_fts MATCH ? AND {date_clause}
                    ORDER BY bm25(articles_fts, 2.0, 1.0, 0.5)
                    LIMIT ?
                    """,
                    [query, *date_params, limit],
                )
            else:
                cursor.execute(
                    """
                    SELECT a.id, a.feed_id, f.name as feed_name,
                           a.title, a.link, a.guid, a.published_at, a.description,
                           bm25(articles_fts, 2.0, 1.0, 0.5) as bm25_score
                    FROM articles_fts
                    JOIN articles a ON articles_fts.rowid = a.rowid
                    JOIN feeds f ON a.feed_id = f.id
                    WHERE articles_fts MATCH ?
                    ORDER BY bm25(articles_fts, 2.0, 1.0, 0.5)
                    LIMIT ?
                    """,
                    (query, limit),
                )
        factor = get_bm25_factor()
        return [
            ArticleListItem(
                id=row["id"],
                feed_id=row["feed_id"],
                feed_name=row["feed_name"],
                title=row["title"],
                link=row["link"],
                guid=row["guid"],
                published_at=row["published_at"],
                description=row["description"],
                bm25_score=1 / (1 + math.exp(row["bm25_score"] * factor)),
            )
            for row in cursor.fetchall()
        ]
