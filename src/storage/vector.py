"""ChromaDB vector storage for semantic search.

Provides ChromaDB PersistentClient singleton and collection management
for article embeddings using SentenceTransformer.
"""

from __future__ import annotations

# Prevent sentence-transformers from making network calls to huggingface.co
# Model is cached locally - no need to verify with remote server
import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import chromadb
from chromadb import PersistentClient
from chromadb.config import Settings
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import platformdirs
from sentence_transformers import SentenceTransformer
import threading

# Module-level singleton client
_chroma_client: PersistentClient | None = None
_embedding_function: SentenceTransformer | None = None
_chroma_lock = threading.Lock()


def _pub_date_to_timestamp(pub_date: str | int | None) -> int | None:
    """Convert pub_date to unix timestamp for ChromaDB storage/query.

    Handles RFC 2822 dates from RSS feeds (e.g., 'Thu, 26 Mar 2026 10:30:00 +0000')
    and ISO format dates (e.g., '2026-03-26', '2026-03-26T10:30:00+00:00').
    Also handles INTEGER unix timestamps from SQLite directly.

    Args:
        pub_date: Publication date as string, int timestamp, or None.

    Returns:
        Unix timestamp (seconds since epoch) or None if parsing fails.
    """
    if pub_date is None:
        return None
    # Handle INTEGER unix timestamp from SQLite
    if isinstance(pub_date, int):
        return pub_date
    if not pub_date:
        return None

    # Try parsing as RFC 2822 (RSS feed format)
    try:
        dt = parsedate_to_datetime(pub_date)
        return int(dt.timestamp())
    except Exception:
        pass

    # Try parsing as ISO format
    try:
        dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        pass

    return None


def _get_chroma_client() -> PersistentClient:
    """Get or create the ChromaDB PersistentClient singleton.

    Uses platformdirs to determine the storage directory:
    ~/.local/share/rss-reader/chroma/

    Returns:
        PersistentClient: The ChromaDB client instance.
    """
    global _chroma_client
    if _chroma_client is not None:
        return _chroma_client

    chroma_dir = platformdirs.user_data_dir(appname="rss-reader") + "/chroma"
    _chroma_client = PersistentClient(
        path=chroma_dir,
        settings=Settings(anonymized_telemetry=False),
    )
    return _chroma_client


def get_embedding_function() -> SentenceTransformer:
    """Get the SentenceTransformer embedding function.

    Uses 'all-MiniLM-L6-v2' model which produces 384-dimensional vectors
    with normalize_embeddings=True for cosine similarity.

    Uses CPU device to avoid MPS concurrency issues in async contexts.

    Returns:
        SentenceTransformer: The embedding function instance.
    """
    global _embedding_function
    if _embedding_function is None:
        _embedding_function = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    return _embedding_function


def preload_embedding_model() -> None:
    """Pre-download and cache the embedding model at CLI startup (D-04).

    Downloads the 'all-MiniLM-L6-v2' model if not already cached.
    Errors are logged but not raised — the model will be downloaded
    on first use if preload fails.
    """
    import logging
    logger = logging.getLogger(__name__)
    try:
        SentenceTransformer("all-MiniLM-L6-v2")
    except Exception as e:
        logger.warning("Embedding model preload failed: %s. Will download on first semantic search.", e)


def get_chroma_collection():
    """Get or create the 'articles' ChromaDB collection.

    The collection stores article embeddings with metadata:
    - article_id: Unique article identifier
    - content: Full article content
    - title: Article title
    - url: Article URL

    Returns:
        Collection: The ChromaDB collection for articles.
    """
    client = _get_chroma_client()
    return client.get_or_create_collection(
        name="articles",
        metadata={"description": "Article embeddings for semantic search", "hnsw:space": "cosine"},
    )


def add_article_embedding(article_id: str, title: str, content: str, url: str, pub_date: str | None = None) -> None:
    """Add an article embedding to ChromaDB.

    Args:
        article_id: Unique article identifier (used as ChromaDB id)
        title: Article title (stored as metadata)
        content: Article content text (used for embedding, or fallback text)
        url: Article URL (stored as metadata)
        pub_date: Publication date (stored as metadata for filtering)
    """
    import logging
    logger = logging.getLogger(__name__)

    # Serialize all encoding + ChromaDB operations to avoid concurrency issues
    with _chroma_lock:
        collection = get_chroma_collection()

        # Determine embedding text
        if content and len(content) >= 50:
            embedding_text = content
        else:
            # Short content - supplement with title
            embedding_text = f"{title} {content}".strip()

        if not embedding_text:
            logger.warning("Skipping embedding for article %s: no useful text", article_id)
            return

        # Manually encode text since we're not using ChromaDB's embedding_function
        # (sentence_transformers 2.7.0 + ChromaDB 1.5.5 have API incompatibility)
        embedding_fn = get_embedding_function()
        try:
            emb = embedding_fn.encode([embedding_text], convert_to_numpy=True, normalize_embeddings=True)[0]
        except Exception as e:
            logger.error("Encoding failed for %s: text_len=%d, error=%s", article_id, len(embedding_text), e)
            raise
        embedding_vector = emb.tolist()

        metadata = {"title": title, "url": url, "pub_date": _pub_date_to_timestamp(pub_date)}
        try:
            collection.add(
                ids=[article_id],
                documents=[embedding_text],
                embeddings=[embedding_vector],
                metadatas=[metadata],
            )
        except Exception as e:
            logger.error("ChromaDB add failed for %s: error=%s", article_id, e)
            raise


