# Codebase Concerns

**Analysis Date:** 2026-03-31

## Tech Debt

**Large Files (Complexity Risk):**
- `src/storage/sqlite/impl.py` - 902 lines. Handles DB operations, list_articles, FTS search. Consider splitting by concern (articles vs feeds).
- `src/providers/rss_provider.py` - 559 lines. RSS/Atom feed parsing. High complexity from multiple concerns.
- `src/storage/vector.py` - 522 lines. ChromaDB + embeddings. Consider extracting ChromaDB operations.
- `src/providers/webpage_provider.py` - 457 lines. Generic webpage extraction logic.

**Commented-Out Code Block:**
- `src/providers/rss_provider.py:530-555` - Large block of commented code for parallel validation. Dead code that should be removed or implemented.

**asyncio.run() Anti-Pattern:**
- `src/providers/rss_provider.py:369` - Uses `asyncio.run()` inside `discover()` method. This creates a new event loop each call and will fail if called from an existing event loop context. Should use `asyncio.get_event_loop().run_until_complete()` or restructure to avoid nesting.

**Global Mutable State (Thread Safety):**
- `src/storage/sqlite/impl.py:20-28` - Global `_db_write_lock` singleton. Initialization at module import time may cause issues with process forking.
- `src/storage/vector.py:31-33` - Global `_chroma_client`, `_embedding_function`, `_chroma_lock`. Same forking concerns.
- `src/utils/github.py:17` - Global `_github_client` singleton.
- `src/application/config.py:12` - Global `_settings` singleton.

**Bare `except Exception` Handlers (Observed 40+ instances):**
Locations include:
- `src/application/search.py:62`
- `src/application/feed.py:87,242,306`
- `src/application/fetch.py:42,53,95,122,216,220`
- `src/providers/rss_provider.py:156,317,513`
- `src/providers/__init__.py:52,108,121,123`
- `src/storage/vector.py:61,70,128,197,219,284,302,373`
- `src/discovery/deep_crawl.py:108,158,190`

**Impact:** Errors are silently swallowed, making debugging difficult. Specific exception types should be caught where possible.

**Synchronous SQLite in Async Context:**
- `src/storage/sqlite/impl.py:242-279` - `store_article_async()` uses `asyncio.to_thread()` for write serialization. Read operations (`list_articles`, `get_article`) are synchronous and will block the event loop during queries.

## Known Bugs

**No explicit TODO/FIXME comments found** in codebase.

**Potential Issue - DiscoveredFeed.valid always False on exception:**
- `src/providers/rss_provider.py:317-325` - On exception, returns `DiscoveredFeed` with `valid=False`. Caller may not handle this gracefully.

**Potential Issue - Silent Failure in Provider Loading:**
- `src/providers/__init__.py:52-53` - Silently catches all exceptions when loading provider modules. A broken provider will fail silently.

## Security Considerations

**URL Fetching (No Sanitization):**
- User-provided URLs are fetched via HTTP. No obvious SSRF protections in place.
- `src/utils/scraping_utils.py` fetches URLs without strict validation.
- Recommendation: Add URL allowlist/blocklist validation, especially for private IP ranges (10.x, 192.168.x, etc.).

**robots.txt Compliance:**
- `src/discovery/deep_crawl.py:190` - Uses `RobotExclusionRulesParser` but catches all exceptions silently, potentially crawling sites that should be excluded.
- Caching of robots.txt results for 1 hour (`robots_cache: TTLCache(maxsize=5000, ttl=3600)`) may not respect `Crawl-delay` directives.

**GitHub Token Exposure:**
- `src/utils/github.py` uses `os.environ.get("GITHUB_TOKEN")`. If set in environment, appears in process listing.
- Recommendation: Use a secrets manager or prompt for token at runtime.

**SQL Injection (Low Risk):**
- FTS queries in `src/storage/sqlite/impl.py` use f-strings for SQL construction (lines 816, 830, 847). SQLite parameter binding is used for values but the FTS query string itself is interpolated. Ensure `query` is sanitized before passing to FTS MATCH.

## Performance Bottlenecks

**Embedding Model Loading:**
- `src/storage/vector.py:127` - Model download happens on first semantic search if not cached. No preload verification at startup.
- `src/storage/vector.py:112` - CPU device used to avoid MPS issues, but CPU inference is slower than GPU.

**SQLite Query Performance:**
- `src/storage/sqlite/impl.py:601-614` - `list_articles()` joins `articles` and `feeds` tables with date filtering. Large datasets may slow without proper indexing.
- FTS5 `bm25()` scoring computed per-row in Python (`src/storage/sqlite/impl.py:871`) rather than in SQL.

