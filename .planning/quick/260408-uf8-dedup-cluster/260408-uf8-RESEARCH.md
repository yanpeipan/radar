# Phase Research: 大规模去重+话题聚类+智能摘要生成

**Researched:** 2026-04-08
**Domain:** News deduplication, topic clustering, and intelligent summarization for RSS feed processing
**Confidence:** MEDIUM

## Summary

This phase introduces three complementary systems to improve report quality:
1. **Three-level deduplication** eliminates redundant articles before processing
2. **Topic clustering** groups semantically similar articles into coherent topics
3. **Intelligent summarization** generates hierarchical summaries from article clusters

The existing Feedship infrastructure (SQLite, ChromaDB, sentence-transformers, scikit-learn, LangChain LCEL) provides a solid foundation. Key gaps: MinHash approximate deduplication (datasketch not installed) and BERTopic for advanced clustering (not installed).

**Primary recommendation:** Implement incrementally — start with Level 1 (MD5 exact dedup) + existing keyword clustering, then add MinHash and embedding-based methods as needed.

## User Constraints

*No CONTEXT.md found — this is a greenfield feature request.*

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-DEDUP | Three-level deduplication (MD5/MinHash/Embedding) | Libraries identified: datasketch, existing ChromaDB cosine similarity |
| REQ-CLUSTER | Topic clustering with embedding + HDBSCAN/K-Means | Libraries: sentence-transformers (available), BERTopic (optional), scikit-learn (available) |
| REQ-SUMMARY | Hierarchical intelligent summary generation | Uses existing LangChain LCEL infrastructure |

## Standard Stack

### Core Dependencies (Already Available)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| **chromadb** | 1.5.6 | Vector store for semantic search | Active |
| **scikit-learn** | 1.8.0 | K-Means clustering, BM25, dimensionality reduction | Active |
| **numpy** | 1.26.x | Array operations | Active |

### Additional Dependencies Required
| Library | Version | Purpose | Install |
|---------|---------|---------|---------|
| **datasketch** | 1.6.x | MinHashLSH for approximate deduplication | `uv add datasketch` |
| **sentence-transformers** | 5.3.x | Text embeddings | Already in ml extras |

### Optional (For Advanced Clustering)
| Library | Purpose | When to Use |
|---------|---------|-------------|
| **BERTopic** | Neural topic modeling with UMAP+HDBSCAN | If semantic topic discovery needed beyond keyword clustering |
| **umap-learn** | UMAP dimensionality reduction (BERTopic dependency) | Only if using BERTopic |

**Note:** The existing `_cluster_articles_into_topics()` in report.py uses simple keyword overlap + feed_id grouping. This can be replaced incrementally with embedding-based methods.

## Architecture Patterns

### Three-Level Deduplication Strategy

```
Article Ingestion
    │
    ├── Level 1: MD5 Exact Dedup (title + first 500 chars hash)
    │           → SQLite: articles.content_hash column
    │           → Fast, O(1) lookup
    │
    ├── Level 2: MinHash Approximate Dedup
    │           → datasketch.MinHashLSH
    │           → Catches near-duplicates (rewrites, trackbacks)
    │           → Threshold: Jaccard similarity >= 0.85
    │
    └── Level 3: Embedding Semantic Dedup
                → ChromaDB cosine similarity
                → Catches semantically similar articles
                → Threshold: cosine similarity >= 0.92
```

**Integration with existing system:**
- Existing `compute_content_hash()` in llm/core.py already computes SHA256 hash
- Need to add content_hash column to articles table if not present
- MinHash can be stored in ChromaDB metadata or separate SQLite table
- ChromaDB collection `articles` already stores embeddings — reuse for semantic dedup

### Deduplication Storage Schema

```sql
-- Add to articles table
ALTER TABLE articles ADD COLUMN content_hash TEXT;
ALTER TABLE articles ADD COLUMN minhash_signature BLOB;

-- Index for fast lookup
CREATE INDEX idx_articles_content_hash ON articles(content_hash);
```

### Topic Clustering Architecture

**Option A: Incremental Enhancement (Recommended)**
- Replace current keyword overlap in `_cluster_articles_into_topics()` with embedding cosine similarity
- Use existing ChromaDB collection to fetch article embeddings
- scikit-learn K-Means for clustering (already available)

