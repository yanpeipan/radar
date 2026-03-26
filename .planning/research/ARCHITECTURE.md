# Architecture Research: ChromaDB Semantic Search Integration

**Domain:** Personal资讯系统 (RSS reader with vector search)
**Researched:** 2026-03-26
**Confidence:** MEDIUM (documentation fragmented, PyPI/main docs not fully aligned; verified core patterns via official sources)

## Executive Summary

ChromaDB is an embedded vector database that coexists naturally alongside SQLite. The integration pattern is **not** to replace SQLite or merge data stores, but to use SQLite for article metadata and ChromaDB for embedding storage and similarity search. ChromaDB runs in-process (embedded mode) with its own persistence, making it a zero-infrastructure addition like SQLite itself.

**Key insight:** ChromaDB's `PersistentClient` writes to a local directory, completely separate from the SQLite database file. Both databases serve different purposes and can operate independently.

---

## ChromaDB Deployment Modes

### Mode Comparison

| Mode | Use Case | Storage | Trade-offs |
|------|----------|---------|------------|
| `chromadb.Client()` (in-memory) | Prototyping only | RAM only, lost on restart | Fast but no persistence |
| `chromadb.PersistentClient(path="...")` | Local CLI app (recommended) | Local disk directory | Survives restarts, zero infra |
| `chromadb.HttpClient(host, port)` | Client-server, multi-process | Chroma server process | Requires running server |

**For this project:** `PersistentClient` is the correct choice. It stores data in a local directory (e.g., `./data/chroma_db/`) and requires no external service, matching the "纯本地应用" constraint.

---

## Recommended Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ search --fts  │  │ search --sem │  │ article related│    │
│  │  (FTS5)       │  │ (ChromaDB)   │  │  (ChromaDB)    │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
├─────────┴────────────────┴─────────────────┴────────────────┤
│                    Storage Layer                             │
│  ┌─────────────────────────┐  ┌────────────────────────────┐ │
│  │   SQLite (articles)     │  │  ChromaDB (embeddings)     │ │
│  │   src/storage/sqlite.py│  │  src/storage/vector.py     │ │
│  │   - Article CRUD       │  │  - Collection mgmt        │ │
│  │   - FTS5 keyword search│  │  - add/query embeddings   │ │
│  └─────────────────────────┘  └────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                  Embedding Service                          │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ sentence-transformers (all-MiniLM-L6-v2)               ││
│  │ src/embedding.py                                       ││
│  │ - encode(text) -> 384-dim vector                       ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|----------------|----------------|
| `src/storage/vector.py` | ChromaDB client lifecycle, collection CRUD | New file, wraps `chromadb.PersistentClient` |
| `src/embedding.py` | Text -> embedding vector | `sentence-transformers.SentenceTransformer` |
| `src/storage/sqlite.py` | Existing article storage (unchanged) | Already implemented |
| CLI commands | Interface for semantic search | Extend existing `src/cli/search.py` |

---

## Data Flow

### Flow 1: Article Fetch with Embedding Generation

```
[Provider.fetch_article()]
    ↓
[Article stored in SQLite via storage.py]
    ↓
[embedding_service.encode(article.content) → 384-dim vector]
    ↓
[vector_storage.add_embedding(article_id, vector, metadata)]
```

**Implementation:** After `storage.store_article()` succeeds in the existing crawl flow, call `vector_storage.add_embedding()`.

### Flow 2: Semantic Search

```
[CLI: search --semantic "query text"]
    ↓
[embedding_service.encode(query) → 384-dim vector]
    ↓
[vector_storage.query(query_vector, n_results=10) → article_ids]
    ↓
[storage.get_articles_by_ids(article_ids) → full article objects]
    ↓
[Render results with article titles/urls]
```

### Flow 3: Related Articles

```
[CLI: article related <article_id>]
    ↓
[vector_storage.get_embedding(article_id) → source vector]
    ↓
[vector_storage.query(source_vector, n_results=5, exclude=[article_id]) → related_ids]
    ↓
[storage.get_articles_by_ids(related_ids) → related articles]
    ↓
[Render related articles]
```

---

## ChromaDB Data Model

### Collection

A ChromaDB collection is analogous to a table. For this project:

```python
collection = client.get_or_create_collection(
    name="articles",
    metadata={"description": "Article content embeddings"}
)
```