**Async Concurrency Limits:**
- `src/application/fetch.py` uses `asyncio.Semaphore(10)` for concurrency limiting. Default of 10 concurrent fetches may be too conservative for high-latency feeds.

**ChromaDB Batch Operations:**
- `src/storage/vector.py:224-300` - `add_article_embeddings()` processes articles sequentially within the lock. Could be parallelized.

## Fragile Areas

**Deep Crawl BFS Implementation:**
- `src/discovery/deep_crawl.py` - BFS crawling with deque. URL normalization and visited-set tracking could have edge cases with query parameters and fragments.
- Line 41-52: URL normalization removes fragments and trailing slashes - may cause false deduplication for sites that use these differently.

**Feed Discovery Race Condition:**
- `src/providers/rss_provider.py:369` - Nested `asyncio.run()` in async context. If `discover()` is called while another async operation is running, this will raise `RuntimeError: asyncio.run() cannot be called from a running event loop`.

**SQLite WAL Mode:**
- `src/storage/sqlite/impl.py:65` - Uses WAL journal mode. Default timeout is 5 seconds. Under high concurrency, this may cause "database is locked" errors.

**Provider Priority System:**
- `src/providers/__init__.py` - Priority-based matching. If two providers match the same URL, only the highest priority wins. No fallback mechanism within a single fetch.

**Date Parsing Fallback Chain:**
- `src/storage/sqlite/impl.py:105-141` - `_normalize_published_at()` has multiple fallback strategies. If all fail, silently uses current time, potentially misrepresenting article dates.

## Scaling Limits

**SQLite Single File:**
- Current architecture uses single SQLite file. Recommended limit ~100GB database size before performance degrades.
- No sharding or replication support. All operations serialized through single connection pool.

**ChromaDB In-Memory with Persistence:**
- ChromaDB collection grows with article count. No eviction policy found.
- `src/storage/vector.py:148` - `get_or_create_collection()` with no size limits.

**Thread-Safe Global State:**
- `_chroma_lock` in `src/storage/vector.py` serializes all ChromaDB operations. At scale, this becomes a bottleneck.

## Dependencies at Risk

**feedparser:**
- Last major release ~2021. RSS/Atom parsing may miss newer feed features.
- No clear alternative with same feature set.

**scrapling:**
- Relatively new (2024). API may change. Version 0.4.x has deprecation warnings (`src/discovery/deep_crawl.py:21-22` disables scrapling logger).

**sentence-transformers + torch:**
- Heavy dependencies (~2GB disk, significant RAM). Model `all-MiniLM-L6-v2` cached locally but initial load is slow.
- `torch` has CUDA/MPS compatibility issues. Currently using CPU (`src/storage/vector.py:112`).

**httpx:**
- Listed in dependencies but appears to be replaced by `scrapling.Fetcher` per CLAUDE.md. May be unused.

## Missing Critical Features

**Error Recovery:**
- No retry logic for transient failures (network timeouts, 503s).
- 429 rate limit immediately returns None without retry (`src/discovery/parallel_probe.py:84-85`).

**Health Checks:**
- No startup verification of database, ChromaDB, or embedding model.
- Failures only detected on first use.

**Configuration Validation:**
- `src/application/config.py` uses Dynaconf but no schema validation.
- Missing required settings will fail at use time, not at startup.

**Graceful Degradation:**
- If ChromaDB fails, semantic search breaks entirely. No fallback to BM25-only search.
- If embedding model fails to load, no error handling path.

## Test Coverage Gaps

**Untested Core Modules:**
- `src/discovery/deep_crawl.py` - No tests found
- `src/discovery/parallel_probe.py` - No tests found
- `src/discovery/parser.py` - No tests found
- `src/discovery/common_paths.py` - No tests found

**Untested Provider Features:**
- `src/providers/github_release_provider.py` - No tests found
- `src/providers/webpage_provider.py` - No tests found
- `src/providers/default_provider.py` - No tests found

**Untested Application Layer:**
- `src/application/search.py` - No tests found
- `src/application/related.py` - No tests found
- `src/application/combine.py` - No tests found
- `src/application/rerank.py` - No tests found
- `src/application/articles.py` - No tests found (only thin wrapper)

**Test Structure Issues:**
- `tests/test_storage.py:75` - Uses `asyncio.run()` directly in test
- No integration tests covering full fetch-to-search flow
- No tests for error paths (network failures, malformed feeds)

---

*Concerns audit: 2026-03-31*
