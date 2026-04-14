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

import logging
import threading
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

import platformdirs
import psutil

_chromadb = None


def _get_chromadb():
    """Lazily import chromadb, raising RuntimeError on failure."""
    global _chromadb
    if _chromadb is None:
        try:
            import chromadb as _chromadb
        except ImportError as e:
            raise RuntimeError(
                "chromadb is required for semantic search. "
                "Install with: pip install feedship[ml]"
            ) from e
    return _chromadb


if TYPE_CHECKING:
    from chromadb import PersistentClient
    from sentence_transformers import SentenceTransformer

    from src.application.articles import ArticleListItem

# Module-level singleton client
_chroma_client: PersistentClient | None = None
_embedding_function: SentenceTransformer | None = None

# Per-collection locks for write serialization
_col_locks: dict[str, threading.Lock] = {}

# Memory guard threshold
MEMORY_THRESHOLD_PERCENT = 80  # Skip embeddings when memory usage exceeds 80%

logger = logging.getLogger(__name__)


def _check_memory_guard() -> bool:
    """Check if memory usage is below threshold for embedding generation.

    Returns:
        True if memory is OK (below threshold), False if should skip.
    """
    memory = psutil.virtual_memory()
    available_gb = memory.available / (1024**3)
    threshold_gb = 0.10 * memory.total / (1024**3)  # 10% of total
    min_gb = 1.0  # Minimum 1GB available
    if available_gb < threshold_gb and available_gb < min_gb:
        logger.warning(
            "Memory available: %.1f GB (threshold: %.1f GB or 10%% total), skipping embedding generation",
            available_gb,
            min_gb,
        )
        return False
    return True


def _published_at_to_timestamp(published_at: str | int | float | None) -> int | None:
    """Convert published_at to unix timestamp for ChromaDB storage/query.

    Handles RFC 2822 dates from RSS feeds (e.g., 'Thu, 26 Mar 2026 10:30:00 +0000')
    and ISO format dates (e.g., '2026-03-26', '2026-03-26T10:30:00+00:00').
    Also handles INTEGER unix timestamps from SQLite directly.
    Handles datetime objects directly (from feedparser raw values).
    Handles float unix timestamps.

    Args:
        published_at: Publication date as string, int/float timestamp, datetime object, or None.

    Returns:
        Unix timestamp (seconds since epoch) or None if parsing fails.
    """
    if published_at is None:
        return None

    # Handle datetime objects directly (feedparser sometimes returns datetime)
    if isinstance(published_at, datetime):
        return int(published_at.timestamp())

    # Handle INTEGER or FLOAT unix timestamp from SQLite
    if isinstance(published_at, int | float):
        return int(published_at)

    if not published_at:
        return None

    # Try parsing as RFC 2822 (RSS feed format)
    try:
        dt = parsedate_to_datetime(published_at)
        return int(dt.timestamp())
    except Exception:
        pass

    # Try parsing as ISO format
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        pass

    return None


def _get_chroma_client() -> PersistentClient:
    """Get or create the ChromaDB PersistentClient singleton.

    Uses platformdirs to determine the storage directory:
    ~/.local/share/feedship/chroma/

    Returns:
        PersistentClient: The ChromaDB client instance.
    """
    global _chroma_client
    if _chroma_client is not None:
        return _chroma_client

    chroma_dir = platformdirs.user_data_dir(appname="feedship") + "/chroma"
    _chroma_client = _get_chromadb().PersistentClient(
        path=chroma_dir,
        settings=_get_chromadb().config.Settings(anonymized_telemetry=False),
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
    from sentence_transformers import SentenceTransformer

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
        logger.warning(
            "Embedding model preload failed: %s. Will download on first semantic search.",
            e,
        )


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
        metadata={
            "description": "Article embeddings for semantic search",
            "hnsw:space": "cosine",
        },
    )


