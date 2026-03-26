# Project Research Summary

**Project:** ChromaDB Semantic Search Integration
**Domain:** Vector semantic search for Python CLI RSS reader
**Researched:** 2026-03-26
**Confidence:** MEDIUM (Stack HIGH, Features/Architecture/Pitfalls MEDIUM)

## Executive Summary

This project adds vector semantic search to an existing Python RSS reader using ChromaDB and sentence-transformers. The approach is to layer ChromaDB alongside the existing SQLite database: SQLite remains the source of truth for article metadata and content (including FTS5 keyword search), while ChromaDB stores vector embeddings for semantic similarity search. This is not a replacement architecture but a co-existence pattern where each storage system handles what it does best.

The recommended stack is straightforward: `chromadb` for vector storage (PersistentClient with local path), `sentence-transformers` with the `all-MiniLM-L6-v2` model for embedding generation. These libraries are already declared in the project's ML extras, reducing integration friction. The critical insight from architecture research is that ChromaDB runs embedded in-process like SQLite, requiring no external service, which aligns with the project's "pure local application" constraint.

The main risks are ChromaDB operational bugs (file descriptor leaks, HNSW corruption under concurrent access, orphaned storage files) and the first-query model download delay. These are manageable: use single-process PersistentClient, pre-warm the model at startup, and implement cleanup routines for orphaned files. The feature research confirms semantic search and related articles are genuine differentiators in the RSS reader space - most competitors lack these capabilities entirely or offer them only as paid cloud features.

## Key Findings

### Recommended Stack

The stack centers on two primary libraries with clear roles:

**Core technologies:**
- **chromadb 1.5.5** -- Vector database for article embeddings -- Local-first, zero-config, embedded mode matches SQLite constraint
- **sentence-transformers 5.3.0** -- Embedding generation -- Industry standard, 384-dim all-MiniLM-L6-v2 model auto-selected by ChromaDB
- **torch >=2.0.0** -- Backend for sentence-transformers -- Already in project ML extras
- **transformers >=4.40.0** -- Model loading -- Dependency of sentence-transformers, already declared

**ChromaDB vs SQLite role separation:**
- SQLite (`articles.db`) -- Article metadata, content, FTS5 keyword search
- ChromaDB (`chroma_db/`) -- Semantic embeddings for similarity search, indexed by article ID

### Expected Features

**Must have (table stakes):**
- `search --semantic "query"` -- Natural language search using embeddings -- Core value proposition
- `article related <id>` -- Find semantically similar articles -- Validates embedding quality
- Incremental embedding on fetch -- New articles automatically embedded -- Prevents search degradation
- Progress indicator for embedding generation -- Feedback during slow operations -- Critical UX

**Should have (competitive):**
- `search "query" --hybrid` -- Combine FTS5 + semantic reranking -- High complexity, user-request driven
- Batch backfill embedding (`reindex` command) -- Generate embeddings for existing articles -- Essential for full functionality
- Feed-filtered semantic search -- Scope search to specific feed -- Low complexity via ChromaDB metadata filtering

**Defer (v2+):**
- Semantic tag clustering -- Auto-discover tag groups -- Existing DBSCAN works, marginal benefit unclear
- Topic modeling / dimensionality reduction -- Visualize article landscape -- Outside CLI scope
- LLM-powered search refinement -- Rewrite queries for better retrieval -- API dependency, cost, complexity

### Architecture Approach

The system follows a layered architecture: CLI commands sit atop a storage layer with two co-existing databases (SQLite for articles, ChromaDB for embeddings), with an embedding service using sentence-transformers below. ChromaDB runs in embedded mode via `PersistentClient`, storing data in a local directory alongside the existing SQLite database. Article IDs (nanoid format) serve as the cross-reference key between both stores.

**Major components:**
1. `src/embedding.py` (NEW) -- sentence-transformers wrapper, lazy-loaded model singleton
2. `src/storage/vector.py` (NEW) -- ChromaDB client lifecycle, collection CRUD, query methods
3. `src/storage/sqlite.py` (EXISTING, unchanged) -- Article storage, FTS5
4. CLI commands (`search.py`, `article.py`) (MODIFY) -- Add `--semantic` flag, `related` subcommand

### Critical Pitfalls

1. **SQLite file descriptor leaks** -- ChromaDB opens connections without closing them. Mitigation: single-process mode, high `ulimit -n`, monitor with `lsof`
2. **Embedding function not persisted** -- Collection loses custom embedding function after restart. Mitigation: always pass `embedding_function` when getting collection
3. **Model download on first query** -- 90MB download causes 30+ second delay. Mitigation: pre-download and warmup at startup
4. **HNSW index corruption** -- Concurrent read/write corrupts index. Mitigation: single-threaded writes, application-level locking
5. **Query parameter in-place mutation** -- `include` list mutated across calls. Mitigation: always pass fresh list object

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Infrastructure Foundation
**Rationale:** Cannot test write or query paths without dependencies installed and core services initialized. ChromaDB setup must be correct before any articles are added.
**Delivers:** Dependencies installed, `src/embedding.py` (model loading/warmup), `src/storage/vector.py` (ChromaDB client), ChromaDB persistence verified at `./data/chroma_db/`
**Avoids:** Pitfall 2 (embedding function persistence) -- initialize collections with correct embedding function from start; Pitfall 3 (model download timeout) -- pre-download model at startup

