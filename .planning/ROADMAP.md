# Roadmap: Personal Information System

## Milestones

- [x] **v1.0 MVP** — Phases 1-3 (shipped 2026-03-22)
- [x] **v1.1 GitHub Monitoring + Tagging** — Phases 4-8 (shipped 2026-03-23)
- [x] **v1.2 Article List Enhancements** — Phases 8.1-11 (shipped 2026-03-23)
- [x] **v1.3 Provider Architecture** — Phases 12-15 (shipped 2026-03-23)
- [x] **v1.4 Storage Layer Enforcement** — Phases 16-18 (shipped 2026-03-25)
- [x] **v1.5 uvloop并发支持** — Phases 19-22 (shipped 2026-03-25)
- [ ] **v1.6 nanoid ID生成** — Phases 23-25 (in progress)

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

- [x] **Phase 19: uvloop Setup + crawl_async Protocol** - Foundation for async crawling (completed 2026-03-25)
- [x] **Phase 20: RSSProvider Async HTTP** - httpx.AsyncClient for RSS feeds (completed 2026-03-24)
- [x] **Phase 21: Concurrent Fetch + SQLite Serialization** - Semaphore + asyncio.to_thread (completed 2026-03-25)
- [x] **Phase 22: CLI Integration** - uvloop.run() + --concurrency parameter (completed 2026-03-25)

### 🚧 v1.6 nanoid ID生成 (Phases 23, 25)

- [ ] **Phase 23: nanoid Code Changes** - Replace uuid.uuid4() with nanoid.generate() in storage functions
- [ ] **Phase 25: Verification** - Validate all article operations work with new IDs

> **Note:** Phase 24 (Migration Script) deferred — historical URL-like IDs will be addressed in future milestone when needed.

## Phase Details

### Phase 23: nanoid Code Changes
**Goal**: store_article(), add_tag(), and tag_article() use nanoid.generate() instead of uuid.uuid4()
**Depends on**: Nothing
**Requirements**: NANO-01
**Success Criteria** (what must be TRUE):
  1. store_article() uses nanoid.generate() for article id instead of uuid.uuid4()
  2. add_tag() uses nanoid.generate() for tag id instead of uuid.uuid4()
  3. tag_article() uses nanoid.generate() for article_tag entries instead of uuid.uuid4()
  4. New articles created during migration window have nanoid format (21 chars, URL-safe)
  5. nanoid package is installed and importable (nanoid>=2.0.0)
**Plans**: TBD

### Phase 25: Verification
**Goal**: All article-related operations work correctly with nanoid format
**Depends on**: Phase 23
**Requirements**: NANO-03
**Success Criteria** (what must be TRUE):
  1. New articles have nanoid-format IDs (21 chars)
  2. article list command works with new articles
  3. article detail <8-char-prefix> works for new articles
  4. article open <8-char-prefix> works for new articles
  5. Tag operations (add/remove) work on new articles
  6. Search returns new articles correctly
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
| 23. nanoid Code Changes | 0/1 | Not started | - |
| 24. Migration Script | 0/1 | Deferred | - |
| 25. Verification | 0/1 | Not started | - |

---
_For completed milestone details, see `.planning/milestones/`_
