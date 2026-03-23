"""AI-powered tagging using embeddings and clustering.

Uses sentence-transformers for embeddings and sklearn DBSCAN for clustering.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

import numpy as np
from sklearn.cluster import DBSCAN

from src.db import get_connection, add_tag, tag_article


def _load_vec_extension(conn: sqlite3.Connection) -> None:
    """Load sqlite-vec extension (D-11)."""
    conn.enable_load_extension(True)
    try:
        conn.load_extension("vec0")
    except sqlite3.OperationalError:
        # vec0 may not be available, clustering will use fallback
        pass


def _ensure_embeddings_table() -> None:
    """Create article_embeddings table if not exists."""
    conn = get_connection()
    try:
        _load_vec_extension(conn)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS article_embeddings (
                article_id TEXT PRIMARY KEY,
                embedding BLOB
            )
        """)
        conn.commit()
    finally:
        conn.close()


def generate_embedding(text: str, model: Optional[Any] = None) -> np.ndarray:
    """Generate embedding for text using sentence-transformers (D-10).

    Args:
        text: Text to encode (title + description).
        model: Pre-loaded model instance (optional, for reuse).

    Returns:
        384-dimensional numpy array (all-MiniLM-L6-v2).
    """
    if model is None:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')

    if not text or not text.strip():
        # Return zero vector for empty text
        return np.zeros(384)

    embedding = model.encode(text, normalize_embeddings=True)
    return embedding


def store_embedding(article_id: str, embedding: np.ndarray) -> None:
    """Store article embedding in sqlite-vec (D-11)."""
    _ensure_embeddings_table()
    conn = get_connection()
    try:
        _load_vec_extension(conn)
        cursor = conn.cursor()
        embedding_bytes = embedding.tobytes()
        cursor.execute("""
            INSERT OR REPLACE INTO article_embeddings (article_id, embedding)
            VALUES (?, ?)
        """, (article_id, embedding_bytes))
        conn.commit()
    finally:
        conn.close()


def get_article_embedding(article_id: str) -> Optional[np.ndarray]:
    """Retrieve stored embedding for an article."""
    conn = get_connection()
    try:
        _load_vec_extension(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT embedding FROM article_embeddings WHERE article_id = ?", (article_id,))
        row = cursor.fetchone()
        if row:
            return np.frombuffer(row["embedding"], dtype=np.float32)
        return None
    finally:
        conn.close()


def _get_article_by_id(article_id: str) -> Optional[Any]:
    """Get article by ID (imported at runtime to avoid circular imports)."""
    from src.articles import get_article
    return get_article(article_id)


def generate_embeddings_for_articles(article_ids: list[str], show_progress: bool = False) -> dict[str, np.ndarray]:
    """Generate and store embeddings for a list of articles.

    Returns dict of {article_id: embedding}.
    """
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('all-MiniLM-L6-v2')

    results = {}
    for i, article_id in enumerate(article_ids):
        article = _get_article_by_id(article_id)
        if not article:
            continue
        text = f"{article.title or ''} {article.description or ''}"
        embedding = generate_embedding(text, model)
        store_embedding(article_id, embedding)
        results[article_id] = embedding
        if show_progress and (i + 1) % 10 == 0:
            print(f"Generated {i + 1}/{len(article_ids)} embeddings")
    return results


def discover_clusters(
    eps: float = 0.3,
    min_samples: int = 3,
    metric: str = 'cosine'
) -> dict[int, list[str]]:
    """Run DBSCAN clustering on article embeddings (D-12).

    Args:
        eps: Maximum distance between samples in same cluster (default 0.3).
        min_samples: Minimum samples in cluster (default 3).
        metric: Distance metric (default 'cosine').

    Returns:
        Dict of {cluster_label: [article_ids]}. Label -1 is noise/outliers.
    """
    conn = get_connection()
    try:
        _load_vec_extension(conn)
        cursor = conn.cursor()

        # Get all embeddings
        cursor.execute("SELECT article_id, embedding FROM article_embeddings")
        rows = cursor.fetchall()

        if len(rows) < min_samples:
            # Not enough articles for clustering
            return {}

        article_ids = [row["article_id"] for row in rows]
        embeddings = np.array([np.frombuffer(row["embedding"], dtype=np.float32) for row in rows])

        # Run DBSCAN
        clustering = DBSCAN(eps=eps, min_samples=min_samples, metric=metric)
        labels = clustering.fit_predict(embeddings)

        # Build cluster map
        clusters: dict[int, list[str]] = {}
        for article_id, label in zip(article_ids, labels):
            clusters.setdefault(label, []).append(article_id)

        return clusters
    finally:
        conn.close()


def suggest_tag_name_from_articles(article_ids: list[str]) -> str:
    """Generate a tag name from cluster articles (D-13).

    Uses most common significant word(s) from titles as suggested tag name.
    """
    if not article_ids:
        return ""

    # Get titles
    titles: list[str] = []
    for article_id in article_ids:
        article = _get_article_by_id(article_id)
        if article and article.title:
            titles.append(article.title)

    if not titles:
        return "Cluster"

    # Simple keyword extraction: split titles, lowercase, filter short words
    words: dict[str, int] = {}
    stop_words = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or", "with", "by", "is", "are", "was", "were", "be", "been", "being", "from", "this", "that", "these", "those"}

    for title in titles:
        for word in title.lower().split():
            word = word.strip(".,!?()[]{}:;\"'")
            if len(word) > 3 and word not in stop_words:
                words[word] = words.get(word, 0) + 1

    if not words:
        return "Cluster"

    # Return most common word (capitalized)
    top_word = max(words.keys(), key=lambda w: words[w])
    return top_word.capitalize()


def run_auto_tagging(eps: float = 0.3, min_samples: int = 3, create_tags: bool = True) -> dict[str, list[str]]:
    """Run full auto-tagging pipeline: generate embeddings, cluster, create tags.

    Args:
        eps: DBSCAN eps parameter.
        min_samples: DBSCAN min_samples parameter.
        create_tags: If True, create tags and tag articles (D-13).

    Returns:
        Dict of {tag_name: [article_ids]} for discovered clusters.
    """
    # Step 1: Get all articles without embeddings
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.id FROM articles a
            LEFT JOIN article_embeddings ae ON a.id = ae.article_id
            WHERE ae.article_id IS NULL
        """)
        article_ids = [row["id"] for row in cursor.fetchall()]
    finally:
        conn.close()

    if article_ids:
        generate_embeddings_for_articles(article_ids)

    # Step 2: Run clustering
    clusters = discover_clusters(eps=eps, min_samples=min_samples)

    if create_tags:
        # Step 3: Create tags for non-noise clusters
        tag_map: dict[str, list[str]] = {}
        for label, cluster_article_ids in clusters.items():
            if label == -1:  # Skip noise
                continue
            tag_name = suggest_tag_name_from_articles(cluster_article_ids)
            # Create unique tag name if exists
            import uuid
            unique_suffix = str(uuid.uuid4())[:4]
            final_tag_name = f"{tag_name}-{unique_suffix}" if tag_name == "Cluster" else tag_name

            # Create tag and link articles
            tag = add_tag(final_tag_name)
            for article_id in cluster_article_ids:
                tag_article(article_id, final_tag_name)
            tag_map[final_tag_name] = cluster_article_ids
        return tag_map

    return {str(k): v for k, v in clusters.items() if k != -1}