### Phase 2: Write Path (Article Fetch Integration)
**Rationale:** Semantic search requires embeddings to exist. The write path must be working before query path can be validated. Backfill capability needed for existing articles.
**Delivers:** Embedding generation integrated into article fetch flow, `reindex` command for batch backfill, progress indicator for embedding generation
**Implements:** After `storage.store_article()` succeeds, call `vector_storage.add_embedding()`
**Avoids:** Pitfall 4 (HNSW corruption) -- single-threaded writes; Orphaned files from article deletion -- implement cleanup alongside

### Phase 3: Query Path (Semantic Search CLI)
**Rationale:** Query path depends on write path (Phase 2). Must verify embeddings exist and are queryable before building UI around results.
**Delivers:** `search --semantic` command, `article related <id>` command, result rendering with similarity scores
**Implements:** ChromaDB query returning article IDs, SQLite lookup for full article objects, CLI output
**Avoids:** Pitfall 5 (query parameter mutation) -- always use fresh list for `include` parameter

### Phase 4: Polish and Error Handling
**Rationale:** Handle edge cases discovered during integration. Performance optimization once basic flow works.
**Delivers:** Error handling for missing embeddings (articles before v1.8), batch embedding performance optimization, cleanup routine for orphaned ChromaDB storage files
**Avoids:** UX pitfalls (first query slowness, empty results confusion) -- progress indicators and clear labeling

### Phase Ordering Rationale

- **Infrastructure before write before query:** Clear dependency chain. Query path requires embeddings from write path; write path requires ChromaDB infrastructure from Phase 1.
- **Single-threaded writes established early:** HNSW corruption is a data-integrity issue; prevention in Phase 2 before concurrent access is attempted.
- **Model warmup at startup:** Prevents first-query timeout from becoming a user experience disaster. Startup latency acceptable, mid-search freeze is not.
- **Cleanup alongside storage:** Orphaned files accumulate silently. Building cleanup into Phase 2 (not Phase 4) prevents disk usage growth from being overlooked.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Write Path):** Batch embedding performance -- sentence-transformers `encode(list)` optimal batch size needs verification; ChromaDB upsert behavior (update vs error on duplicate ID) needs testing
- **Phase 4 (Polish):** asyncio + ChromaDB thread safety details -- need to verify exact behavior with project's async fetch pipeline

Phases with standard patterns (skip research-phase):
- **Phase 1 (Infrastructure):** ChromaDB PersistentClient pattern is well-documented; embedding function configuration is established
- **Phase 3 (Query Path):** ChromaDB query API is stable; result rendering follows existing CLI patterns

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Verified via PyPI, official docs, version compatibility confirmed |
| Features | MEDIUM | Web search unavailable; used WebFetch on official docs + training data |
| Architecture | MEDIUM | Documentation fragmented (PyPI/main docs not fully aligned); core patterns verified via official sources |
| Pitfalls | MEDIUM | Primarily GitHub issues (community-reported bugs); some gaps in official documentation |

**Overall confidence:** MEDIUM

The stack is solid and well-verified. Feature set and architecture are well understood with clear patterns. Pitfalls research is comprehensive (six critical pitfalls documented with GitHub issues), but some ChromaDB operational behaviors (upsert, concurrent access specifics) need on-the-ground validation during implementation.

### Gaps to Address

- **Batch embedding performance:** sentence-transformers `encode(list_of_texts)` batch size optimization not verified -- test during Phase 2
- **ChromaDB upsert behavior:** If `add` called with existing ID, does it update or error? Needs verification before Phase 2
- **asyncio + ChromaDB thread safety:** Project uses async httpx for fetching; interaction with ChromaDB threading model needs explicit testing during Phase 2 or 4

## Sources

### Primary (HIGH confidence)
- [PyPI chromadb 1.5.5](https://pypi.org/project/chromadb/) -- Stack recommendations, version compatibility
- [PyPI sentence-transformers 5.3.0](https://pypi.org/project/sentence-transformers/) -- Stack recommendations, version compatibility
- [ChromaDB GitHub Issue #4039](https://github.com/chroma-core/chroma/issues/4039) -- File descriptor leak pitfall
- [ChromaDB GitHub Issue #3486](https://github.com/chroma-core/chroma/issues/3486) -- HNSW corruption pitfall
- [ChromaDB GitHub Issue #5857](https://github.com/chroma-core/chroma/issues/5857) -- Query parameter mutation pitfall
- [ChromaDB GitHub Issue #6021](https://github.com/chroma-core/chroma/issues/6021) -- Embedding function persistence pitfall
- [ChromaDB GitHub Issue #5520](https://github.com/chroma-core/chroma/issues/5520) -- Collection deletion orphan files pitfall

### Secondary (MEDIUM confidence)
- [ChromaDB Query Documentation](https://docs.trychroma.com/docs/querying-collections/query-and-get) -- Feature implementation patterns
- [ChromaDB Embeddings Documentation](https://docs.trychroma.com/docs/embeddings) -- Embedding function configuration
- [sentence-transformers Documentation](https://www.sbert.net/docs/) -- Model selection
- [LangChain RAG Tutorial](https://docs.langchain.com/oss/python/langchain/rag) -- Integration patterns reference

### Tertiary (LOW confidence)
- [PrivateGPT Architecture](https://github.com/imartinez/privateGPT) -- Alternative integration approaches (needs validation against actual ChromaDB API)

---
*Research completed: 2026-03-26*
*Ready for roadmap: yes*
