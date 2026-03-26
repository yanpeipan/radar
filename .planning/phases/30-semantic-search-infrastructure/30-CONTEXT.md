# Phase 30: Semantic Search Infrastructure - Context

**Gathered:** 2026-03-26 (assumptions mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

Setup ChromaDB infrastructure for semantic search: PersistentClient singleton, sentence-transformers embedding service, model pre-download at startup. This is pure infrastructure — no article embeddings are generated yet (that comes in Phase 31).

</domain>

<decisions>
## Implementation Decisions

### ChromaDB Client Location
- **D-01:** ChromaDB PersistentClient instantiated in `src/storage/` as module-level singleton, initialized on first CLI command call (same pattern as `get_db()`)

### ChromaDB Storage Directory
- **D-02:** ChromaDB data stored in `~/.local/share/rss-reader/chroma/` alongside SQLite — use `platformdirs.user_data_dir(appname="rss-reader")` + `/chroma` subdirectory

### Embedding Function (all-MiniLM-L6-v2)
- **D-03:** ChromaDB uses `sentence_transformers.SentenceTransformer("all-MiniLM-L6-v2")` as embedding function — same model already used in `src/tags/ai_tagging.py`

### Model Pre-Download at Startup
- **D-04:** Model pre-download triggered during CLI startup in `src/cli/__init__.py` alongside `init_db()` — meets SEM-03 requirement (not on first query)

### Coexistence with sqlite-vec
- **D-05:** ChromaDB added alongside existing sqlite-vec embedding storage, not replacing it — preserves AI auto-tagging in `src/tags/ai_tagging.py`

### ChromaDB Collection
- **D-06:** ChromaDB collection named `"articles"` with article ID, content, title, url metadata

### API Design
- **D-07:** `src/storage/__init__.py` exports ChromaDB functions alongside existing storage API

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Storage Layer (existing)
- `src/storage/__init__.py` — Public storage API exports (to add ChromaDB exports)
- `src/storage/sqlite.py` — Current storage with `get_db()` pattern, embedding functions
- `src/tags/ai_tagging.py` — Existing sentence-transformers usage (lines 33, 45)

### CLI Layer
- `src/cli/__init__.py` — Startup initialization (lines 23-29) — add model pre-download here

### Models
- `src/models.py` — Article dataclass

### Research
- `planning/research/SUMMARY.md` — ChromaDB integration patterns, pitfalls
- `planning/research/STACK.md` — chromadb 1.5.5, sentence-transformers 5.3.0
- `planning/research/PITFALLS.md` — File descriptor leaks, HNSW corruption, model download delay

</canonical_refs>

<codebase_context>
## Existing Code Insights

### Reusable Assets
- `src/storage/sqlite.py:get_db()` pattern — module-level singleton with context manager
- `src/tags/ai_tagging.py:_get_model()` — existing sentence-transformers model loading
- `src/tags/ai_tagging.py` already uses `"all-MiniLM-L6-v2"` — same model for ChromaDB

### Established Patterns
- Storage layer boundary: all data operations in `src/storage/`
- Startup initialization in `src/cli/__init__.py`
- Module-level singletons for clients

### Integration Points
- `src/cli/__init__.py` — startup hook for model pre-download
- `src/storage/__init__.py` — add ChromaDB exports
- `src/storage/` — new `vector.py` module for ChromaDB operations

</codebase_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — analysis stayed within phase scope

</deferred>
