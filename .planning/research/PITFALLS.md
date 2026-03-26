# Pitfalls Research

**Domain:** ChromaDB + sentence-transformers semantic search integration in Python content aggregation app
**Researched:** 2026-03-26
**Confidence:** MEDIUM (official docs limited, primarily GitHub issues and community discussions)

## Critical Pitfalls

### Pitfall 1: ChromaDB SQLite File Descriptor Leaks

**What goes wrong:**
After running queries, ChromaDB fails with `sqlite3.OperationalError: unable to open database file` or `OSError: [Errno 24] Too many open files`. The service crashes intermittently after working fine initially.

**Why it happens:**
ChromaDB opens new SQLite connections for each operation but does not properly close them. Under load or after many queries, the process exhausts its file descriptor limit. This is a known bug in ChromaDB's sqlite pool implementation (GitHub issue #4039).

**How to avoid:**
- Use ChromaDB in single-process mode (EphemeralClient or single PersistentClient instance)
- Set `ulimit -n` to a high value before running (e.g., `ulimit -n 65536`)
- Monitor open file descriptors with `lsof -p <pid>` for your Python process
- Implement connection pooling at the application level if using PersistentClient
- Consider using ChromaDB's HTTP client mode with a single worker to isolate the issue

**Warning signs:**
- `OSError: [Errno 24] Too many open files` appears in logs before the SQLite error
- Query latency increases over time
- Number of open files grows monotonically

**Phase to address:**
This is a ChromaDB infrastructure issue — address in the **embedding storage phase** when setting up ChromaDB integration. Mitigation strategies should be in place before handling large article volumes.

---

### Pitfall 2: Embedding Function Not Persisted Across Restarts

**What goes wrong:**
A collection created with a custom embedding function (e.g., OpenAIEmbeddingFunction, or sentence-transformers) loses its embedding function after client restart. Subsequent queries fail or produce incorrect results.

**Why it happens:**
ChromaDB stores collection metadata (name, settings) but not the embedding function itself. When you recreate a client, the collection re-opens with the default embedding function unless you explicitly re-specify it.

**How to avoid:**
- Always pass the same `embedding_function` when getting a collection: `client.get_collection("name", embedding_function=my_ef)`
- Store the embedding function configuration alongside your app's configuration
- Create a helper function that consistently initializes collections with the correct embedding function
- Document which embedding function each collection uses

```python
# Correct pattern
def get_articles_collection(client):
    return client.get_collection(
        "articles",
        embedding_function=sentence_transformer_ef
    )

# Wrong - loses embedding function after restart
collection = client.get_collection("articles")
```

**Warning signs:**
- Query results change unexpectedly after application restart
- Embedding dimension mismatches when querying
- Collection works initially but fails after code deployment

**Phase to address:**
**Embedding generation phase** — the embedding function setup must be consistent and documented before any articles are added.

---

### Pitfall 3: Model Download on First Query Causes Timeout

**What goes wrong:**
The first semantic search query hangs for 30+ seconds or times out. Subsequent queries are fast.

**Why it happens:**
The default sentence-transformers model (`all-MiniLM-L6-v2`) downloads ~90MB of model files on first use. If network is slow or the first query is in a time-sensitive context, users experience long delays.

**How to avoid:**
- Explicitly download/bake in the model at application startup, before any user query

```python
from sentence_transformers import SentenceTransformer

# At startup / initialization
model = SentenceTransformer('all-MiniLM-L6-v2')
# Warm up the model
model.encode(["warmup"])
```

- Cache the model in a known location using `model.save()`
- Consider bundling a smaller model or using ONNX for faster initialization
- Set appropriate timeouts and show progress to users during first load

**Warning signs:**
- First search command takes >10 seconds
- Logs show model downloading or `Downloading [...]` messages
- ChromaDB collection creation is slow

**Phase to address:**
**Embedding generation phase** — model initialization should happen during app startup, not on first query.

---

### Pitfall 4: HNSW Index Corruption from Concurrent Access

**What goes wrong:**
HNSW index fails to load with `Error loading hnsw index` or `Error constructing hnsw segment reader`. The collection becomes unqueryable.

**Why it happens:**
ChromaDB's HNSW index (backed by hnswlib) has thread-safety limitations:
- `add_items` and `knn_query` cannot run concurrently on the same index
- `resize_index` is not thread-safe with `add_items` and `knn_query`
- Pickling an index while adding items is not thread-safe (GitHub hnswlib issues)

