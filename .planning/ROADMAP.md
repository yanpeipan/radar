# Roadmap: Personal Information System

## Milestones

- [x] **v1.0 MVP** — Phases 1-3 (shipped 2026-03-22)
- [x] **v1.1 GitHub Monitoring + Tagging** — Phases 4-8 (shipped 2026-03-23)
- [x] **v1.2 Article List Enhancements** — Phases 8.1-11 (shipped 2026-03-23)
- [x] **v1.3 Provider Architecture** — Phases 12-15 (shipped 2026-03-23)
- [x] **v1.4 Storage Layer Enforcement** — Phases 16-18 (shipped 2026-03-25)
- [x] **v1.5 uvloop并发支持** — Phases 19-22 (shipped 2026-03-25)
- [x] **v1.7 pytest测试框架** — Phases 26-29 (shipped 2026-03-25)
- [x] **v1.8 ChromaDB 语义搜索** — Phases 30-33 (shipped 2026-03-27)
- [x] **v1.9 Automatic Discovery Feed** — Phases 34-37 (shipped 2026-03-27)

- [x] **v1.10 uvloop Best Practices Review** — Phase 39 (shipped 2026-03-28)

- [x] **v1.11 Comprehensive uvloop Audit** — Phase 40 (shipped 2026-03-28)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-3) — SHIPPED 2026-03-22</summary>

- [x] Phase 1: Foundation (v1.0)
- [x] Phase 2: Search & Refresh (v1.0)
- [x] Phase 3: Web Crawling (v1.0)
  - [x] Phase 3.1: Fix httpx User-Agent (gap closure)

</details>

<details>
<summary>✅ v1.1 GitHub Monitoring + Tagging (Phases 4-8) — SHIPPED 2026-03-23</summary>

- [x] Phase 4: GitHub API Client + Releases Integration
- [x] Phase 5: Changelog Detection + Scraping
- [x] Phase 6: Unified Display + Refresh Integration
- [x] Phase 7: Tagging System
- [x] Phase 8: GitHub URL Metadata

</details>

<details>
<summary>✅ v1.2 Article List Enhancements (Phases 8.1-11) — SHIPPED 2026-03-23</summary>

- [x] Phase 8.1: Unified Feed Add (gap closure)
- [x] Phase 9: Enhanced Article List
- [x] Phase 10: Article Detail View
- [x] Phase 11: GitHub Release Tagging

</details>

<details>
<summary>✅ v1.3 Provider Architecture (Phases 12-15) — SHIPPED 2026-03-23</summary>

- [x] Phase 12: Provider Core Infrastructure (2/2 plans)
- [x] Phase 13: Provider Implementations + Tag Parsers (2/2 plans)
- [x] Phase 14: CLI Integration (3/3 plans)
- [x] Phase 15: PyGithub Refactor (2/2 plans)

</details>

<details>
<summary>✅ v1.4 Storage Layer Enforcement (Phases 16-18) — SHIPPED 2026-03-25</summary>

- [x] Phase 16: GitHubReleaseProvider (1/1 plans)
- [x] Phase 17: Anti-屎山 Refactoring (2/2 plans)
- [x] Phase 18: Storage Layer Enforcement (1/1 plans)

</details>

<details>
<summary>✅ v1.5 uvloop并发支持 (Phases 19-22) — SHIPPED 2026-03-25</summary>

- [x] Phase 19: uvloop Setup + crawl_async Protocol (completed 2026-03-25)
- [x] Phase 20: RSSProvider Async HTTP (completed 2026-03-24)
- [x] Phase 21: Concurrent Fetch + SQLite Serialization (completed 2026-03-25)
- [x] Phase 22: CLI Integration (completed 2026-03-25)

</details>

<details>
<summary>✅ v1.7 pytest测试框架 (Phases 26-29) — SHIPPED 2026-03-25</summary>

- [x] Phase 26: pytest框架搭建 (completed 2026-03-24)
- [x] Phase 27: Provider单元测试 (completed 2026-03-24)
- [x] Phase 28: Storage层单元测试 (completed 2026-03-25)
- [x] Phase 29: CLI集成测试 (completed 2026-03-25)

</details>

### 🚧 v1.9 Automatic Discovery Feed (Phases 34-37)

- [x] **Phase 34: Discovery Core Module** — HTML parsing, path probing, URL resolution, feed validation
- [x] **Phase 35: Discovery CLI Command** — `discover <url>` command (completed 2026-03-27)
- [x] **Phase 36: Feed Add Integration** — `--discover` and `--automatic` flags (completed 2026-03-27)
- [x] **Phase 37: Deep Crawling** — BFS crawler, robots.txt, CSS selector-based link discovery (completed 2026-03-27)

