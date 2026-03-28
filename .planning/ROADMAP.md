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
- [ ] **v2.0 Search Ranking Architecture** — Phases 41-44 (planned)

## Phase Progress

| Phase | Plans | Status | Completed |
|-------|-------|--------|-----------|
| 1. Foundation | Complete | ✅ | 2026-03-22 |
| 2. Search & Refresh | Complete | ✅ | 2026-03-22 |
| 3. Web Crawling | Complete | ✅ | 2026-03-22 |
| 4. GitHub API Client | Complete | ✅ | 2026-03-23 |
| 5. Changelog Detection | Complete | ✅ | 2026-03-23 |
| 6. Unified Display | Complete | ✅ | 2026-03-23 |
| 7. Tagging System | Complete | ✅ | 2026-03-23 |
| 8. GitHub URL Metadata | Complete | ✅ | 2026-03-23 |
| 8.1 Unified Feed Add | 2/2 | ✅ | 2026-03-23 |
| 9. Enhanced Article List | 1/1 | ✅ | 2026-03-23 |
| 10. Article Detail View | 1/1 | ✅ | 2026-03-23 |
| 11. GitHub Release Tagging | 1/1 | ✅ | 2026-03-23 |
| 12. Provider Core Infrastructure | 2/2 | ✅ | 2026-03-23 |
| 13. Provider Implementations | 2/2 | ✅ | 2026-03-23 |
| 14. CLI Integration | 3/3 | ✅ | 2026-03-23 |
| 15. PyGithub Refactor | 2/2 | ✅ | 2026-03-23 |
| 16. GitHubReleaseProvider | 1/1 | ✅ | 2026-03-24 |
| 17. Anti-屎山 Refactoring | 2/2 | ✅ | 2026-03-24 |
| 18. Storage Layer Enforcement | 1/1 | ✅ | 2026-03-24 |
| 19. uvloop Setup | 1/1 | ✅ | 2026-03-25 |
| 20. RSSProvider Async | 1/1 | ✅ | 2026-03-24 |
| 21. Concurrent Fetch | 1/1 | ✅ | 2026-03-25 |
| 22. CLI Integration | 1/1 | ✅ | 2026-03-25 |
| 23. nanoid Code Changes | 1/1 | ✅ | 2026-03-25 |
| 24. Migration Script | 0/1 | Deferred | — |
| 25. Verification | 1/1 | ✅ | 2026-03-25 |
| 26. pytest框架搭建 | 1/1 | ✅ | 2026-03-24 |
| 27. Provider单元测试 | 1/1 | ✅ | 2026-03-24 |
| 28. Storage层单元测试 | 1/1 | ✅ | 2026-03-25 |
| 29. CLI集成测试 | 1/1 | ✅ | 2026-03-25 |
| 30. Semantic Search Infrastructure | 3/3 | ✅ | 2026-03-27 |
| 31. Write Path - Incremental Embedding | 2/2 | ✅ | 2026-03-26 |
| 32. Query Path - Semantic Search CLI | 1/1 | ✅ | 2026-03-27 |
| 33. Polish - Error Handling | 1/1 | ✅ | 2026-03-27 |
| 34. Discovery Core Module | 3/3 | ✅ | 2026-03-27 |
| 35. Discovery CLI Command | 1/1 | ✅ | 2026-03-27 |
| 36. Feed Add Integration | 1/1 | ✅ | 2026-03-27 |
| 37. Deep Crawling | 2/2 | ✅ | 2026-03-27 |
| 38. Search Result Ranking | 1/1 | ✅ | 2026-03-27 |
| 39. uvloop Best Practices Review | 1/1 | ✅ | 2026-03-28 |
| 40. Comprehensive uvloop Audit | 1/1 | ✅ | 2026-03-28 |
| 41. ArticleListItem & Semantic Search Core | 1/1 | Complete   | 2026-03-28 |
| 42. Storage Scoring Fixes | 0 | Not started | - |
| 43. Scoring Infrastructure | 0 | Not started | - |
| 44. CLI Integration | 0 | Not started | - |

---

## Milestone Details

<details>
<summary>✅ v1.0 MVP (Phases 1-3) — SHIPPED 2026-03-22</summary>

- [x] Phase 1: Foundation
- [x] Phase 2: Search & Refresh
- [x] Phase 3: Web Crawling
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

- [x] Phase 19: uvloop Setup + crawl_async Protocol
- [x] Phase 20: RSSProvider Async HTTP
- [x] Phase 21: Concurrent Fetch + SQLite Serialization
- [x] Phase 22: CLI Integration

</details>

<details>
<summary>✅ v1.7 pytest测试框架 (Phases 26-29) — SHIPPED 2026-03-25</summary>

- [x] Phase 26: pytest框架搭建
- [x] Phase 27: Provider单元测试
- [x] Phase 28: Storage层单元测试
- [x] Phase 29: CLI集成测试

