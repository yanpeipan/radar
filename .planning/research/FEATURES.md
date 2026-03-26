# Feature Research: Semantic Search & Related Articles

**Domain:** Personal RSS reader with vector semantic search
**Researched:** 2026-03-26
**Confidence:** MEDIUM (web search tools unavailable, used WebFetch on official docs + training data)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Semantic search query | Users want natural language search, not just keyword matching | MEDIUM | Requires embedding generation + ChromaDB query |
| Related articles | "More like this" is standard UX for content consumption | MEDIUM | Similarity search using article embedding |
| Search result relevance ranking | Results should be ordered by relevance | LOW | ChromaDB returns ordered results by default |
| Hybrid search (keyword + semantic) | Users may want exact matches AND semantic matches | HIGH | FTS5 already exists, combining adds complexity |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Incremental embedding on fetch | New articles automatically become searchable semantically | MEDIUM | Hook into fetch pipeline, batch embedding generation |
| Feed-filtered semantic search | "Only show me articles similar to X within feed Y" | LOW | ChromaDB supports metadata filtering via `where` clause |
| Semantic tag suggestions | "This article seems related to tags [A, B]" | MEDIUM | Uses similarity against tag clusters |
| Cross-feed discovery | Find related content across different feeds | LOW | Natural outcome of semantic search across all articles |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time semantic search | Instant results as you type | Embedding generation is expensive, CPU-bound | Debounced search with progress indicator |
| Full LLM summarization of results | "AI-powered insights" | API cost, latency, complexity | Pre-computed summaries on demand |
| Collaborative filtering | "Users like you also read..." | Requires user data, multi-user architecture | Tag-based similarity (already exists) |
| Automatic article categorization | "Put this in category X" | Taxonomy management overhead | Use semantic search + existing tags |

## Feature Dependencies

```
Semantic Search CLI
    └──requires──> Embedding Generation Service
                        └──requires──> sentence-transformers model
                        └──requires──> ChromaDB collection

Article Related
    └──requires──> Embedding Generation Service (same)
    └──requires──> Existing article embedding (in ChromaDB)

Incremental Embedding
    └──requires──> Semantic Search CLI (same service)
    └──triggered by──> fetch --all (new articles)
```

### Dependency Notes

- **Semantic search requires embedding generation:** The `all-MiniLM-L6-v2` model must be loaded and used to encode query text. First query has model loading overhead (~2-5 seconds).
- **Related articles requires existing embedding:** If an article was stored before ChromaDB integration, it has no embedding. Need migration strategy.
- **ChromaDB is separate from SQLite:** Vectors stored in ChromaDB (`chroma.sqlite`), not in existing `articles.db`. Data remains synchronized via article ID.

## MVP Definition

### Launch With (v1.8)

Minimum viable product -- what is needed to validate the concept.

- [ ] `search --semantic "query"` -- Semantic search using sentence-transformers + ChromaDB. Returns top-k similar articles by cosine similarity. **Why essential:** Core value proposition of the milestone.
- [ ] `article related <id>` -- Find articles similar to a given article ID. **Why essential:** Natural companion to semantic search; validates embedding quality.
- [ ] Incremental embedding on fetch -- New articles automatically generate embeddings and store in ChromaDB. **Why essential:** Without this, semantic search degrades over time as new content lacks embeddings.
- [ ] Progress indicator for embedding generation -- Users should see feedback during batch embedding. **Why essential:** Embedding generation is slow; silent failure frustrates users.

### Add After Validation (v1.x)

Features to add once core is working.

- [ ] `search "query" --hybrid` -- Combine FTS5 keyword results with semantic reranking. **Trigger:** User feedback requesting exact-match searches.
- [ ] Batch backfill embedding -- CLI command to generate embeddings for existing articles. **Trigger:** Users want to search old content semantically.
- [ ] Feed-filtered semantic search -- `search --semantic "query" --feed-id X`. **Trigger:** Users with many feeds want scoped discovery.

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] Semantic tag clustering -- Auto-discover tag groups via embedding similarity. **Why defer:** Existing DBSCAN clustering works; marginal benefit unclear.
- [ ] Topic modeling / dimensionality reduction -- Visualize article landscape. **Why defer:** Visualization outside CLI scope; would need web UI.
- [ ] LLM-powered search refinement -- Rewrite queries for better retrieval. **Why defer:** API dependency, cost, complexity.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Semantic search CLI | HIGH | MEDIUM | P1 |
| Related articles | HIGH | LOW | P1 |
| Incremental embedding | HIGH | MEDIUM | P1 |
| Progress indicator | MEDIUM | LOW | P1 |
| Hybrid search | MEDIUM | HIGH | P2 |
| Backfill embedding | MEDIUM | MEDIUM | P2 |
| Feed-filtered search | MEDIUM | LOW | P2 |
| Semantic tag clustering | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## CLI UX Patterns

### Existing CLI Patterns (from codebase review)

The current CLI follows these conventions:

