"""ChromaDB vector storage for semantic search.

Provides ChromaDB PersistentClient singleton and collection management
for article embeddings using SentenceTransformer.
"""

from __future__ import annotations

import chromadb
from chromadb import PersistentClient
from chromadb.config import Settings
import platformdirs
from sentence_transformers import SentenceTransformer
import threading

# Module-level singleton client
_chroma_client: PersistentClient | None = None
_embedding_function: SentenceTransformer | None = None
_chroma_lock = threading.Lock()


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
    Should be called during CLI initialization before any embedding
    operations to avoid delays on first use.
    """
    SentenceTransformer("all-MiniLM-L6-v2")


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
        metadata={"description": "Article embeddings for semantic search"},
    )


def add_article_embedding(article_id: str, title: str, content: str, url: str) -> None:
    """Add an article embedding to ChromaDB.

    Args:
        article_id: Unique article identifier (used as ChromaDB id)
        title: Article title (stored as metadata)
        content: Article content text (used for embedding, or fallback text)
        url: Article URL (stored as metadata)
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
            emb = embedding_fn.encode([embedding_text], convert_to_numpy=True)[0]
        except Exception as e:
            logger.error("Encoding failed for %s: text_len=%d, error=%s", article_id, len(embedding_text), e)
            raise
        embedding_vector = emb.tolist()

        metadata = {"title": title, "url": url}
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