</details>

<details>
<summary>✅ v1.8 ChromaDB 语义搜索 (Phases 30-33) — SHIPPED 2026-03-27</summary>

- [x] Phase 30: Semantic Search Infrastructure (3/3 plans)
- [x] Phase 31: Write Path - Incremental Embedding (2/2 plans)
- [x] Phase 32: Query Path - Semantic Search CLI (1/1 plans)
- [x] Phase 33: Polish - Error Handling (1/1 plans)

</details>

<details>
<summary>✅ v1.9 Automatic Discovery Feed (Phases 34-37) — SHIPPED 2026-03-27</summary>

- [x] Phase 34: Discovery Core Module (3/3 plans)
- [x] Phase 35: Discovery CLI Command (1/1 plans)
- [x] Phase 36: Feed Add Integration (1/1 plans)
- [x] Phase 37: Deep Crawling (2/2 plans)

**Key features:** `discover <url>` CLI, BFS crawler with robots.txt, CSS selector link discovery, multi-factor ranking

</details>

<details>
<summary>✅ v1.10 uvloop Best Practices Review (Phase 39) — SHIPPED 2026-03-28</summary>

- [x] Phase 39: uvloop Best Practices Review (1/1 plans)

**Key changes:** Simplified `install_uvloop()` to `uvloop.install()`, removed dead code from `asyncio_utils.py` (93→44 lines)

</details>

<details>
<summary>✅ v1.11 Comprehensive uvloop Audit (Phase 40) — SHIPPED 2026-03-28</summary>

- [x] Phase 40: Comprehensive uvloop Audit (1/1 plans)

**Key findings:** Zero `asyncio.run()` in `src/`, 5 `uvloop.run()` at CLI boundaries, no blocking I/O outside `to_thread()`

</details>

---

### v2.0 Search Ranking Architecture (Planned)

**Milestone Goal:** 实现 Route A — 三种搜索方法返回原始信号，应用层 `combine_scores` 统一合并，可选 Cross-Encoder 重排

#### Phase 41: ArticleListItem & Semantic Search Core
**Goal**: ArticleListItem extended with scoring fields; search_articles_semantic returns raw cos_sim without crashing
**Depends on**: Phase 40
**Requirements**: SEARCH-00, SEARCH-01, SEARCH-02
**Success Criteria** (what must be TRUE):
1. ArticleListItem has vec_sim, bm25_score, freshness, source_weight, ce_score, final_score fields
2. search_articles_semantic returns ArticleListItem with vec_sim set to raw cosine similarity from ChromaDB
3. search_articles_semantic no longer crashes when pub_date is INTEGER unix timestamp
4. search_articles_semantic score is NOT a weighted combination (returns raw cos_sim directly)
**Plans**: 1 plan
- [x] 41-01-PLAN.md — ArticleListItem field extension + pub_date crash fix + raw cos_sim return

#### Phase 42: Storage Scoring Fixes
**Goal**: list_articles and search_articles return properly normalized freshness and BM25 scores
**Depends on**: Phase 41
**Requirements**: SEARCH-03, SEARCH-04
**Success Criteria** (what must be TRUE):
1. list_articles populates freshness score (0-1, time decay from publication date)
2. Articles without vec_sim/bm25_score/ce_score have those fields set to 0.0
3. search_articles BM25 score uses sigmoid normalization: sigmoid_norm(bm25_raw, factor)
4. BM25 sigmoid factor is configurable via config.py (default 0.5)
**Plans**: TBD

#### Phase 43: Scoring Infrastructure
**Goal**: Cross-Encoder rerank module and combine_scores function exist and work correctly
**Depends on**: Phase 42
**Requirements**: SEARCH-05, SEARCH-06
**Success Criteria** (what must be TRUE):
1. rerank() function exists in application/rerank.py and performs Cross-Encoder reranking
2. torch and transformers are lazy imported inside rerank() function (not at module level)
3. _model and _tokenizer are globally cached to avoid repeated loading
4. combine_scores(candidates, alpha, beta, gamma, delta) function exists in application/combine.py
5. combine_scores uses Newton's cooling law for freshness calculation (half_life_days=7)
6. combine_scores returns results sorted by final_score in descending order
**Plans**: TBD

#### Phase 44: CLI Integration
**Goal**: CLI article search command wires all components with weight configuration
**Depends on**: Phase 43
**Requirements**: SEARCH-07
**Success Criteria** (what must be TRUE):
1. `article search --semantic` uses: vector_search -> optional rerank -> combine_scores(gamma=0.2, delta=0.0)
2. `article search` (default FTS5) uses: search_articles -> optional rerank -> combine_scores(gamma=0.0, delta=0.2)
3. alpha and beta weights are always passed to combine_scores (default alpha=0.3)
4. --semantic and default search both produce ArticleListItem with final_score populated
**Plans**: TBD

---

_For completed milestone details, see `.planning/milestones/`_
