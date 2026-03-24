# Roadmap: Personal Information System

## Milestones

- [x] **v1.0 MVP** — Phases 1-3 (shipped 2026-03-22)
- [x] **v1.1 GitHub Monitoring + Tagging** — Phases 4-8 (shipped 2026-03-23)
- [x] **v1.2 Article List Enhancements** — Phases 8.1-11 (shipped 2026-03-23)
- [x] **v1.3 Provider Architecture** — Phases 12-15 (shipped 2026-03-23)
- [x] **v1.4 Storage Layer Enforcement** — Phases 16-18 (shipped 2026-03-25)
- [ ] **v1.5 uvloop并发支持** — Phases 19-22 (in progress)

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

### 🚧 v1.5 uvloop并发支持 (Phases 19-22)

- [x] **Phase 19: uvloop Setup + crawl_async Protocol** - Foundation for async crawling ✅ 2026-03-25
- [x] **Phase 20: RSSProvider Async HTTP** - httpx.AsyncClient for RSS feeds (completed 2026-03-24)
- [x] **Phase 21: Concurrent Fetch + SQLite Serialization** - Semaphore + asyncio.to_thread (completed 2026-03-24)
- [ ] **Phase 22: CLI Integration** - uvloop.run() + --concurrency parameter

## Phase Details

### Phase 19: uvloop Setup + crawl_async Protocol
**Goal**: Async crawl capability available on all providers
**Depends on**: Nothing (foundation phase)
**Requirements**: UVLP-01, UVLP-02
**Success Criteria** (what must be TRUE):
  1. uvloop.install() is called at application startup on Linux/macOS
  2. uvloop.install() fails gracefully on Windows (falls back to asyncio without error)
  3. ContentProvider protocol has crawl_async() method defined
  4. Default crawl_async() implementation wraps sync crawl() in run_in_executor
  5. Non-main thread uvloop errors are caught and handled gracefully
**Plans**: 2 plans
  - [ ] 19-01-PLAN.md — uvloop dependency + asyncio_utils + Protocol extension
  - [ ] 19-02-PLAN.md — CLI integration + DefaultProvider crawl_async

### Phase 20: RSSProvider Async HTTP
**Goal**: RSSProvider performs async HTTP requests using httpx.AsyncClient
**Depends on**: Phase 19
**Requirements**: UVLP-03
**Success Criteria** (what must be TRUE):
  1. RSSProvider implements crawl_async() using httpx.AsyncClient
  2. feedparser.parse() runs in thread pool executor to avoid blocking event loop
  3. AsyncClient is properly closed after use (context manager or explicit cleanup)
  4. RSS feeds are fetched concurrently during fetch_all_async()
**Plans**: 1 plan
  - [x] 20-01-PLAN.md — RSSProvider async HTTP with httpx.AsyncClient

### Phase 21: Concurrent Fetch + SQLite Serialization
**Goal**: Concurrent feed fetching with asyncio.Semaphore and serialized SQLite writes
**Depends on**: Phase 20
**Requirements**: UVLP-04, UVLP-05
**Success Criteria** (what must be TRUE):
  1. fetch_all_async() limits concurrent crawls using asyncio.Semaphore (default 10)
  2. SQLite write operations use asyncio.to_thread() to serialize access
  3. No "database is locked" errors occur during concurrent fetch
  4. All storage layer functions work correctly when called from async context
**Plans**: TBD

### Phase 22: CLI Integration
**Goal**: User can invoke async fetch from CLI with configurable concurrency
**Depends on**: Phase 21
**Requirements**: UVLP-06, UVLP-07
**Success Criteria** (what must be TRUE):
  1. `fetch --all` command uses uvloop.run() to execute async fetch logic
  2. `fetch --all --concurrency N` overrides default concurrency limit
  3. `fetch --concurrency 5 --all` works correctly
  4. Error aggregation provides summary output without crashing on individual feed failures
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
| 12. Provider Core Infrastructure | 2/2 | Complete | 2026-03-23 |
| 13. Provider Implementations | 2/2 | Complete | 2026-03-23 |
| 14. CLI Integration | 3/3 | Complete | 2026-03-23 |
| 15. PyGithub Refactor | 2/2 | Complete | 2026-03-23 |
| 16. GitHubReleaseProvider | 1/1 | Complete | 2026-03-24 |
| 17. Anti-屎山 Refactoring | 2/2 | Complete | 2026-03-24 |
| 18. Storage Layer Enforcement | 1/1 | Complete | 2026-03-24 |
| 19. uvloop Setup + crawl_async Protocol | 0/2 | Not started | - |
| 20. RSSProvider Async HTTP | 1/1 | Complete    | 2026-03-24 |
| 21. Concurrent Fetch + SQLite Serialization | 1/1 | Complete   | 2026-03-24 |
| 22. CLI Integration | 0/1 | Not started | - |

---
_For completed milestone details, see `.planning/milestones/`_
