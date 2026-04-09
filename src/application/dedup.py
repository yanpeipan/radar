"""Three-level article deduplication pipeline.

Level 1 — MD5/SHA256 exact dedup:   content_hash stored in SQLite (SHA256 of title + first 500 chars).
Level 2 — MinHash LSH approximate dedup: Jaccard >= 0.85 via datasketch.
Level 3 — Embedding cosine dedup:    cosine similarity >= 0.92 via ChromaDB embeddings.

All three levels run before clustering in the report generation flow.
"""

from __future__ import annotations

import hashlib
import logging
import pickle

from datasketch import MinHash, MinHashLSH

from src.storage.vector import get_chroma_collection

logger = logging.getLogger(__name__)

# Threshold constants
_MINHASH_THRESHOLD = 0.85  # Jaccard similarity for MinHash LSH
_EMBEDDING_THRESHOLD = 0.92  # Cosine similarity for semantic dedup
_NUM_PERM = 128  # MinHash number of permutations


def compute_content_hash(title: str, content: str) -> str:
    """Compute SHA256 hash of title + first 500 chars of content.

    Args:
        title: Article title.
        content: Article content (or description as fallback).

    Returns:
        Hex-encoded SHA256 digest of title + first 500 content chars.
    """
    text = f"{title}{content[:500]}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_minhash_signature(text: str) -> bytes:
    """Compute MinHash signature for a piece of text.

    Args:
        text: The text to hash (title + content).

    Returns:
        Pickled MinHash signature as bytes, suitable for storage in SQLite BLOB.
    """
    tokens = text.lower().split()
    m = MinHash(num_perm=_NUM_PERM)
    for token in tokens:
        m.update(token.encode("utf-8"))
    return pickle.dumps(m)


def _level1_exact_dedup(articles: list[dict]) -> list[dict]:
    """Level 1: Remove exact duplicates by content_hash.

    Articles missing content_hash are kept (may be legacy data).
    Returns deduplicated list preserving first occurrence order.
    """
    seen: dict[str, dict] = {}
    for a in articles:
        ch = a.get("content_hash")
        if ch is None:
            # No hash yet — keep it, but don't use as dedup source
            key = id(a)
            seen[f"__keep_{key}__"] = a
        elif ch not in seen:
            seen[ch] = a
        # else: exact duplicate, skip
    return list(seen.values())


def _level2_minhash_dedup(articles: list[dict]) -> list[dict]:
    """Level 2: Remove near-duplicates using MinHash LSH (Jaccard >= 0.85).

    Articles missing minhash_signature are kept but not used as LSH sources.
    Returns deduplicated list preserving first occurrence order.
    """
    # Build LSH index from articles that have signatures
    lsh = MinHashLSH(threshold=_MINHASH_THRESHOLD, num_perm=_NUM_PERM)
    signature_map: dict[str, dict] = {}  # key -> article

    for a in articles:
        sig_blob = a.get("minhash_signature")
        if sig_blob is None:
            continue
        try:
            m = pickle.loads(sig_blob)
            key = a.get("content_hash") or id(a)
            lsh.insert(key, m)

            signature_map[key] = a
        except Exception as e:
            logger.warning("Failed to load MinHash for article %s: %s", a.get("id"), e)

    # Collect articles that are not near-duplicates
    result: list[dict] = []
    for a in articles:
        sig_blob = a.get("minhash_signature")
        if sig_blob is None:
            result.append(a)
            continue
        try:
            m = pickle.loads(sig_blob)
            key = a.get("content_hash") or id(a)
            # Query LSH for near-duplicates
            neighbors = lsh.query(m)
            if not neighbors or neighbors == [key]:
                # Not a near-duplicate of anything we've kept
                result.append(a)
                # Add to LSH so later articles can dedup against it
                lsh.insert(key, m)

                signature_map[key] = a
        except Exception as e:
            logger.warning(
                "MinHash LSH query failed for article %s: %s", a.get("id"), e
            )
            result.append(a)

    return result