def add_article_embedding(
    article_id: str, title: str, content: str, url: str, published_at: str | None = None
) -> None:
    """Add an article embedding to ChromaDB.

    Args:
        article_id: Unique article identifier (used as ChromaDB id)
        title: Article title (stored as metadata)
        content: Article content text (used for embedding, or fallback text)
        url: Article URL (stored as metadata)
        published_at: Publication date (stored as metadata for filtering)
    """
    import logging

    logger = logging.getLogger(__name__)

    # Memory guard - skip embedding generation if memory is high
    if not _check_memory_guard():
        return

    # Serialize ChromaDB operations per collection to avoid concurrency issues
    col_lock = _col_locks.setdefault("articles", threading.Lock())
    with col_lock:
        collection = get_chroma_collection()

        # Determine embedding text
        if content and len(content) >= 50:
            embedding_text = content
        else:
            # Short content - supplement with title
            embedding_text = f"{title} {content}".strip()

        if not embedding_text:
            logger.warning(
                "Skipping embedding for article %s: no useful text", article_id
            )
            return

        # Manually encode text since we're not using ChromaDB's embedding_function
        # (sentence_transformers 2.7.0 + ChromaDB 1.5.5 have API incompatibility)
        embedding_fn = get_embedding_function()
        try:
            emb = embedding_fn.encode(
                [embedding_text], convert_to_numpy=True, normalize_embeddings=True
            )[0]
        except Exception as e:
            logger.error(
                "Encoding failed for %s: text_len=%d, error=%s",
                article_id,
                len(embedding_text),
                e,
            )
            raise
        embedding_vector = emb.tolist()

        metadata = {
            "title": title,
            "url": url,
        }
        ts = _published_at_to_timestamp(published_at)
        if ts is not None:
            metadata["published_at"] = ts
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
        articles: List of article dicts with keys: article_id, title, content, url, published_at.
    """
    import logging

    logger = logging.getLogger(__name__)

    if not articles:
        return

    # Memory guard - skip embedding generation if memory is high
    if not _check_memory_guard():
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
        published_at = article.get("published_at")
        author = article.get("author") or ""
        tags = article.get("tags") or ""
        category = article.get("category") or ""

        # Ensure title and url are strings (defensive against unexpected types)
        title = str(title) if title else ""
        url = str(url) if url else ""

        # Compose rich embedding text from all available fields
        parts = [title, author, tags, category, content]
        embedding_text = " ".join(p for p in parts if p)

        if not embedding_text:
            logger.warning(
                "Skipping embedding for article %s: no useful text", article_id
            )
            continue

        embedding_texts.append(embedding_text)
        ids.append(article_id)
        meta = {
            "title": title,
            "url": url,
        }
        ts = _published_at_to_timestamp(published_at)
        if ts is not None:
            meta["published_at"] = ts
        metadatas.append(meta)

    if not embedding_texts:
        return

    import time

    embedding_fn = get_embedding_function()
    t0 = time.monotonic()
    total_chars = sum(len(t) for t in embedding_texts)
    try:
        emb = embedding_fn.encode(
            embedding_texts, convert_to_numpy=True, normalize_embeddings=True
        )
        encode_time = time.monotonic() - t0
        logger.debug(
            "Embedding encode: %d articles, %d chars, %.3fs (%.0f chars/s)",
            len(embedding_texts),
            total_chars,
            encode_time,
            total_chars / encode_time if encode_time > 0 else 0,
        )
    except Exception as e:
        logger.error(
            "Batch encoding failed for %d articles: error=%s",
            len(embedding_texts),
            e,
        )
        raise
    embedding_vectors = emb.tolist()

    # Serialize ChromaDB write per collection (lock acquired after encoding to avoid
    # holding the lock during slow CPU-bound encoding, reducing lock contention)
    col_lock = _col_locks.setdefault("articles", threading.Lock())
    with col_lock:
        collection = get_chroma_collection()
        t1 = time.monotonic()
        try:
            collection.add(
                ids=ids,
                documents=embedding_texts,
                embeddings=embedding_vectors,
                metadatas=metadatas,
            )
            add_time = time.monotonic() - t1
            logger.debug(
                "ChromaDB add: %d articles, %.3fs",
                len(ids),
                add_time,
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


def search_articles_semantic(
    query_text: str,
    limit: int = 10,
    since: str | None = None,
    until: str | None = None,
    on: list[str] | None = None,
    groups: list[str] | None = None,
    tag: str | None = None,
) -> list[ArticleListItem]:
    """Search articles by semantic similarity using ChromaDB.

    Args:
        query_text: Natural language query to search for
        limit: Maximum number of results to return
        since: Optional start date (inclusive), format YYYY-MM-DD.
        until: Optional end date (inclusive), format YYYY-MM-DD.
        on: Optional list of specific dates to match.
        groups: Optional list of feed groups to filter by (OR semantics).
        tag: Optional tag name to filter by (articles from feeds with this tag).

    Returns:
        List of ArticleListItem with keys: id, feed_id, feed_name, title, link, guid, published_at, score
    """
    import logging

    from src.application.articles import ArticleListItem

    logger = logging.getLogger(__name__)

    # Build ChromaDB where clause for date filtering
    # ChromaDB $gte/$lte operators require numeric values (unix timestamps)
    where_conditions = []
    if since:
        where_conditions.append(
            ("published_at", {"$gte": _parse_date_to_timestamp(since)})
        )
    if until:
        where_conditions.append(
            ("published_at", {"$lte": _parse_date_to_timestamp(until)})
        )
    if on:
        where_conditions.append(
            ("published_at", {"$in": [_parse_date_to_timestamp(d) for d in on]})
        )
    where_clause = None
    if len(where_conditions) == 1:
        where_clause = {where_conditions[0][0]: where_conditions[0][1]}
    elif len(where_conditions) > 1:
        # Combine with $and
        where_clause = {"$and": [{k: v} for k, v in where_conditions]}

    embedding_fn = get_embedding_function()
    try:
        emb = embedding_fn.encode(
            [query_text], convert_to_numpy=True, normalize_embeddings=True
        )[0]
    except Exception as e:
        logger.error("Encoding failed for semantic query: %s", e)
        raise
    embedding_vector = emb.tolist()

    # ChromaDB is thread-safe for reads; no lock needed
    collection = get_chroma_collection()

    # Fetch more results when groups filter is active to have enough candidates after filtering
    fetch_limit = limit * 3 if groups else limit
    try:
        results = collection.query(
            query_embeddings=[embedding_vector],
            n_results=fetch_limit,
            where=where_clause,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        logger.warning("ChromaDB error in search_articles_semantic: %s", e)
        return []

    # Flatten and map results
    ids = results.get("ids", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    # Batch lookup full article data by SQLite nanoid - single query instead of N queries
    valid_ids = [aid for aid in ids if aid]
    id_to_article = {}
    if valid_ids:
        from src.storage.sqlite import get_articles_by_ids

        articles_data = get_articles_by_ids(valid_ids)
        id_to_article = {a["id"]: a for a in articles_data}

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

        published_at = article_info.get("published_at")

        ranked_results.append(
            {
                "sqlite_id": sqlite_id,
                "article_id": article_id,
                "feed_id": article_info.get("feed_id") or "",
                "feed_name": article_info.get("feed_name") or "",
                "feed_group": article_info.get("feed_group"),
                "title": metadatas[i].get("title") if metadatas[i] else None,
                "url": metadatas[i].get("url") if metadatas[i] else None,
                "published_at": published_at,
                "cos_sim": cos_sim,
            }
        )

    # ChromaDB returns results ordered by similarity - no additional sort needed
    # Post-fetch group filtering (ChromaDB doesn't store group metadata)
    if groups:
        ranked_results = [r for r in ranked_results if r.get("feed_group") in groups]

    # Post-fetch tag filtering
    if tag:
        # Get feed IDs that have this tag
        from src.storage.sqlite.conn import get_db

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT ft.feed_id
                FROM feed_tags ft
                JOIN tags t ON ft.tag_id = t.id
                WHERE t.name = ?
                """,
                (tag,),
            )
            tagged_feed_ids = {row[0] for row in cursor.fetchall()}
        ranked_results = [
            r for r in ranked_results if r.get("feed_id") in tagged_feed_ids
        ]
    ranked_results = ranked_results[:limit]

    # Convert to ArticleListItem
    result_items = []
    for r in ranked_results:
        result_items.append(
            ArticleListItem(
                id=r["sqlite_id"] or r["article_id"] or "",
                feed_id=r["feed_id"] or "",
                feed_name=r["feed_name"] or "",
                title=r.get("title"),
                link=r.get("url"),
                guid=r["sqlite_id"] or r["article_id"] or "",
                published_at=r.get("published_at"),
                description=None,
                vec_sim=cos_sim,
            )
        )
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

    # ChromaDB is thread-safe for reads; no lock needed
    collection = get_chroma_collection()
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
        articles.append(
            {
                "article_id": related_id,
                "title": metadatas[i].get("title") if metadatas[i] else None,
                "url": metadatas[i].get("url") if metadatas[i] else None,
                "distance": distances[i] if i < len(distances) else None,
                "document": documents[i] if i < len(documents) else None,
            }
        )
        if len(articles) >= limit:
            break
    return articles