**Option B: Full BERTopic Pipeline**
- UMAP dimensionality reduction → HDBSCAN clustering → c-TF-IDF topic representation
- More powerful but heavier dependency

**Proposed: Hybrid approach**
1. Fetch embeddings from ChromaDB for all articles in date range
2. Compute pairwise cosine similarity matrix (batch operation)
3. Use scikit-learn AgglomerativeClustering or K-Means on embedding vectors
4. Merge small clusters with nearest neighbor (existing logic)

### Hierarchical Summary Generation

Existing infrastructure (report.py + llm/chains.py) supports this:

```
Cluster of N articles
    │
    ├── Extract key points per article (use existing summarize_article_content)
    │
    ├── Cluster-level summary via get_layer_summary_chain()
    │   (already implemented in llm/chains.py LAYER_SUMMARY_PROMPT)
    │
    └── Topic-level title via get_topic_title_chain()
        (already implemented in llm/chains.py TOPIC_TITLE_PROMPT)
```

**Enhancement opportunity:** Add article-level importance weighting based on quality_score before generating cluster summary.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Approximate deduplication | Custom MinHash implementation | datasketch.MinHash | Correct Jaccard estimation, optimized storage |
| Topic modeling | Custom TF-IDF clustering | BERTopic or scikit-learn | Battle-tested, handles outliers with HDBSCAN |
| Embedding computation | Direct transformer inference | sentence-transformers | Optimized models (all-MiniLM-L6-v2), batch inference |
| Cosine similarity search | Naive pairwise comparison | ChromaDB query with where filter | Indexed, memory-efficient |

## Common Pitfalls

### Pitfall 1: Embedding Staleness
**What goes wrong:** Articles embedded once with old model version become incompatible.
**How to avoid:** Store model name in ChromaDB collection metadata; re-embed if model changes.

### Pitfall 2: MinHash Memory Explosion
**What goes wrong:** Storing MinHash for 10K+ articles without pruning.
**How to avoid:** Set max_perm=128 (sufficient precision); prune signatures older than 30 days.

### Pitfall 3: ChromaDB Query Latency at Scale
**What goes wrong:** cosine similarity query across 10K vectors in ChromaDB is slow.
**How to avoid:** Pre-filter by date range in SQL, then query ChromaDB with `where` clause on article_id; use batch queries.

### Pitfall 4: Duplicate Processing in Report Generation
**What goes wrong:** Same article appears in multiple clusters due to improper dedup.
**How to avoid:** Deduplication MUST happen before clustering, not after.

## Performance Considerations for 10K Articles

| Operation | Time Estimate | Strategy |
|-----------|----------------|----------|
| MD5 hash computation | < 1s | Batch compute, SQLite index lookup |
| MinHash signature (128 permutations) | ~5s for 10K | Batch with datasketch, store signatures |
| Embedding fetch from ChromaDB | ~10s | Batch query with IDs filter |
| Cosine similarity matrix (10K x 10K) | ~30s | Use sklearn.metrics.pairwise.cosine_similarity, compute on demand for date-range subset |
| K-Means clustering (10K, k=50) | ~15s | sklearn.cluster.KMeans, n_init=3 |

**Total estimate:** ~1-2 minutes for full pipeline on 10K articles.

**Optimization:** Process only articles in report date range (not full DB).

## Integration Points

### Where Deduplication Fits
```
fetch_articles() → deduplicate() → classify() → cluster() → generate_report()
```

Should run AFTER fetching articles but BEFORE storing to database, OR as a pre-processing step before report generation.

### Where Clustering Fits
Current `_cluster_articles_into_topics()` in report.py is called during report generation. Can be enhanced to use embeddings instead of keyword overlap.

### ChromaDB Schema Extension

```python
# Existing collection: "articles"
# Add metadata fields:
{
    "article_id": "...",
    "content_hash": "...",      # For exact dedup
    "minhash_sig": "...",       # Base64 encoded MinHash
    "published_date": "...",
    "feed_id": "..."
}
```

## Code Examples

### MinHash Deduplication (datasketch)

