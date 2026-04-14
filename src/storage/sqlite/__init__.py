"""SQLite storage package."""

from src.storage.sqlite.articles import (
    get_article,
    get_article_detail,
    get_articles_by_ids,
    list_articles,
    store_article,
    store_article_async,
    update_article_content,
    upsert_articles,
    upsert_articles_async,
)
from src.storage.sqlite.conn import (
    _DB_PATH,
    _get_db_write_lock,
    get_db,
    get_db_path,
    init_db,
)
from src.storage.sqlite.feeds import (
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
from src.storage.sqlite.init import DatabaseInitializer
from src.storage.sqlite.llm import (
    get_article_with_llm,
    update_article_llm,
)
from src.storage.sqlite.search import search_articles_fts
from src.storage.sqlite.status import (
    mark_article_read,
    mark_article_unread,
    star_article,
    toggle_article_star,
    unstar_article,
)

__all__ = [
    "DatabaseInitializer",
    "get_db",
    "init_db",
    "store_article",
    "store_article_async",
    "upsert_articles",
    "upsert_articles_async",
    "get_db_path",
    "feed_exists",
    "add_feed",
    "list_feeds",
    "get_feed",
    "get_feeds_by_ids",
    "remove_feed",
    "update_feed",
    "update_feed_metadata",
    "update_article_content",
    "upsert_feed",
    "list_articles",
    "get_article",
    "get_article_detail",
    "search_articles_fts",
    "get_articles_by_ids",
    "update_article_llm",
    "get_article_with_llm",
    "mark_article_read",
    "mark_article_unread",
    "toggle_article_star",
    "star_article",
    "unstar_article",
    "tag_exists",
    "add_tag",
    "list_tags",
    "get_tag",
    "delete_tag",
]
