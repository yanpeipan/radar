# Phase 31: Write Path - Incremental Embedding - Context

**Gathered:** 2026-03-27 (skipping discuss - builds directly on Phase 30 infrastructure)
**Status:** Ready for planning

<domain>
## Phase Boundary

Integrate ChromaDB embedding generation into the article fetch flow so new articles automatically generate embeddings during fetch. After `store_article_async()` succeeds in `fetch_one_async()`, call a new ChromaDB storage function to add the article embedding. This is the write path for semantic search — no CLI queries yet (Phase 32).
</domain>

<decisions>
## Implementation Decisions

### ChromaDB Write Integration (D-08)
- **New function** `add_article_embedding(article_id, title, content, url)` in `src/storage/vector.py` that:
  - Takes article_id, title, content, and url
  - Embeds the content (or title+description for short content)
  - Adds to ChromaDB "articles" collection via `.add()`

### Integration Point (D-09)
- Call `add_article_embedding()` in `src/application/fetch.py` `fetch_one_async()` right after `store_article_async()` succeeds
- Tag rules applied AFTER store, embedding should follow same pattern — applied right after store

### Content for Embedding (D-10)
- Use article content field primarily; fall back to description if content is empty/short
- Title is stored as metadata, not as the embedding text
- URL stored as metadata

### ChromaDB Collection Schema (from Phase 30 D-06)
- Collection "articles" with: id (article_id), content (embedding text), title, url
- Already established in Phase 30

### Async Handling
- Embedding generation should be synchronous (CPU-bound) or use `asyncio.to_thread()` to avoid blocking
- ChromaDB client is thread-safe for writes

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Storage Layer
- `src/storage/__init__.py` — exports to add `add_article_embedding`
- `src/storage/vector.py` — existing ChromaDB client, add `add_article_embedding()` here
- `src/storage/sqlite.py` — `store_article_async()` at line 360

### Application Layer
- `src/application/fetch.py` — `fetch_one_async()` at line 22, integration point after `store_article_async()` (line 62)

### Models
- `src/models.py` — Article dataclass

### Phase 30 Context
- `.planning/phases/30-semantic-search-infrastructure/30-CONTEXT.md` — D-01 through D-07 (ChromaDB infrastructure)

</canonical_refs>

<codebase_context>
## Existing Code Insights

### Reusable Assets
- `src/storage/vector.py:get_chroma_collection()` — already returns configured "articles" collection
- `src/storage/vector.py:get_embedding_function()` — returns SentenceTransformer for encoding
- `src/application/fetch.py` — already has hook after `store_article_async()` for tag rules

### Integration Pattern
- Similar to how `apply_rules_to_article()` is called after `store_article_async()` in `fetch_one_async()` (lines 79-86)
- Embedding should follow the same pattern: called right after successful store

### ChromaDB add() API
- Collection `.add()` takes: ids (list), documents (list), metadatas (list)
- Each must be same length
- Documents are the text to embed

</codebase_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

- Batch backfill of existing articles (deferred to future CLI command)
- Feed-filtered semantic search (Phase 32 scope)
- Hybrid search (Phase 32 scope)

</deferred>