def add_article_embeddings(articles: list[dict]) -> None:
    """Batch add article embeddings to ChromaDB.

    Args:
        articles: List of article dicts with keys: article_id, title, content, url, pub_date.
    """
    import logging
    logger = logging.getLogger(__name__)

    if not articles:
        return

    # Prepare embedding texts and metadata
    embedding_texts = []
    ids = []
    metadatas = []

    for article in articles:
        article_id = article["article_id"]
        title = article.get("title") or ""
        content = article.get("content") or ""
        url = article.get("url") or ""
        pub_date = article.get("pub_date")

        if content and len(content) >= 50:
            embedding_text = content
        else:
            embedding_text = f"{title} {content}".strip()

        if not embedding_text:
            logger.warning("Skipping embedding for article %s: no useful text", article_id)
            continue

        embedding_texts.append(embedding_text)
        ids.append(article_id)
        metadatas.append({"title": title, "url": url, "pub_date": _pub_date_to_timestamp(pub_date)})

    if not embedding_texts:
        return

    # Serialize all encoding + ChromaDB operations to avoid concurrency issues
    with _chroma_lock:
        collection = get_chroma_collection()
        embedding_fn = get_embedding_function()

        try:
            emb = embedding_fn.encode(embedding_texts, convert_to_numpy=True, normalize_embeddings=True)
        except Exception as e:
            logger.error("Batch encoding failed for %d articles: error=%s", len(embedding_texts), e)
            raise

        embedding_vectors = emb.tolist()

        try:
            collection.add(
                ids=ids,
                documents=embedding_texts,
                embeddings=embedding_vectors,
                metadatas=metadatas,
            )
        except Exception as e:
            logger.error("ChromaDB batch add failed: error=%s", e)
            raise