### Document Record Structure

```python
collection.add(
    ids=[article.id],              # String ID (matches SQLite article.id)
    embeddings=[embedding_vector], # 384-dim numpy array (all-MiniLM-L6-v2)
    documents=[article.content],   # Full text for reference (optional)
    metadatas=[{
        "title": article.title,
        "url": article.url,
        "pub_date": article.pub_date.isoformat() if article.pub_date else None,
        "feed_id": article.feed_id,
    }]
)
```

**Note:** `ids` should match the `article.id` from SQLite (nanoid format) to enable cross-referencing between the two stores.

---

## Integration Points

### 1. Embedding Service (`src/embedding.py`) - NEW

```python
from sentence_transformers import SentenceTransformer

class EmbeddingService:
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            # all-MiniLM-L6-v2: 384-dim, fast, CPU-friendly
            cls._model = SentenceTransformer("all-MiniLM-L6-v2")
        return cls._model

    def encode(self, text: str) -> list[float]:
        """Generate embedding vector for text."""
        model = self.get_model()
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
```

**Dependencies added:** `sentence-transformers`, `torch`

### 2. Vector Storage Layer (`src/storage/vector.py`) - NEW

```python
import chromadb
from chromadb import PersistentClient
from pathlib import Path

class VectorStorage:
    def __init__(self, persist_path: str = "./data/chroma_db"):
        self.client = PersistentClient(path=persist_path)
        self.collection = self.client.get_or_create_collection(
            name="articles",
            metadata={"description": "Article content embeddings"}
        )

    def add_embedding(self, article_id: str, text: str, metadata: dict):
        """Add embedding for an article."""
        embedding = embedding_service.encode(text)
        self.collection.add(
            ids=[article_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata]
        )

    def query(self, query_text: str, n_results: int = 10, exclude_ids: list[str] = None):
        """Find similar articles by text query."""
        embedding = embedding_service.encode(query_text)
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
            include=["metadatas", "distances"]
        )
        return results  # {ids, distances, metadatas}

    def get_related(self, article_id: str, n_results: int = 5):
        """Find articles related to a given article."""
        result = self.collection.get(ids=[article_id], include=["embeddings"])
        if not result["ids"]:
            return []
        embedding = result["embeddings"][0]
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results + 1,  # +1 because query article may be included
            include=["metadatas", "distances"]
        )
        return results
```

### 3. CLI Integration - MODIFY `src/cli/search.py`

```python
# src/cli/search.py - additions
import click
from ...storage.vector import vector_storage
from ...embedding import embedding_service

@click.command()
@click.option("--semantic", "search_type", flag_value="semantic", default=False)
@click.option("--fts", "search_type", flag_value="fts", default=True)
@click.argument("query")
def search(query, search_type):
    """Search articles by keyword or semantics."""
    if search_type == "semantic":
        results = vector_storage.query(query, n_results=20)
        # Render from metadata
        for i, (article_id, metadata, distance) in enumerate(zip(
            results["ids"][0], results["metadatas"][0], results["distances"][0]
        )):
            click.echo(f"[{i+1}] {metadata['title']} (similarity: {1-distance:.3f})")
    else:
        # Existing FTS5 logic
        ...
```

---

## Project Structure

```
src/
├── embedding.py              # NEW: sentence-transformers wrapper
├── storage/
│   ├── sqlite.py             # EXISTING: article/feed CRUD
│   ├── vector.py             # NEW: ChromaDB wrapper
│   └── __init__.py
├── providers/                # EXISTING: RSSProvider, etc.
├── cli/
│   ├── search.py             # MODIFY: add --semantic flag
│   └── article.py            # MODIFY: add related command
└── crawl.py                  # MODIFY: call vector_storage after store_article()

data/
├── articles.db               # EXISTING: SQLite
└── chroma_db/                # NEW: ChromaDB persistence
    └── (ChromaDB files)
```

---

## Build Order

### Phase 1: Infrastructure (do first)
- Add `chromadb`, `sentence-transformers`, `torch` to dependencies
- Create `src/embedding.py` - basic model loading and encode()
- Create `src/storage/vector.py` - ChromaDB client initialization
- Verify ChromaDB persists to `./data/chroma_db/`

