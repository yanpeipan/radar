# Roadmap: Personal Information System

## Milestones

- [x] **v1.0 MVP** — Phases 1-3 (shipped 2026-03-22)
- [x] **v1.1 GitHub Monitoring + Tagging** — Phases 4-8 (shipped 2026-03-23)
- [x] **v1.2 Article List Enhancements** — Phases 8.1-11 (shipped 2026-03-23)
- [x] **v1.3 Provider Architecture** — Phases 12-15 (shipped 2026-03-23)
- [x] **v1.4 Storage Layer Enforcement** — Phases 16-18 (shipped 2026-03-25)
- [x] **v1.5 uvloop并发支持** — Phases 19-22 (shipped 2026-03-25)
- [x] **v1.7 pytest测试框架** — Phases 26-29 (shipped 2026-03-25)
- [ ] **v1.8 ChromaDB 语义搜索** — Phases 30-33 (in progress)

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

### 🚧 v1.8 ChromaDB 语义搜索 (Phases 30-33)

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
**Plans**: TBD

### Phase 33: Polish - Error Handling
**Goal**: System handles edge cases gracefully without crashing
**Depends on**: Phase 32
**Requirements**: SEM-07
**Success Criteria** (what must be TRUE):
  1. Articles fetched before v1.8 (no embedding) show friendly message when queried semantically
  2. ChromaDB errors (corruption, disk full) are caught and reported without crash
  3. `article related <id>` on article without embedding shows helpful message
  4. `search --semantic` on empty index handles gracefully
**Plans**: TBD

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
| 31. Write Path - Incremental Embedding | 2/2 | Complete   | 2026-03-26 |
| 32. Query Path - Semantic Search CLI | 0/1 | Not started | - |
| 33. Polish - Error Handling | 0/1 | Not started | - |

---
_For completed milestone details, see `.planning/milestones/`_
