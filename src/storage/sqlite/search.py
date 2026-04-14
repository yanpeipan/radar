"""FTS5 full-text search for articles.

Provides FTS5-based article search with BM25 ranking, date filtering,
and feed/group filtering.
"""

from __future__ import annotations

import logging
import math

from src.storage.sqlite.conn import get_db
from src.storage.sqlite.utils import _date_to_timestamp, _date_to_timestamp_end

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
    tag: str | None = None,
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
        tag: Optional tag name to filter by (articles from feeds with this tag).

    Returns:
        List of ArticleListItem objects ranked by BM25 score.
    """
    from src.application.articles import ArticleListItem
    from src.application.config import get_bm25_factor, get_timezone

    if not query or not query.strip():
        return []

    tz = get_timezone()
    where_sql, params = _build_fts_where_clause(
        query, feed_id=feed_id, since=since, until=until, on=on, groups=groups, tz=tz
    )

    with get_db() as conn:
        cursor = conn.cursor()

        # Build dynamic FROM clause
        from_parts = [
            "articles_fts",
            "JOIN articles a ON articles_fts.rowid = a.rowid",
            "JOIN feeds f ON a.feed_id = f.id",
        ]
        if tag:
            from_parts.append("INNER JOIN feed_tags ft ON f.id = ft.feed_id")
            from_parts.append("INNER JOIN tags t ON ft.tag_id = t.id")
        from_sql = "\n".join(from_parts)

        # Extend WHERE clause with tag filter (already built by _build_fts_where_clause)
        if tag:
            where_sql += " AND t.name = ?"
            params.append(tag)

        query_sql = f"""
            SELECT a.id, a.feed_id, f.name as feed_name,
                   a.title, a.link, a.guid, a.published_at, a.description,
                   bm25(articles_fts, 2.0, 1.0, 0.5) as bm25_score
            FROM {from_sql}
            WHERE {where_sql}
            ORDER BY bm25(articles_fts, 2.0, 1.0, 0.5)
            LIMIT ?
            """
        cursor.execute(  # nosec B608
            query_sql,
            [*params, limit],
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