ChromaDB has known HNSW bugs including memory leaks and deleted nodes being counted toward `ef` (GitHub issue #3486).

**How to avoid:**
- Use ChromaDB in single-threaded mode for writing (no concurrent add operations)
- Query operations (`knn_query`) can be concurrent but not with writes
- Set `allow_reset=True` in Settings only if you can afford data loss for recovery
- Implement application-level locking if you need concurrent writes to the same collection
- Monitor index size — oversized indexes are more likely to corrupt

**Warning signs:**
- `Error loading hnsw index` in logs
- Inconsistent query results (sometimes empty, sometimes correct)
- Application crashes during concurrent write + read operations

**Phase to address:**
**Embedding storage phase** — the ChromaDB configuration and deployment mode must be decided before concurrent article fetching is implemented.

---

### Pitfall 5: Query Parameter In-Place Mutation Corruption

**What goes wrong:**
Query results become corrupted across calls. The `include` parameter accumulates mutations causing wrong results or validation errors.

**Why it happens:**
ChromaDB's CollectionCommon.py (line 307-314) mutates the `include` list in-place without copying it. If you reuse the same list object across multiple queries, mutations accumulate (GitHub issue #5857).

**How to avoid:**
Always pass a fresh list for the `include` parameter:

```python
# Wrong - can cause corruption
my_include = ["embeddings", "documents"]
collection.query(query_texts=["test1"], include=my_include)
collection.query(query_texts=["test2"], include=my_include)  # my_include is now mutated

# Correct - always use fresh list
collection.query(query_texts=["test1"], include=["embeddings", "documents"])
collection.query(query_texts=["test2"], include=["embeddings", "documents"])
```

**Warning signs:**
- Query results vary for the same query string
- Validation errors in newer ChromaDB versions
- Sporadic empty result sets

**Phase to address:**
**Query implementation phase** — wrap all query calls with fresh parameter lists.

---

### Pitfall 6: Collection Deletion Leaves Orphaned Files

**What goes wrong:**
Calling `delete_collection()` does not remove the data files from disk. Over time, disk usage grows unbounded even after deleting articles and collections.

**Why it happens:**
Known bug in ChromaDB: `delete_collection` and `collection.delete(ids)` do not properly clean up the underlying storage files. The folder in `./chroma/{uuid}` persists (GitHub issues #5520, #1309).

**How to avoid:**
- Periodically run a cleanup routine that identifies and removes orphaned ChromaDB data directories
- Track collection IDs in your SQLite database and explicitly clean up ChromaDB storage when articles are deleted
- Use `client.reset()` only as a last resort (deletes ALL collections)
- Monitor `./chroma` directory size separately from your SQLite database

```python
import shutil
import os

def cleanup_chroma_orphans(client, valid_collection_ids):
    chroma_dir = "./chroma"
    if not os.path.exists(chroma_dir):
        return
    for folder in os.listdir(chroma_dir):
        folder_path = os.path.join(chroma_dir, folder)
        if os.path.isdir(folder_path) and folder not in valid_collection_ids:
            shutil.rmtree(folder_path)
```

**Warning signs:**
- `./chroma` directory grows despite deleting articles
- `delete_collection()` returns success but disk usage unchanged
- Multiple ChromaDB versions or restarts cause data accumulation

**Phase to address:**
**Embedding storage phase** — implement cleanup alongside the storage implementation to prevent accumulation.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Using default embedding function without explicit configuration | Simpler initial code | Embedding function loss on restart, inconsistent results | Never for production |
| Letting ChromaDB manage its own SQLite | No separate setup | File descriptor leaks, persistence bugs | Only for very low-volume apps |
| Not setting `ef` parameter for HNSW | Default works | Suboptimal search quality/speed | Only for initial prototyping |
| Storing all embeddings in a single collection | Simpler code | Performance degradation at scale | Only for <10k articles |
| Using relative paths for ChromaDB persistence | Works on dev machine | Path resolution issues in production | Only for single-user local apps |
| Ignoring model warmup | Faster startup perceived | First query timeout | Only for CLI tools run once |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| ChromaDB + SQLite | Two separate database files with no coordination | Track ChromaDB collection IDs in SQLite; coordinate deletions |
| ChromaDB + sentence-transformers | Model downloaded on first query | Pre-download and warmup model at startup |
| ChromaDB + asyncio | Concurrent writes corrupt HNSW | Use asyncio.Lock for write operations to same collection |
| ChromaDB + uvloop | Event loop conflicts with ChromaDB's threading | Use ChromaDB in main thread or separate process |
| ChromaDB + httpx async fetch | Fast article ingestion floods ChromaDB | Add backpressure / batching for embedding writes |
| ChromaDB + existing FTS5 | Redundant search capabilities | ChromaDB for semantic, FTS5 for keyword; do not duplicate |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Large article batch ingestion | Memory spikes, HNSW index corruption | Batch embeddings (100-500 articles), add with pauses | >10k articles in single batch |
| Using default HNSW `ef` | Slow queries or low recall | Set `ef=200` for better accuracy, tune based on results | >100k vectors |
| No embedding cache | Repeated encoding of same content | Cache article embeddings in SQLite before ChromaDB | When re-fetching articles |
| Single large collection | Query latency increases | Partition by feed or time period | >500k total article embeddings |
| Not indexing on metadata | Slow filtered queries | Create separate collections or use ChromaDB's metadata indexing | When filtering by feed/tag/time |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing embeddings without article content | Cannot reconstruct original text | Always store full article text alongside embedding |
| No input sanitization on query_texts | Potential injection via malformed queries | Sanitize user query input before passing to ChromaDB |
| Exposing ChromaDB HTTP server without auth | Unauthorized data access | Use local-only PersistentClient for personal tool |
| Storing sensitive article metadata in ChromaDB | Data leakage if device compromised | Keep sensitive metadata in main SQLite only |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| First semantic search is slow | User thinks app is broken | Show "loading model..." message on first search |
| Empty results for valid queries | User confused about semantic vs keyword | Clearly label semantic search; offer keyword fallback |
| No similarity score explanation | User doesn't understand relevance | Show distance/similarity score alongside results |
| Semantic search replacing FTS5 | Keyword searches become less discoverable | Keep both; semantic for "related", FTS5 for "exact" |
| No indication of search mode | User uses wrong command | Visual distinction between `search` and `search --semantic` |

---

## "Looks Done But Isn't" Checklist

- [ ] **Embedding generation:** Model downloads successfully but warmup not done — verify first query is fast
- [ ] **Embedding storage:** ChromaDB collection created but embedding function not saved — verify across restart
- [ ] **Article deletion:** Article deleted from SQLite but ChromaDB orphan files remain — verify disk usage
- [ ] **Semantic search:** Query returns results but similarity scores not shown — verify result quality
- [ ] **Collection cleanup:** `delete_collection` called but data folder persists — verify cleanup routine
- [ ] **Incremental updates:** New articles added but embeddings not generated — verify background job works

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| ChromaDB file descriptor exhaustion | MEDIUM | Restart process, increase ulimit, switch to single-worker mode |
| HNSW index corruption | HIGH | Delete collection, re-embed all articles, restore from backup |
| Embedding function loss | MEDIUM | Re-specify embedding function, verify dimension consistency |
| Orphaned ChromaDB storage | LOW | Run cleanup script to remove `./chroma` directories for deleted collections |
| Query corruption from mutation | LOW | Restart application, pass fresh list objects to queries |
| Model not pre-downloaded | LOW | Pre-download model, add warmup at startup |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| File descriptor leaks | Phase: Embedding Storage Infrastructure | Monitor open files during extended use |
| Embedding function persistence | Phase: Embedding Generation | Restart app, verify query still works |
| Model download timeout | Phase: Embedding Generation | First query should be <2 seconds after warmup |
| HNSW corruption | Phase: Embedding Storage | Test concurrent read/write scenarios |
| Query parameter mutation | Phase: Query Implementation | Run same query 10x, verify consistent results |
| Orphaned storage files | Phase: Embedding Storage | Delete articles, verify disk usage decreases |
| asyncio conflicts | Phase: Async Integration | Test uvloop + ChromaDB coexistence |

---

## Sources

- [ChromaDB GitHub Issue #4039](https://github.com/chroma-core/chroma/issues/4039) — SQLite file descriptor leak (HIGH confidence)
- [ChromaDB GitHub Issue #3486](https://github.com/chroma-core/chroma/issues/3486) — HNSW bugs (HIGH confidence)
- [ChromaDB GitHub Issue #5857](https://github.com/chroma-core/chroma/issues/5857) — Query parameter mutation corruption (HIGH confidence)
- [ChromaDB GitHub Issue #6021](https://github.com/chroma-core/chroma/issues/6021) — Embedding function not persisted (HIGH confidence)
- [ChromaDB GitHub Issue #5520](https://github.com/chroma-core/chroma/issues/5520) — Collection deletion leaves files (HIGH confidence)
- [ChromaDB GitHub Issue #1309](https://github.com/chroma-core/chroma/issues/1309) — PersistentClient delete_collection bug (HIGH confidence)
- [ChromaDB GitHub Issue #6432](https://github.com/chroma-core/chroma/issues/6432) — Multi-worker inconsistency (HIGH confidence)
- [hnswlib GitHub](https://github.com/nmslib/hnswlib) — Thread safety warnings, distance metric limitations (HIGH confidence)
- [sentence-transformers Documentation](https://www.sbert.net/docs/pretrained_models.html) — Model selection, common mistakes (HIGH confidence)
- [ChromaDB Documentation](https://docs.trychroma.com/docs/overview) — Embedding configuration (MEDIUM confidence — API docs partially unavailable)

---
*Pitfalls research for: ChromaDB + sentence-transformers semantic search in Python RSS reader*
*Researched: 2026-03-26*