### Phase 2: Write Path (before testing queries)
- Integrate embedding generation into article fetch flow
- After `storage.store_article()` succeeds in crawl, call `vector_storage.add_embedding()`
- Add CLI command `reindex` to batch-generate embeddings for existing articles
- Handle duplicate IDs gracefully (upsert or skip)

### Phase 3: Query Path (requires write path)
- Add `search --semantic` CLI command
- Add `article related <id>` CLI command
- Implement result pagination (ChromaDB returns ordered by similarity)

### Phase 4: Polish
- Error handling for missing embeddings (articles before v1.8)
- Batch embedding for performance (sentence-transformers supports batch encode)
- Progress reporting for `reindex` command

---

## Scaling Considerations

| Scale | ChromaDB Behavior |
|-------|------------------|
| 0-10K articles | ChromaDB embedded mode handles easily. all-MiniLM-L6-v2 is fast on CPU. |
| 10K-100K articles | Query latency may increase. Consider adding `where` filters to reduce search space. |
| 100K+ articles | May need to switch to client-server Chroma deployment with more RAM. |

**For this project:** Embedded mode is appropriate. The target corpus is personal-scale (thousands of articles, not millions).

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Storing Embeddings in SQLite

**What people do:** Try to store embedding vectors as BLOBs in SQLite to "keep everything in one place."
**Why it's wrong:** SQLite is not designed for vector operations. ChromaDB provides HNSW indexing for fast similarity search; SQLite cannot do this efficiently.
**Do this instead:** Accept two data stores. SQLite + ChromaDB is not a problem, it's the correct architecture.

### Anti-Pattern 2: Generating Embeddings Synchronously During Fetch

**What people do:** Call `model.encode()` synchronously inside the crawl loop.
**Why it's wrong:** Sentence-transformers model loading is slow (~seconds on first call). Blocking the fetch pipeline makes users wait.
**Do this instead:** Load model once at startup (lazy singleton pattern). Generate embeddings after article is stored.

### Anti-Pattern 3: Re-embedding on Every Query

**What people do:** Re-encode the query text on every search without caching.
**Why it's wrong:** While encoding is faster than search, it still adds latency.
**Do this instead:** Encode query on-demand (fast, ~10-50ms). For high-frequency queries, consider caching, but unlikely needed for personal use.

### Anti-Pattern 4: Storing Full Article Text in ChromaDB

**What people do:** Pass entire article content as `documents` parameter.
**Why it's wrong:** ChromaDB stores documents for you, but SQLite already has the full content. Duplication wastes ChromaDB storage.
**Do this instead:** Store only the content reference (article_id) in ChromaDB. Retrieve full content from SQLite when displaying results.

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| ChromaDB PersistentClient with `./data/chroma_db/` | Matches "纯本地应用" constraint. No external service needed. |
| all-MiniLM-L6-v2 model | 384-dim vectors (small), fast on CPU, good quality, auto-downloaded by ChromaDB |
| Separate `src/embedding.py` service | Single responsibility, testable, swappable (could use OpenAI embeddings later) |
| Separate `src/storage/vector.py` | Mirrors existing `sqlite.py` storage pattern. ChromaDB lifecycle in one place. |
| Article ID as ChromaDB document ID | Enables cross-reference between ChromaDB results and SQLite articles |
| Batch reindex command | Existing articles need embeddings too. Cannot just do new articles. |

---

## Gaps / Phase-Specific Research Needed

- **Batch embedding performance:** sentence-transformers supports `model.encode(list_of_texts)` - verify batch size for optimal throughput
- **ChromaDB upsert behavior:** If `add` is called with an existing ID, does it update or error? Need to verify
- **Metadata filtering:** ChromaDB supports `where` clauses on metadata - could filter by feed_id for feed-specific search

---

## Sources

- [ChromaDB PyPI (v1.5.5, March 2026)](https://pypi.org/project/chromadb/) — HIGH confidence
- [ChromaDB Embedding Functions Docs](https://docs.trychroma.com/docs/embeddings/embedding-functions) — HIGH confidence
- [sentence-transformers PyPI](https://pypi.org/project/sentence-transformers/) — HIGH confidence
- [ChromaDB GitHub](https://github.com/chroma-core/chroma) — MEDIUM confidence (PyPI more authoritative for API)

---

*Architecture research for: ChromaDB semantic search integration*
*Researched: 2026-03-26*