### Phase 38: Search Result Ranking
**Goal**: Implement multi-factor ranking algorithm for semantic search results combining normalized cosine similarity (50%), normalized freshness (30%), and configurable source weights (20%)
**Depends on**: Phase 30, Phase 31, Phase 32
**Requirements**: RANK-01
**Success Criteria** (what must be TRUE):
  1. `rank_semantic_results()` function exists in `src/application/search.py`
  2. Ranking formula: `final_score = 0.5 * norm_similarity + 0.3 * norm_freshness + 0.2 * source_weight`
  3. Source weights: `{'openai.com': 1.0, 'arxiv.org': 0.9, 'medium.com': 0.5, 'default': 0.3}`
  4. Articles without SQLite IDs (pre-v1.8) are excluded from ranked results
  5. `search --semantic` CLI command applies ranking before displaying results
  6. CLI output labeled "ranked" not "by similarity"
**Plans**: 1 plan
Plans:
- [x] 38-01-PLAN.md — Multi-factor ranking algorithm (rank_semantic_results, CLI wiring, tests)

### Phase 39: uvloop Best Practices Review
**Goal**: Review all async code patterns to ensure uvloop is used correctly, remove dead code, and document findings
**Depends on**: Phase 19, Phase 20, Phase 21, Phase 22 (v1.5 uvloop concurrency)
**Requirements**: None (code review phase)
**Success Criteria** (what must be TRUE):
  1. All CLI entry points use `uvloop.run()` (not `asyncio.run()`)
  2. All async code uses standard asyncio primitives (Semaphore, gather, to_thread)
  3. No custom event loop creation in async code
  4. Dead code removed from `src/utils/asyncio_utils.py`
  5. `install_uvloop()` pattern is consistent across all CLI entry points
**Plans**: 1 plan
Plans:
- [x] 39-01-PLAN.md — Dead code removal + install_uvloop() simplification (completed 2026-03-28)

### Phase 40: Comprehensive uvloop Audit
**Goal**: Full audit of all async code to identify uvloop anti-patterns, ensure no asyncio.run() usage, verify blocking calls are wrapped in asyncio.to_thread(), and confirm all async code flows through uvloop.run() at CLI boundaries
**Depends on**: Phase 39 (v1.10 uvloop Best Practices Review)
**Requirements**: None (code audit phase)
**Success Criteria** (what must be TRUE):
  1. Zero `asyncio.run()` calls found in `src/` (verified via grep)
  2. No blocking I/O calls outside `asyncio.to_thread()`
  3. No custom event loop creation in async code
  4. All async providers use true async (not sync-in-async patterns)
  5. Any uvloop anti-patterns found are fixed or noted as deferred
**Plans**: 1 plan
**Status**: ✅ Complete

Plans:
- [x] 40-01-PLAN.md — Comprehensive uvloop Audit (grep verification + file-by-file audit + VERIFICATION.md)

### Phase 34: Discovery Core Module
**Goal**: Users can programmatically discover RSS/Atom/RDF feeds from a website URL via the discovery service module
**Depends on**: Nothing (first phase of v1.9)
**Requirements**: DISC-01, DISC-02, DISC-03, DISC-04
**Success Criteria** (what must be TRUE):
  1. `discover_feeds(url)` function parses HTML `<head>` for `<link rel="alternate" type="...">` tags and returns discovered feed URLs
  2. `discover_feeds(url)` falls back to well-known paths (/feed, /feed/, /rss, /rss.xml, /atom.xml, /feed.xml, /index.xml) when no autodiscovery tags found
  3. Relative URLs in `<link href="...">` are correctly resolved to absolute URLs using urljoin and `<base href>` override
  4. Discovered feed URLs are validated via HEAD request, returning only feeds with HTTP 200 and Content-Type containing rss/atom/rdf
  5. Bozo feeds (malformed but parseable) are identified and filtered from results
**Plans**: 3 plans
Plans:
- [ ] 34-01-PLAN.md — Discovery package foundation (models, common_paths)
- [ ] 34-02-PLAN.md — HTML link parser and feed validator (parser.py, fetcher.py)
- [ ] 34-03-PLAN.md — discover_feeds() entry point orchestration

### Phase 35: Discovery CLI Command
**Goal**: Users can run `discover <url> --discover-deep [n]` to see all discoverable feeds without subscribing
**Depends on**: Phase 34
**Requirements**: DISC-05
**Success Criteria** (what must be TRUE):
  1. User can run `discover <url>` and see a list of discovered RSS/Atom/RDF feeds
  2. User can run `discover <url> --discover-deep 1` to limit crawling to depth 1 (current page only)
  3. User can run `discover <url> --discover-deep 2` to enable BFS crawling up to depth 2
  4. CLI output shows feed URL, feed type (RSS/Atom/RDF), and title if available
