# Summary: 260408-uf8-dedup-cluster

## What was done

### Task 1: Install datasketch + SQLite migration
- Added `datasketch>=1.6.4` to `pyproject.toml` dependencies
- Added `content_hash TEXT` and `minhash_signature BLOB` columns to `_ARTICLES_EXTRA_COLUMNS` in `src/storage/sqlite/init.py`
- Added `idx_articles_content_hash` index on `content_hash`
- Fixed pre-existing bug in `src/storage/sqlite/impl.py`: `row.get()` replaced with `row[]` for `sqlite3.Row` access

### Task 2: Implement three-level dedup pipeline
Created `src/application/dedup.py` with:
- `compute_content_hash(title, content)` — SHA256 of title + first 500 chars
- `compute_minhash_signature(text)` — MinHash with num_perm=128, pickled to BLOB
- `deduplicate_articles(articles, threshold=0.85)` — three-level pipeline:
  - **Level 1**: Exact dedup via SHA256 content_hash
  - **Level 2**: MinHash LSH approximate dedup (Jaccard >= 0.85)
  - **Level 3**: Embedding cosine dedup (cosine >= 0.92) via ChromaDB

### Task 3: Enhance clustering with embedding-based similarity
Modified `_cluster_articles_into_topics()` in `src/application/report.py`:
- Fetches ChromaDB embeddings for all articles in a layer
- Dynamic k selection: `k = max(5, min(sqrt(n/2), 50))`
- K-Means clustering on embedding matrix
- Small clusters (<=2) merged with nearest neighbour by centroid cosine similarity
- Legacy articles (no embeddings) fall back to feed_id + keyword overlap
- Fixed numpy array truthiness bug (`if cid and emb` → `if cid is not None and emb is not None`)
- Added `deduplicate_articles()` call in `_cluster_articles_v2_async()` before per-layer clustering

## Verification
- `uv add datasketch` installed successfully (v1.9.0)
- All imports: `deduplicate_articles`, `compute_content_hash`, `compute_minhash_signature` pass
- SQLite init: schema migrated without errors
- `feedship report --template v2 --since 2026-04-01 --until 2026-04-08` generated successfully
- Report shows proper topic clusters with LLM-generated titles (no fallback to feed_id grouping)
- No ChromaDB fetch errors in output

## Files changed
- `pyproject.toml` — added datasketch dependency
- `src/storage/sqlite/init.py` — added content_hash + minhash_signature columns and index
- `src/storage/sqlite/impl.py` — fixed sqlite3.Row.get() → row[] for 5 fields
- `src/application/report.py` — enhanced _cluster_articles_into_topics with K-Means, added dedup call
- `src/application/dedup.py` — new file with three-level dedup pipeline