# ---------------------------------------------------------------------------
# LLM collections: article summaries and keywords
# ---------------------------------------------------------------------------


def get_llm_summary_collection():
    """Get or create the 'article_summaries' ChromaDB collection.

    Stores LLM-generated summaries with embeddings for semantic search.

    Returns:
        Collection: ChromaDB collection for article summaries.
    """
    client = _get_chroma_client()
    return client.get_or_create_collection(
        name="article_summaries",
        metadata={
            "description": "LLM article summaries for semantic search",
            "hnsw:space": "cosine",
        },
    )


def get_llm_keywords_collection():
    """Get or create the 'article_keywords' ChromaDB collection.

    Stores LLM-extracted keywords with embeddings for semantic keyword search.

    Returns:
        Collection: ChromaDB collection for article keywords.
    """
    client = _get_chroma_client()
    return client.get_or_create_collection(
        name="article_keywords",
        metadata={
            "description": "LLM article keywords for semantic search",
            "hnsw:space": "cosine",
        },
    )


def upsert_article_summary(
    article_id: str,
    summary: str,
    title: str | None = None,
    url: str | None = None,
    published_at: str | None = None,
) -> None:
    """Store LLM summary and its embedding in ChromaDB.

    Args:
        article_id: Unique article identifier (SQLite nanoid).
        summary: LLM-generated summary text.
        title: Article title (metadata).
        url: Article URL (metadata).
        published_at: Publication date (metadata).
    """
    import logging

    logger = logging.getLogger(__name__)

    if not summary:
        return

    col_lock = _col_locks.setdefault("article_summaries", threading.Lock())

    embedding_fn = get_embedding_function()
    try:
        emb = embedding_fn.encode(
            [summary], convert_to_numpy=True, normalize_embeddings=True
        )[0]
    except Exception as e:
        logger.error("Encoding failed for summary %s: %s", article_id, e)
        raise
    embedding_vector = emb.tolist()

    metadata = {
        "title": title or "",
        "url": url or "",
    }
    ts = _published_at_to_timestamp(published_at)
    if ts is not None:
        metadata["published_at"] = ts
    with col_lock:
        collection = get_llm_summary_collection()
        try:
            collection.upsert(
                ids=[article_id],
                documents=[summary],
                embeddings=[embedding_vector],
                metadatas=[metadata],
            )
        except Exception as e:
            logger.error("ChromaDB upsert failed for summary %s: %s", article_id, e)
            raise