**Plans**: 1 plan
Plans:
- [x] 35-01-PLAN.md — Discovery CLI command (discover.py, registration)

### Phase 36: Feed Add Integration
**Goal**: Users can add feeds via discovery using `feed add <url> --discover --automatic --discover-deep`
**Depends on**: Phase 34, Phase 35
**Requirements**: DISC-06
**Success Criteria** (what must be TRUE):
  1. User can run `feed add <url> --discover on` to enable feed discovery during subscription
  2. User can run `feed add <url> --automatic on` to enable automatic feed addition from discovered feeds
  3. User can run `feed add <url> --discover-deep 2` to set deep crawl depth for discovery
  4. Default behavior: `--discover on`, `--automatic off` (discovery enabled but not automatic)
**Plans**: 1 plan
Plans:
- [x] 36-01-PLAN.md — Feed Add Integration (discovery options, selection prompt)

### Phase 37: Deep Crawling
**Goal**: Users can discover feeds across an entire website with BFS crawling, respecting robots.txt
**Depends on**: Phase 34, Phase 35
**Requirements**: DISC-07, DISC-08, DISC-09
**Success Criteria** (what must be TRUE):
  1. Deep crawl (depth > 1) uses BFS with visited-set to avoid cycles and duplicate URLs
  2. Deep crawl respects rate limiting (2 seconds per host) to avoid overwhelming servers
  3. Deep crawl honors robots.txt using robotexclusionrulesparser for disallowed paths
  4. User can read `docs/Automatic Discovery Feed.md` which documents the discovery algorithm, URL resolution rules, and supported feed types
**Plans**: 2 plans
Plans:
- [x] 37-01-PLAN.md — Deep Crawling (BFS, rate limiting, robots.txt, docs)
- [x] 37-02-PLAN.md — Dynamic Subdirectory Discovery (CSS selector-based link discovery, remove hardcoded subdir names)

### v1.8 ChromaDB 语义搜索 (Phases 30-33)

- [ ] **Phase 30: Semantic Search Infrastructure** - ChromaDB setup, embedding service, model pre-download
- [x] **Phase 31: Write Path - Incremental Embedding** - Embed articles during fetch, reindex command (completed 2026-03-26)
- [ ] **Phase 32: Query Path - Semantic Search CLI** - search --semantic, article related
- [ ] **Phase 33: Polish - Error Handling** - Graceful handling for pre-v1.8 articles

## Phase Details

### Phase 30: Semantic Search Infrastructure
**Goal**: Users can perform semantic similarity search across all articles using vector embeddings
**Depends on**: Nothing
**Requirements**: SEM-01, SEM-02, SEM-03
**Success Criteria** (what must be TRUE):
  1. ChromaDB PersistentClient initialized with local directory storage
  2. Article embeddings (384-dim via all-MiniLM-L6-v2) can be stored and queried
  3. Embedding model downloaded on first startup (not on first search query)
  4. ChromaDB collection exists and is accessible for add/query operations
  5. ChromaDB client is singleton (reused across CLI invocations)
**Plans**: 3 plans
Plans:
- [x] 30-01-PLAN.md — ChromaDB Client Infrastructure (PersistentClient singleton, collection setup)
- [x] 30-02-PLAN.md — Embedding Function + Model Pre-download (sentence-transformers integration)
- [x] 30-03-PLAN.md — Integration Verification (verify all components work together)

### Phase 31: Write Path - Incremental Embedding
**Goal**: New articles are automatically embedded and stored in ChromaDB during fetch
**Depends on**: Phase 30
**Requirements**: SEM-06
**Success Criteria** (what must be TRUE):
  1. Newly fetched articles automatically generate embedding and store in ChromaDB
  2. Embedding generation does not block article storage (async or background)
  3. Existing articles without embeddings can be backfilled via reindex command
  4. Articles are deduplicated by ID before embedding (no duplicate vectors)
**Plans**: 2 plans
Plans:
- [x] 31-01-PLAN.md — Add add_article_embedding() to vector.py and export from __init__.py
- [x] 31-02-PLAN.md — Integrate add_article_embedding in fetch.py after store_article_async()

### Phase 32: Query Path - Semantic Search CLI
**Goal**: Users can discover articles using natural language queries
**Depends on**: Phase 30, Phase 31
**Requirements**: SEM-04, SEM-05
**Success Criteria** (what must be TRUE):
  1. `search --semantic "query"` returns articles sorted by semantic similarity
  2. `article related <id>` shows articles similar to the specified article
  3. Results display article title, similarity score, and source
  4. Empty results handled gracefully with user-friendly message