def _parse_date_to_timestamp(date_str: str) -> int:
    """Convert YYYY-MM-DD date string to unix timestamp.

    Args:
        date_str: Date string in YYYY-MM-DD format.

    Returns:
        Unix timestamp (seconds since epoch).
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return int(dt.timestamp())


def search_articles_semantic(query_text: str, limit: int = 10, since: str | None = None, until: str | None = None, on: list[str] | None = None) -> list[ArticleListItem]:
    """Search articles by semantic similarity using ChromaDB.

    Args:
        query_text: Natural language query to search for
        limit: Maximum number of results to return
        since: Optional start date (inclusive), format YYYY-MM-DD.
        until: Optional end date (inclusive), format YYYY-MM-DD.
        on: Optional list of specific dates to match.

    Returns:
        List of ArticleListItem with keys: id, feed_id, feed_name, title, link, guid, pub_date, score
    """
    from src.application.articles import ArticleListItem

    import logging
    logger = logging.getLogger(__name__)

    # Build ChromaDB where clause for date filtering
    # ChromaDB $gte/$lte operators require numeric values (unix timestamps)
    where_conditions = []
    if since:
        where_conditions.append(("pub_date", {"$gte": _parse_date_to_timestamp(since)}))
    if until:
        where_conditions.append(("pub_date", {"$lte": _parse_date_to_timestamp(until)}))
    if on:
        where_conditions.append(("pub_date", {"$in": [_parse_date_to_timestamp(d) for d in on]}))
    where_clause = None
    if len(where_conditions) == 1:
        where_clause = {where_conditions[0][0]: where_conditions[0][1]}
    elif len(where_conditions) > 1:
        # Combine with $and
        where_clause = {"$and": [{k: v} for k, v in where_conditions]}

    with _chroma_lock:
        collection = get_chroma_collection()
        embedding_fn = get_embedding_function()
        try:
            emb = embedding_fn.encode([query_text], convert_to_numpy=True, normalize_embeddings=True)[0]
        except Exception as e:
            logger.error("Encoding failed for semantic query: %s", e)
            raise
        embedding_vector = emb.tolist()

        try:
            results = collection.query(
                query_embeddings=[embedding_vector],
                n_results=limit,
                where=where_clause,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.warning("ChromaDB error in search_articles_semantic: %s", e)
            return []

    # Flatten and map results
    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    # Batch lookup full article data by SQLite nanoid - single query instead of N queries
    valid_ids = [aid for aid in ids if aid]
    id_to_article = {}
    if valid_ids:
        from src.storage.sqlite import get_articles_by_ids, get_feeds_by_ids
        articles_data = get_articles_by_ids(valid_ids)
        id_to_article = {a["id"]: a for a in articles_data}

        # Batch fetch all unique feeds to avoid N DB calls in loop
        feed_ids = list({a.get("feed_id") for a in articles_data if a.get("feed_id")})
        id_to_feed = {f.id: f for f in get_feeds_by_ids(feed_ids).values()} if feed_ids else {}
    else:
        id_to_feed = {}

    # Build ranked results with multi-factor scoring
    ranked_results = []
    for i, article_id in enumerate(ids):
        if not article_id:
            continue

        article_info = id_to_article.get(article_id, {})
        distance = distances[i] if i < len(distances) else None
        sqlite_id = article_info.get("id")

        # Skip articles not found in SQLite (stale ChromaDB entries)
        if not sqlite_id:
            continue

        # Calculate cosine similarity from cosine distance
        # hnsw:space=cosine means distance = 1 - cosine_similarity (range 0-2)
        cos_sim = max(0.0, 1.0 - distance / 2.0) if distance is not None else 0.5

        # Calculate freshness score (D-07: freshness signal removed from storage layer)
        pub_date = article_info.get("pub_date")
        pub_ts = _pub_date_to_timestamp(pub_date)  # Returns int or None
        freshness = 0.0
        if pub_ts:
            pub_dt = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
            days_ago = (datetime.now(timezone.utc) - pub_dt).days
            freshness = max(0.0, 1.0 - days_ago / 30)

        ranked_results.append({
            "sqlite_id": sqlite_id,
            "article_id": article_id,
            "feed_id": feed_id or "",
            "feed_name": article_info.get("feed_name") or "",
            "title": metadatas[i].get("title") if metadatas[i] else None,
            "url": metadatas[i].get("url") if metadatas[i] else None,
            "pub_date": pub_date,
            "cos_sim": cos_sim,
        })

    # ChromaDB returns results ordered by similarity - no additional sort needed
    ranked_results = ranked_results[:limit]

    # Convert to ArticleListItem
    result_items = []
    for r in ranked_results:
        result_items.append(ArticleListItem(
            id=r["sqlite_id"] or r["article_id"] or "",
            feed_id=r["feed_id"] or "",
            feed_name=r["feed_name"] or "",
            title=r.get("title"),
            link=r.get("url"),
            guid=r["sqlite_id"] or r["article_id"] or "",
            pub_date=r.get("pub_date"),
            description=None,
            vec_sim=cos_sim,
        ))
    return result_items


def get_related_articles(article_id: str, limit: int = 5) -> list[dict]:
    """Find articles semantically similar to a given article.

    Args:
        article_id: The SQLite article ID to find related articles for
        limit: Maximum number of related articles to return

    Returns:
        List of dicts with keys: article_id, title, url, distance, document
    """
    import logging
    logger = logging.getLogger(__name__)

    # article_id is the SQLite nanoid, which is also the ChromaDB ID
    chroma_id = article_id

    with _chroma_lock:
        collection = get_chroma_collection()
        # First get the embedding vector for the source article
        # First get the embedding vector for the source article
        try:
            existing = collection.get(ids=[chroma_id], include=["embeddings"])
        except Exception as e:
            logger.warning("ChromaDB error in get_related_articles: %s", e)
            return []
        embeddings = existing.get("embeddings", [[]])
        if embeddings is None or len(embeddings) == 0 or len(embeddings[0]) == 0:
            logger.info("Article %s has no embedding (fetched before v1.8)", article_id)
            return []
        source_embedding = embeddings[0]

        # Now query for similar articles using the source embedding
        try:
            results = collection.query(
                query_embeddings=[source_embedding],
                n_results=limit + 1,  # +1 because the query article itself is included
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.warning("ChromaDB error in get_related_articles: %s", e)
            return []

    # Flatten and map results, excluding the query article itself
    articles = []
    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for i, related_id in enumerate(ids):
        if related_id == chroma_id:
            continue  # Skip the query article itself
        articles.append({
            "article_id": related_id,
            "title": metadatas[i].get("title") if metadatas[i] else None,
            "url": metadatas[i].get("url") if metadatas[i] else None,
            "distance": distances[i] if i < len(distances) else None,
            "document": documents[i] if i < len(documents) else None,
        })
        if len(articles) >= limit:
            break
    return articles
