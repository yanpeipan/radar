"""Storage package for SQLite database operations.

Vector storage (ChromaDB) imports are lazy to avoid torch import overhead.
Import vector functions directly from src.storage.vector when needed:
    from src.storage.vector import search_articles_semantic, add_article_embedding
"""

from src.storage.sqlite import (
    get_db,
    init_db,
    store_article,
    store_article_async,
    get_db_path,
    store_embedding,
    get_article_embedding,
    feed_exists,
    add_feed,
    list_feeds,
    get_feed,
    remove_feed,
    list_articles,
    get_article,
    get_article_detail,
    search_articles,
    ensure_crawled_feed,
    get_all_embeddings,
    get_articles_without_embeddings,
    get_article_id_by_url,
    get_articles_by_urls,
)