```
article list [--limit] [--feed-id] [--tag] [--tags] [--verbose]
article view <article_id> [--verbose]
article open <article_id>
article tag [<article_id> <tag_name>] [--auto] [--rules]
search <query> [--limit] [--feed-id]
```

- Top-level commands: `feed`, `article`, `search`, `fetch`
- Article subcommands: `list`, `view`, `open`, `tag`
- Options use `--flag` syntax
- Required arguments use positional syntax
- Error output uses `click.secho(..., fg="red")`

### Semantic Search CLI Proposal

**Option A: Separate command (cleanest)**
```
search --semantic "query" [--limit] [--feed-id]
```
- Pros: Clear separation from keyword search
- Cons: Two separate commands for related functionality

**Option B: Flag on existing search**
```
search "query" [--semantic] [--limit] [--feed-id]
```
- Pros: Single command, easy to switch between keyword/semantic
- Cons: Semantic search is architecturally different (requires embedding), may confuse users expecting similar behavior

**Option C: Subcommand**
```
search semantic "query" [--limit] [--feed-id]
search keyword "query" [--limit] [--feed-id]
```
- Pros: Explicit, extensible (could add `search hybrid`)
- Cons: More verbose

**Recommendation: Option B** -- The existing `search` command is FTS5-only. Adding a `--semantic` flag clearly indicates the mode. Users can experiment easily.

### Related Articles CLI Proposal

**Proposed syntax:**
```
article related <article_id> [--limit] [--feed-id]
```

- Uses `article` as parent (consistent with `article view`, `article open`)
- `related` subcommand follows pattern of sibling subcommands
- Options match semantic search: `--limit`, `--feed-id`

### Embedding Generation Feedback

**During fetch (automatic):**
```
Fetching feed: Example Feed... 5 new articles
Generating embeddings... [████████████░░░░] 12s
```

**Backfill command (manual):**
```
$ rss-reader embed --all
Generating embeddings for 2479 existing articles...
[████████████████████████████] 4m 32s
Done. 2479 articles embedded.
```

## ChromaDB Integration Patterns

### Collection Configuration

```python
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

# Default uses all-MiniLM-L6-v2 (384 dimensions)
client = chromadb.PersistentClient(path="./data/chroma")
collection = client.create_collection(
    name="articles",
    embedding_function=DefaultEmbeddingFunction()
)
```

### Adding Article Embeddings

```python
# Batch add for incremental updates
collection.add(
    ids=[article_id],
    documents=[article_content],  # title + description + content
    metadatas=[{
        "feed_id": feed_id,
        "pub_date": pub_date,
        "url": link
    }]
)
```

### Semantic Search Query

```python
# Query by text (ChromaDB embeds automatically)
results = collection.query(
    query_texts=["machine learning optimization"],
    n_results=10,
    where={"feed_id": feed_id},  # optional filter
    include=["documents", "metadatas", "distances"]
)
```

### Related Articles Query

```python
# Get embedding for source article
article_embedding = collection.get(ids=[article_id])["embeddings"][0]

# Find similar articles
results = collection.query(
    query_embeddings=[article_embedding],
    n_results=6,  # 5 + source article
    include=["documents", "metadatas", "distances"]
)
# Exclude source article from results
```

## Competitor Feature Analysis

| Feature | Feedly | Miniflux | Fresh RSS | Our Approach |
|---------|--------|----------|-----------|--------------|
| Keyword search | FULL-TEXT | FULL-TEXT | FULL-TEXT (plugin) | FTS5 (existing) |
| Semantic search | AI Pro addon | NOT AVAILABLE | NOT AVAILABLE | Native via ChromaDB |
| Related articles | "More like this" | NOT AVAILABLE | NOT AVAILABLE | `article related` |
| Search filters | Feed, tag, date | Feed, tag, status | Feed, tag | Feed ID (existing) |
| Embedding model | OpenAI | N/A | N/A | sentence-transformers (local) |

**Key insight:** Semantic search and related articles are NOT table stakes in RSS readers. Most competitors either lack them entirely or offer as paid/Cloud-only features. This is a genuine differentiator for a personal, local-first tool.

## Sources

- [ChromaDB Query Documentation](https://docs.trychroma.com/docs/querying-collections/query-and-get) (HIGH confidence)
- [ChromaDB Add Data Documentation](https://docs.trychroma.com/docs/collections/add-data) (HIGH confidence)
- [ChromaDB Embeddings Documentation](https://docs.trychroma.com/docs/embeddings) (HIGH confidence)
- [SBERT Pretrained Models](https://www.sbert.net/docs/pretrained_models.html) (HIGH confidence)
- [LangChain RAG Tutorial](https://docs.langchain.com/oss/python/langchain/rag) (MEDIUM confidence)
- [PrivateGPT Architecture](https://github.com/imartinez/privateGPT) (MEDIUM confidence)

---
*Feature research for: ChromaDB semantic search in RSS reader*
*Researched: 2026-03-26*