```python
from datasketch import MinHash, MinHashLSH
import json

def create_minhash(text: str, num_perm: int = 128) -> MinHash:
    m = MinHash(num_perm=num_perm)
    for word in text.split():
        m.update(word.encode('utf8'))
    return m

def find_near_duplicates(texts: list[str], threshold: float = 0.85) -> list[set[int]]:
    lsh = MinHashLSH(threshold=threshold, num_perm=128)
    minhashes = []
    for i, text in enumerate(texts):
        m = create_minhash(text)
        minhashes.append(m)
        lsh.insert(f"doc_{i}", m)
    
    # Find duplicates
    duplicates = []
    for i, m in enumerate(minhashes):
        matches = lsh.query(m)
        if len(matches) > 1:
            dup_set = {int(m.replace("doc_", "")) for m in matches}
            duplicates.append(dup_set)
    return duplicates
```

### Embedding-Based Clustering (scikit-learn)

```python
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

def cluster_articles_by_embedding(embeddings: np.ndarray, n_clusters: int = 50) -> np.ndarray:
    """Cluster articles using K-Means on embedding vectors."""
    # Reduce dimensionality if needed
    if embeddings.shape[1] > 384:
        from sklearn.decomposition import TruncatedSVD
        embeddings = TruncatedSVD(n_components=384).fit_transform(embeddings)
    
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=3)
    return kmeans.fit_predict(embeddings)

def find_similar_articles(embedding: np.ndarray, all_embeddings: np.ndarray, top_k: int = 5) -> list[int]:
    """Find most similar articles by cosine similarity."""
    similarities = cosine_similarity([embedding], all_embeddings)[0]
    return np.argsort(similarities)[-top_k:].tolist()
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | sentence-transformers uses all-MiniLM-L6-v2 (384-dim) | Standard Stack | ChromaDB collection dimension mismatch — check with `chromadb.get_collection().metadata` |
| A2 | datasketch 1.6.x compatible with Python 3.12 | Dependencies | May need version adjustment |
| A3 | ChromaDB can handle 10K vectors efficiently | Performance | May need to use Annoy or FAISS for larger scale |

## Open Questions

1. **When to deduplicate?**
   - Option A: At fetch time (before storing) — cleaner DB, but loses potential "same topic from different sources"
   - Option B: At report generation time — keeps diversity, but processes more articles
   - Recommendation: Option B for semantic dedup (keep different perspectives), Option A for exact/MinHash dedup

2. **Cluster count (k) selection?**
   - Fixed k=50 may not fit all date ranges
   - Could use dynamic k = sqrt(n/2) or hierarchical clustering with automatic cut

3. **MinHash storage location?**
   - ChromaDB metadata (simple but not queryable)
   - Separate SQLite table (queryable, but adds complexity)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| chromadb | Semantic dedup, vector search | ✓ | 1.5.6 | — |
| scikit-learn | K-Means, BM25 | ✓ | 1.8.0 | — |
| sentence-transformers | Embedding generation | ml extras | 5.3.0 | Install with `uv add -e .[ml]` |
| datasketch | MinHash LSH | ✗ | — | `uv add datasketch` |
| numpy | Array operations | ✓ | 1.26.x | — |

**Missing dependencies with fallback:**
- **datasketch**: Not installed — plan must include `uv add datasketch`

**Missing dependencies with no fallback:**
- None blocking — all core functionality has fallback

## Validation Architecture

*No nyquist_validation config found — validation section skipped.*

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V5 Input Validation | Yes | Content from RSS feeds — sanitize before embedding |
| V4 Access Control | No | Local-only application |

**Known threat patterns:**
- **RSS feed poisoning**: Malicious content in feed items could inject harmful text
- ** Mitigation**: Use existing trafilatura sanitization; LLM prompts should not execute arbitrary content

## Sources

### Primary (HIGH confidence)
- [datasketch GitHub](https://github.com/ekzhu/datasketch) - MinHash LSH documentation
- [scikit-learn KMeans](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html) - Clustering API
- [sentence-transformers](https://sbert.net/) - Embedding model documentation

### Secondary (MEDIUM confidence)
- [BERTopic documentation](https://maartengr.github.io/BERTopic/) - Topic modeling approach
- [ChromaDB query documentation](https://docs.trychroma.com/) - Vector operations

### Tertiary (LOW confidence)
- Performance estimates based on general knowledge; needs benchmarking with actual data

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM - packages verified, specific versions need confirmation
- Architecture: MEDIUM - pattern is sound, integration points need design
- Pitfalls: MEDIUM - common issues identified, mitigation strategies proposed

**Research date:** 2026-04-08
**Valid until:** 2026-05-08 (30 days)