def _level3_embedding_dedup(
    articles: list[dict],
    threshold: float = _EMBEDDING_THRESHOLD,
) -> list[dict]:
    """Level 3: Remove near-duplicates using embedding cosine similarity >= 0.92.

    Fetches ChromaDB embeddings for articles in the input list and computes
    pairwise cosine similarity. Articles without embeddings fall through (kept).

    Args:
        articles: List of article dicts with 'id' keys.
        threshold: Cosine similarity threshold (default 0.92).

    Returns:
        Deduplicated list preserving first occurrence order.
    """
    if len(articles) < 2:
        return articles

    # Collect article IDs
    ids = [a["id"] for a in articles]

    try:
        collection = get_chroma_collection()
        existing = collection.get(ids=ids, include=["embeddings"])
    except Exception as e:
        logger.warning("ChromaDB fetch for embedding dedup failed: %s", e)
        return articles

    chroma_ids = existing.get("ids", [])
    embeddings_list: list[list[float] | None] = existing.get("embeddings", [])

    # Map chroma_id -> embedding
    id_to_embedding: dict[str, list[float]] = {}
    for i, cid in enumerate(chroma_ids):
        emb = embeddings_list[i] if i < len(embeddings_list) else None
        if cid is not None and emb is not None:
            id_to_embedding[cid] = emb

    # Build embedding matrix for articles that have embeddings
    articles_with_emb: list[dict] = []
    emb_matrix: list[list[float]] = []
    for a in articles:
        e = id_to_embedding.get(a["id"])
        if e is not None:
            articles_with_emb.append(a)
            emb_matrix.append(e)

    if len(articles_with_emb) < 2:
        return articles

    # Compute pairwise cosine similarity using sklearn
    from sklearn.metrics.pairwise import cosine_similarity

    sim_matrix = cosine_similarity(emb_matrix)

    # Mark duplicates: article i is duplicate of j if sim_matrix[i][j] >= threshold and j comes first
    n = len(articles_with_emb)
    duplicate_flags = [False] * n
    for i in range(n):
        if duplicate_flags[i]:
            continue
        for j in range(i + 1, n):
            if sim_matrix[i][j] >= threshold:
                duplicate_flags[j] = True

    # Build result: articles without embeddings always pass through
    result: list[dict] = []
    emb_idx = 0
    for a in articles:
        e = id_to_embedding.get(a["id"])
        if e is None:
            result.append(a)
        else:
            if not duplicate_flags[emb_idx]:
                result.append(a)
            emb_idx += 1

    return result


def deduplicate_articles(
    articles: list[dict],
    threshold: float = 0.85,
) -> list[dict]:
    """Remove duplicate articles at three levels.

    Level 1 — Exact dedup (SHA256 content_hash): removes bit-for-bit identical content.
    Level 2 — MinHash LSH (Jaccard >= threshold): removes near-duplicate text.
    Level 3 — Embedding cosine (>= 0.92): removes semantically identical articles.

    Args:
        articles: List of article dicts with id, content_hash, minhash_signature, etc.
        threshold: MinHash LSH Jaccard threshold (default 0.85). Embedding threshold is fixed at 0.92.

    Returns:
        Deduplicated article list preserving first occurrence order.
    """
    if not articles:
        return []

    logger.debug("Dedup input: %d articles", len(articles))

    # Level 1: exact hash dedup
    step1 = _level1_exact_dedup(articles)
    logger.debug("After Level 1 (exact): %d articles", len(step1))

    # Level 2: MinHash LSH dedup
    step2 = _level2_minhash_dedup(step1)
    logger.debug("After Level 2 (MinHash): %d articles", len(step2))

    # Level 3: Embedding cosine dedup
    step3 = _level3_embedding_dedup(step2)
    logger.debug("After Level 3 (embedding): %d articles", len(step3))

    removed = len(articles) - len(step3)
    if removed > 0:
        logger.info(
            "Dedup removed %d duplicate articles (%d -> %d)",
            removed,
            len(articles),
            len(step3),
        )

    return step3