**Plans**: 1 plan
Plans:
- [x] 40-01-PLAN.md — Comprehensive uvloop Audit (grep verification + file-by-file audit + VERIFICATION.md)

### Phase 33: Polish - Error Handling
**Goal**: System handles edge cases gracefully without crashing
**Depends on**: Phase 32
**Requirements**: SEM-07
**Success Criteria** (what must be TRUE):
  1. Articles fetched before v1.8 (no embedding) show friendly message when queried semantically
  2. ChromaDB errors (corruption, disk full) are caught and reported without crash
  3. `article related <id>` on article without embedding shows helpful message
  4. `search --semantic` on empty index handles gracefully
**Plans**: 1 plan
Plans:
- [ ] 33-01-PLAN.md — Add graceful error handling for semantic search edge cases

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | Complete | ✅ | 2026-03-22 |
| 2. Search & Refresh | Complete | ✅ | 2026-03-22 |
| 3. Web Crawling | Complete | ✅ | 2026-03-22 |
| 4. GitHub API Client | Complete | ✅ | 2026-03-23 |
| 5. Changelog Detection | Complete | ✅ | 2026-03-23 |
| 6. Unified Display | Complete | ✅ | 2026-03-23 |
| 7. Tagging System | Complete | ✅ | 2026-03-23 |
| 8. GitHub URL Metadata | Complete | ✅ | 2026-03-23 |
| 8.1 Unified Feed Add | 2/2 | ✅ Complete | 2026-03-23 |
| 9. Enhanced Article List | 1/1 | ✅ Complete | 2026-03-23 |
| 10. Article Detail View | 1/1 | ✅ Complete | 2026-03-23 |
| 11. GitHub Release Tagging | 1/1 | ✅ Complete | 2026-03-23 |
| 12. Provider Core Infrastructure | 2/2 | ✅ Complete | 2026-03-23 |
| 13. Provider Implementations | 2/2 | ✅ Complete | 2026-03-23 |
| 14. CLI Integration | 3/3 | ✅ Complete | 2026-03-23 |
| 15. PyGithub Refactor | 2/2 | ✅ Complete | 2026-03-23 |
| 16. GitHubReleaseProvider | 1/1 | ✅ Complete | 2026-03-24 |
| 17. Anti-屎山 Refactoring | 2/2 | ✅ Complete | 2026-03-24 |
| 18. Storage Layer Enforcement | 1/1 | ✅ Complete | 2026-03-24 |
| 19. uvloop Setup | 1/1 | ✅ Complete | 2026-03-25 |
| 20. RSSProvider Async | 1/1 | ✅ Complete | 2026-03-24 |
| 21. Concurrent Fetch | 1/1 | ✅ Complete | 2026-03-25 |
| 22. CLI Integration | 1/1 | ✅ Complete | 2026-03-25 |
| 23. nanoid Code Changes | 1/1 | ✅ Complete | 2026-03-25 |
| 24. Migration Script | 0/1 | Deferred | - |
| 25. Verification | 1/1 | ✅ Complete | 2026-03-25 |
| 26. pytest框架搭建 | 1/1 | ✅ Complete | 2026-03-24 |
| 27. Provider单元测试 | 1/1 | ✅ Complete | 2026-03-24 |
| 28. Storage层单元测试 | 1/1 | ✅ Complete | 2026-03-25 |
| 29. CLI集成测试 | 1/1 | ✅ Complete | 2026-03-25 |
| 30. Semantic Search Infrastructure | 3/3 | ✅ Complete | 2026-03-27 |
| 31. Write Path - Incremental Embedding | 2/2 | ✅ Complete | 2026-03-26 |
| 32. Query Path - Semantic Search CLI | — | ✅ Complete | 2026-03-27 |
| 33. Polish - Error Handling | — | ✅ Complete | 2026-03-27 |
| 34. Discovery Core Module | 3/3 | ✅ Complete | 2026-03-27 |
| 35. Discovery CLI Command | 1/1 | ✅ Complete | 2026-03-27 |
| 36. Feed Add Integration | 1/1 | ✅ Complete | 2026-03-27 |
| 37. Deep Crawling | 2/2 | Complete    | 2026-03-27 |
| 38. Search Result Ranking | 1/1 | Complete    | 2026-03-27 |
| 39. uvloop Best Practices Review | 1/1 | Complete    | 2026-03-27 |
| 40. Comprehensive uvloop Audit | 1/1 | ✅ Complete | 2026-03-28 |

---
_For completed milestone details, see `.planning/milestones/`_
