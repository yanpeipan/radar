"""AI-powered tagging using embeddings and clustering.

Uses sentence-transformers for embeddings (with TF-IDF fallback)
and sklearn DBSCAN for clustering.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer

from src.storage import add_tag, tag_article, store_embedding, get_article_embedding, get_all_embeddings, get_articles_without_embeddings

logger = logging.getLogger(__name__)

# Global embedder state: ("sentencetransformers" or "tfidf")
_EMBEDDER: str | None = None
_TFIDF_VECTORIZER: TfidfVectorizer | None = None
_EMBEDDING_DIM: int = 384
_MODEL: Any = None  # Shared sentence-transformers model instance


def _get_embedder() -> str:
    """Return the available embedder type: 'sentencetransformers' or 'tfidf'."""
    global _EMBEDDER
    if _EMBEDDER is None:
        try:
            from sentence_transformers import SentenceTransformer
            _ = SentenceTransformer("all-MiniLM-L6-v2")
            _EMBEDDER = "sentencetransformers"
        except ImportError:
            _EMBEDDER = "tfidf"
    return _EMBEDDER


def _get_model() -> Any:
    """Get or create the shared sentence-transformers model."""
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _MODEL


def generate_embedding(text: str) -> np.ndarray:
    """Generate embedding for text using sentence-transformers or TF-IDF fallback.

    Args:
        text: Text to encode (title + description).

    Returns:
        384-dimensional numpy array.
    """
    if _get_embedder() == "sentencetransformers":
        model = _get_model()
        if not text or not text.strip():
            return np.zeros(384)
        return model.encode(text, normalize_embeddings=True)

    # TF-IDF fallback
    if not text or not text.strip():
        return np.zeros(_EMBEDDING_DIM)

    global _TFIDF_VECTORIZER
    if _TFIDF_VECTORIZER is None:
        # Vectorizer must be fitted first via generate_embeddings_for_articles
        return np.zeros(_EMBEDDING_DIM)

    vec = _TFIDF_VECTORIZER.transform([text]).toarray()[0]
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.astype(np.float32)


def _get_article_by_id(article_id: str) -> Any:
    """Get article by ID (imported at runtime to avoid circular imports)."""
    from src.application.articles import get_article
    return get_article(article_id)


def generate_embeddings_for_articles(article_ids: list[str], show_progress: bool = False) -> dict[str, np.ndarray]:
    """Generate and store embeddings for a list of articles.

    Returns dict of {article_id: embedding}.
    """
    # Fit TF-IDF vectorizer on corpus first if using fallback
    if _get_embedder() == "tfidf":
        global _TFIDF_VECTORIZER
        articles = [_get_article_by_id(aid) for aid in article_ids]
        texts = [f"{a.title or ''} {a.description or ''}" for a in articles if a]
        if texts:
            _TFIDF_VECTORIZER = TfidfVectorizer(max_features=_EMBEDDING_DIM)
            _TFIDF_VECTORIZER.fit(texts)

    results = {}
    for i, article_id in enumerate(article_ids):
        article = _get_article_by_id(article_id)
        if not article:
            continue
        text = f"{article.title or ''} {article.description or ''}"
        embedding = generate_embedding(text)
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
    article_ids, embeddings = get_all_embeddings()

    if len(article_ids) < min_samples:
        # Not enough articles for clustering
        return {}

    # Run DBSCAN
    clustering = DBSCAN(eps=eps, min_samples=min_samples, metric=metric)
    labels = clustering.fit_predict(embeddings)

    # Build cluster map
    clusters: dict[int, list[str]] = {}
    for article_id, label in zip(article_ids, labels):
        clusters.setdefault(label, []).append(article_id)

    return clusters


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
    # Step 1: Get all articles without embeddings and generate them
    article_ids = get_articles_without_embeddings()
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
            # Create unique tag name to avoid collisions
            import uuid
            unique_suffix = str(uuid.uuid4())[:4]
            final_tag_name = f"{tag_name}-{unique_suffix}"

            # Create tag and link articles
            tag = add_tag(final_tag_name)
            for article_id in cluster_article_ids:
                tag_article(article_id, final_tag_name)
            tag_map[final_tag_name] = cluster_article_ids
        return tag_map

    return {str(k): v for k, v in clusters.items() if k != -1}
