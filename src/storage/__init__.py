"""Storage package for SQLite database operations.

Vector storage (ChromaDB) imports are lazy to avoid torch import overhead.
Import vector functions directly from src.storage.vector when needed:
    from src.storage.vector import search_articles_semantic, add_article_embedding
"""

from src.storage.sqlite.impl import (
    add_feed,
    feed_exists,
    get_article,
    get_article_detail,
    get_article_with_llm,
    get_articles_by_ids,
    get_db,
    get_db_path,
    get_feed,
    get_feeds_by_ids,
    init_db,
    list_articles,
    list_feeds,
    mark_article_read,
    mark_article_unread,
    remove_feed,
    search_articles_fts,
    star_article,
    store_article,
    store_article_async,
    toggle_article_star,
    unstar_article,
    update_article_content,
    update_article_llm,
    update_feed,
    update_feed_metadata,
    upsert_articles,
    upsert_articles_async,
    upsert_feed,
)
from src.storage.sqlite.init import DatabaseInitializer