def upsert_article_keywords(
    article_id: str,
    keywords: list[str],
    title: str | None = None,
    url: str | None = None,
    published_at: str | None = None,
) -> None:
    """Store LLM-extracted keywords and their embedding in ChromaDB.

    Keywords are joined into a single string for embedding.

    Args:
        article_id: Unique article identifier (SQLite nanoid).
        keywords: List of extracted keyword strings.
        title: Article title (metadata).
        url: Article URL (metadata).
        published_at: Publication date (metadata).
    """
    import logging

    logger = logging.getLogger(__name__)

    if not keywords:
        return

    keywords_text = " | ".join(keywords)

    col_lock = _col_locks.setdefault("article_keywords", threading.Lock())

    embedding_fn = get_embedding_function()
    try:
        emb = embedding_fn.encode(
            [keywords_text], convert_to_numpy=True, normalize_embeddings=True
        )[0]
    except Exception as e:
        logger.error("Encoding failed for keywords %s: %s", article_id, e)
        raise
    embedding_vector = emb.tolist()

    metadata = {
        "title": title or "",
        "url": url or "",
        "keywords": keywords_text,
    }
    ts = _published_at_to_timestamp(published_at)
    if ts is not None:
        metadata["published_at"] = ts
    with col_lock:
        collection = get_llm_keywords_collection()
        try:
            collection.upsert(
                ids=[article_id],
                documents=[keywords_text],
                embeddings=[embedding_vector],
                metadatas=[metadata],
            )
        except Exception as e:
            logger.error("ChromaDB upsert failed for keywords %s: %s", article_id, e)
            raise


