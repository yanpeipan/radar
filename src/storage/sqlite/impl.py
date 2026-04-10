"""Backward-compatibility shim for SQLite storage.

All functionality has been extracted into domain-specific modules:
- src.storage.sqlite.conn     : DB connection, write lock, date utilities
- src.storage.sqlite.feeds    : Feed CRUD operations
- src.storage.sqlite.articles  : Article CRUD and listing
- src.storage.sqlite.llm       : Article LLM fields (summary, quality, keywords, tags)
- src.storage.sqlite.search   : FTS5 full-text search

This module re-exports everything from those modules so that existing
imports (e.g. ``from src.storage.sqlite.impl import store_article``) continue
to work without modification.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# articles.py - Article CRUD and listing
# ---------------------------------------------------------------------------
from src.storage.sqlite.articles import (  # noqa: F401, E402
    _batch_upsert_articles,
    _get_article_field,
    get_article,
    get_article_detail,
    get_article_id_by_url,
    get_articles_by_ids,
    list_articles,
    store_article,
    store_article_async,
    update_article_content,
    upsert_articles,
    upsert_articles_async,
)

# ---------------------------------------------------------------------------
# conn.py  - DB connection, write lock, date utilities
# ---------------------------------------------------------------------------
from src.storage.sqlite.conn import (  # noqa: F401, E402
    _DB_PATH,
    _date_to_str,
    _date_to_str_end,
    _date_to_timestamp,
    _date_to_timestamp_end,
    _get_connection,
    _get_db_write_lock,
    _normalize_published_at,
    get_db,
    get_db_path,
    init_db,
)

# ---------------------------------------------------------------------------
# feeds.py - Feed CRUD
# ---------------------------------------------------------------------------
from src.storage.sqlite.feeds import (  # noqa: F401, E402
    add_feed,
    feed_exists,
    get_feed,
    get_feeds_by_ids,
    list_feeds,
    remove_feed,
    update_feed,
    update_feed_metadata,
    upsert_feed,
)

# ---------------------------------------------------------------------------
# llm.py - Article LLM fields
# ---------------------------------------------------------------------------
from src.storage.sqlite.llm import (  # noqa: F401, E402
    get_article_with_llm,
    list_articles_for_llm,
    update_article_llm,
)

# ---------------------------------------------------------------------------
# search.py - FTS5 full-text search
# ---------------------------------------------------------------------------
from src.storage.sqlite.search import (  # noqa: F401, E402
    search_articles_fts,
)
