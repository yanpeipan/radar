# Stack Research

**Domain:** Vector Semantic Search for Python CLI RSS Reader
**Researched:** 2026-03-26
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **chromadb** | 1.5.5 | Vector database for article embeddings | Local-first, persistent storage, zero-config embedding handling. ChromaDB's default embedding function uses sentence-transformers `all-MiniLM-L6-v2` automatically. |
| **sentence-transformers** | 5.3.0 | Generate article and query embeddings | Industry standard for sentence-level embeddings. 15,000+ pretrained models on HuggingFace. Project already declares this in `[ml]` extras. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **torch** | >=2.0.0 | Backend for sentence-transformers | Required for sentence-transformers inference. Project already declares in `[ml]` extras. |
| **transformers** | >=4.40.0 | Model loading for sentence-transformers | Required dependency of sentence-transformers. Project already declares in `[ml]` extras. |
| **safetensors** | >=0.4.3 | Fast model loading | Faster model loading than pickle. Already declared in `[ml]` extras. |
| **onnxruntime** | (via sentence-transformers[onnx]) | Faster CPU inference | Optional: 2-3x speedup for embedding generation on CPU. Install with `pip install sentence-transformers[onnx]` if embedding speed becomes a concern. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **pytest** | Testing | Already in project with 85 tests. Add tests for ChromaDB integration. |
| **pytest-asyncio** | Async test support | Already present for async fetch tests. |

## Installation

```bash
# Core ML dependencies (already in pyproject.toml [ml] extras)
pip install sentence-transformers[onnx]>=3.0.0
pip install chromadb>=1.5.5

# Existing project dependencies already include:
# - torch>=2.0.0
# - transformers>=4.40.0
# - safetensors>=0.4.3
```

## Integration with Existing Architecture

### ChromaDB vs SQLite Role Separation

| System | Purpose | Storage |
|--------|---------|---------|
| **SQLite (existing)** | Article metadata, content, FTS5 keyword search | `~/.rss-reader/articles.db` |
| **ChromaDB (new)** | Semantic embeddings for similarity search | `~/.rss-reader/chroma_db/` |

ChromaDB does NOT replace SQLite. It stores vector embeddings indexed by article ID, while SQLite remains the source of truth for article content.

### Recommended Integration Pattern

```python
import chromadb
from chromadb.utils import sentence_transformers

# Local persistent storage in app data directory
# Use app's config directory (platformdirs already in project)
chroma_client = chromadb.PersistentClient(path=str(chroma_db_path))

# Collection for articles — ChromaDB uses sentence-transformers
# all-MiniLM-L6-v2 by default (384-dim embeddings)
collection = chroma_client.get_or_create_collection(
    name="articles",
    metadata={"description": "Article semantic embeddings"}
)

# Add article embedding
collection.add(
    ids=[article_id],           # nanoid from existing articles
    documents=[article_content], # Full text or title+content
    metadatas=[{"title": article.title, "url": article.url}]
)

# Semantic search returns article IDs
results = collection.query(
    query_texts=[search_query],
    n_results=10
)
article_ids = results["ids"][0]
```

### Data Flow

```
New article → SQLite (existing) → Generate embedding (sentence-transformers) → ChromaDB
Search query → Embedding (sentence-transformers) → ChromaDB similarity search → Article IDs → SQLite lookup → Display
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| chromadb | faiss-cpu | If you need more control over indexing algorithms or expect >1M vectors. faiss is more manual. |
| chromadb | qdrant | If you need a server-based vector DB. Overkill for single-user CLI. |
| sentence-transformers | openai embeddings | Requires API key, not local-first. sentence-transformers is the right local choice. |
| all-MiniLM-L6-v2 | all-mpnet-base-v2 | Use mpnet for higher quality at 2x speed cost. MiniLM is the right default for CLI responsiveness. |
| ONNX (optional) | None | Skip if startup time is acceptable. Add if embedding generation is a bottleneck. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| ChromaDB HttpClient | Requires running a Chroma server process. Overcomplicates a local CLI. | PersistentClient with local path |
| ChromaDB OpenAI/Cohere embedding functions | Require API keys, not local-first. | Built-in sentence-transformers (default) |
| pgvector | Requires PostgreSQL server. Violates SQLite-only constraint. | chromadb |
| torch with GPU | No GPU on typical CLI deployment. | CPU inference with ONNX optimization if needed |

## Stack Patterns by Variant

**For initial implementation:**
- Use `chromadb.PersistentClient` with local path
- Use ChromaDB's default embedding function (sentence-transformers `all-MiniLM-L6-v2`)
- No ONNX needed initially

**If embedding speed becomes a bottleneck (large corpus >10K articles):**
- Add `sentence-transformers[onnx]` for 2-3x CPU speedup
- Pre-compute embeddings for all existing articles in background

**If semantic quality is insufficient:**
- Replace `all-MiniLM-L6-v2` with `all-mpnet-base-v2` (768-dim, better quality, slower)

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| chromadb 1.5.5 | Python >=3.9 | Confirmed via PyPI |
| sentence-transformers 5.3.0 | Python >=3.10 | Project requires >=3.10, compatible |
| torch >=2.0.0 | sentence-transformers 5.3.0 | Required dependency |
| transformers >=4.40.0 | sentence-transformers 5.3.0 | Required dependency |

**Note:** Project Python requirement (`>=3.10`) is compatible with both chromadb (`>=3.9`) and sentence-transformers (`>=3.10`).

## Sources

- [PyPI chromadb 1.5.5](https://pypi.org/project/chromadb/) — Latest version (March 10, 2026), Python >=3.9
- [PyPI sentence-transformers 5.3.0](https://pypi.org/project/sentence-transformers/) — Latest version (March 12, 2026), Python >=3.10, ONNX extras confirmed
- [ChromaDB Documentation: Clients](https://docs.trychroma.com/docs/run-chroma/clients) — PersistentClient usage confirmed
- [ChromaDB Documentation: Embeddings](https://docs.trychroma.com/docs/embeddings/embedding-functions) — Default sentence-transformers integration confirmed
- [ChromaDB GitHub](https://github.com/chroma-core/chroma) — Custom embedding function pattern confirmed
- [sentence-transformers Documentation](https://www.sbert.net/docs/) — Model choices and optimization options

---

*Stack research for: ChromaDB vector search integration*
*Researched: 2026-03-26*