def search_llm_summaries(
    query_text: str,
    limit: int = 10,
    since: str | None = None,
    until: str | None = None,
) -> list[dict]:
    """Semantic search over LLM-generated summaries.

    Args:
        query_text: Natural language query.
        limit: Maximum number of results.
        since: Optional start date (YYYY-MM-DD).
        until: Optional end date (YYYY-MM-DD).

    Returns:
        List of dicts with keys: article_id, summary, title, url, distance.
    """
    import logging

    logger = logging.getLogger(__name__)

    where_conditions = []
    if since:
        where_conditions.append(
            ("published_at", {"$gte": _parse_date_to_timestamp(since)})
        )
    if until:
        where_conditions.append(
            ("published_at", {"$lte": _parse_date_to_timestamp(until)})
        )
    where_clause = None
    if len(where_conditions) == 1:
        where_clause = {where_conditions[0][0]: where_conditions[0][1]}
    elif len(where_conditions) > 1:
        where_clause = {"$and": [{k: v} for k, v in where_conditions]}

    embedding_fn = get_embedding_function()

    try:
        emb = embedding_fn.encode(
            [query_text], convert_to_numpy=True, normalize_embeddings=True
        )[0]
    except Exception as e:
        logger.error("Encoding failed for summary query: %s", e)
        raise
    embedding_vector = emb.tolist()

    # ChromaDB is thread-safe for reads; no lock needed
    collection = get_llm_summary_collection()
    try:
        results = collection.query(
            query_embeddings=[embedding_vector],
            n_results=limit,
            where=where_clause,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        logger.warning("ChromaDB error in search_llm_summaries: %s", e)
        return []

    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    output = []
    for i, article_id in enumerate(ids):
        if not article_id:
            continue
        distance = distances[i] if i < len(distances) else None
        cos_sim = max(0.0, 1.0 - distance / 2.0) if distance is not None else 0.5
        output.append(
            {
                "article_id": article_id,
                "summary": documents[i] if i < len(documents) else None,
                "title": metadatas[i].get("title") if metadatas[i] else None,
                "url": metadatas[i].get("url") if metadatas[i] else None,
                "cos_sim": cos_sim,
            }
        )
    return output


def search_llm_keywords(
    query_text: str,
    limit: int = 10,
    since: str | None = None,
    until: str | None = None,
) -> list[dict]:
    """Semantic search over LLM-extracted keywords.

    Args:
        query_text: Natural language query.
        limit: Maximum number of results.
        since: Optional start date (YYYY-MM-DD).
        until: Optional end date (YYYY-MM-DD).

    Returns:
        List of dicts with keys: article_id, keywords, title, url, distance.
    """
    import logging

    logger = logging.getLogger(__name__)

    where_conditions = []
    if since:
        where_conditions.append(
            ("published_at", {"$gte": _parse_date_to_timestamp(since)})
        )
    if until:
        where_conditions.append(
            ("published_at", {"$lte": _parse_date_to_timestamp(until)})
        )
    where_clause = None
    if len(where_conditions) == 1:
        where_clause = {where_conditions[0][0]: where_conditions[0][1]}
    elif len(where_conditions) > 1:
        where_clause = {"$and": [{k: v} for k, v in where_conditions]}

    embedding_fn = get_embedding_function()

    try:
        emb = embedding_fn.encode(
            [query_text], convert_to_numpy=True, normalize_embeddings=True
        )[0]
    except Exception as e:
        logger.error("Encoding failed for keyword query: %s", e)
        raise
    embedding_vector = emb.tolist()

    # ChromaDB is thread-safe for reads; no lock needed
    collection = get_llm_keywords_collection()
    try:
        results = collection.query(
            query_embeddings=[embedding_vector],
            n_results=limit,
            where=where_clause,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        logger.warning("ChromaDB error in search_llm_keywords: %s", e)
        return []

    ids = results.get("ids", [[]])[0]
    _documents = results.get("documents", [[]])[0]  # intentionally unused
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    output = []
    for i, article_id in enumerate(ids):
        if not article_id:
            continue
        distance = distances[i] if i < len(distances) else None
        cos_sim = max(0.0, 1.0 - distance / 2.0) if distance is not None else 0.5
        output.append(
            {
                "article_id": article_id,
                "keywords": metadatas[i].get("keywords") if metadatas[i] else None,
                "title": metadatas[i].get("title") if metadatas[i] else None,
                "url": metadatas[i].get("url") if metadatas[i] else None,
                "cos_sim": cos_sim,
            }
        )
    return output
