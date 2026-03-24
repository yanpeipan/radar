# Roadmap: Personal Information System

## Milestones

- [x] **v1.0 MVP** — Phases 1-3 (shipped 2026-03-22)
- [x] **v1.1 GitHub Monitoring + Tagging** — Phases 4-8 (shipped 2026-03-23)
- [x] **v1.2 Article List Enhancements** — Phases 8.1-11 (shipped 2026-03-23)
- [x] **v1.3 Provider Architecture** — Phases 12-15 (shipped 2026-03-23)
- [x] **v1.4 Storage Layer Enforcement** — Phases 16-18 (shipped 2026-03-25)
- [x] **v1.5 uvloop并发支持** — Phases 19-22 (shipped 2026-03-25)
- [ ] **v1.7 pytest测试框架** — Phases 26-29 (in progress)

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

### 🚧 v1.7 pytest测试框架 (Phases 26-29)

- [x] **Phase 26: pytest框架搭建** - conftest.py fixtures, pytest configuration, testing conventions (completed 2026-03-24)
- [ ] **Phase 27: Provider单元测试** - RSSProvider, GitHubReleaseProvider, ProviderRegistry tests
- [ ] **Phase 28: Storage层单元测试** - SQLite storage CRUD operation tests
- [ ] **Phase 29: CLI集成测试** - CLI command integration tests with CliRunner

## Phase Details

### Phase 23: nanoid Code Changes
**Goal**: store_article(), add_tag(), and tag_article() use nanoid.generate() instead of uuid.uuid4()
**Depends on**: Nothing
**Requirements**: NANO-01
**Status**: ✅ Complete (2026-03-25)
**Success Criteria** (what must be TRUE):
  1. store_article() uses nanoid.generate() for article id instead of uuid.uuid4()
  2. add_tag() uses nanoid.generate() for tag id instead of uuid.uuid4()
  3. tag_article() uses nanoid.generate() for article_tag entries instead of uuid.uuid4()
  4. New articles created during migration window have nanoid format (21 chars, URL-safe)
  5. nanoid package is installed and importable (nanoid>=2.0.0)
**Plans**: 1 plan
  - [x] 23-01-PLAN.md - Replace uuid.uuid4() with nanoid.generate() in storage functions

### Phase 25: Verification
**Goal**: All article-related operations work correctly with nanoid format
**Depends on**: Phase 23
**Requirements**: NANO-03
**Status**: In progress
**Success Criteria** (what must be TRUE):
  1. New articles have nanoid-format IDs (21 chars)
  2. article list command works with new articles
  3. article detail <8-char-prefix> works for new articles
  4. article open <8-char-prefix> works for new articles
  5. Tag operations (add/remove) work on new articles
  6. Search returns new articles correctly
**Plans**: 1 plan
  - [ ] 25-PLAN.md - Verify nanoid article operations

### Phase 26: pytest框架搭建
**Goal**: Install pytest packages, configure pyproject.toml, create root conftest.py with fixtures
**Depends on**: Nothing
**Requirements**: TEST-01
**Status**: In progress (1/1 plans)
**Success Criteria** (what must be TRUE):
  1. pytest 9.0.2+ installed with pytest-asyncio, pytest-cov, pytest-mock, pytest-click, pytest-httpx
  2. `asyncio_mode = "auto"` configured in pyproject.toml
  3. `tests/conftest.py` created with fixtures: temp_db_path, initialized_db, sample_feed, sample_article, cli_runner
  4. Test conventions established: no private function testing, real DB via tmp_path
**Plans**: 1 plan
  - [x] 26-PLAN.md - pytest框架搭建

### Phase 27: Provider单元测试
**Goal**: Write unit tests for Provider plugin architecture
**Depends on**: Phase 26
**Requirements**: TEST-02
**Status**: Not started
**Success Criteria** (what must be TRUE):
  1. test_providers.py covers RSSProvider.match(), crawl(), crawl_async(), parse()
  2. test_providers.py covers GitHubReleaseProvider.match(), priority(), crawl(), parse()
  3. ProviderRegistry discover() and discover_or_default() tested
  4. HTTP mocked via httpx_mock fixture (no real network calls)
**Plans**: 1 plan
  - [ ] 27-PLAN.md - Provider单元测试

### Phase 28: Storage层单元测试
**Goal**: Write unit tests for SQLite storage layer
**Depends on**: Phase 26
**Requirements**: TEST-03
**Status**: Not started
**Success Criteria** (what must be TRUE):
  1. test_storage.py covers store_article(), list_articles(), search_articles()
  2. test_storage.py covers feed CRUD (add_feed, list_feeds, etc.)
  3. test_storage.py covers tag operations (add_tag, tag_article, get_article_tags)
  4. All tests use real SQLite via tmp_path fixture (no mocking sqlite3)
**Plans**: 1 plan
  - [ ] 28-PLAN.md - Storage层单元测试

### Phase 29: CLI集成测试
**Goal**: Write integration tests for CLI commands
**Depends on**: Phase 26, Phase 28
**Requirements**: TEST-04
**Status**: Not started
**Success Criteria** (what must be TRUE):
  1. test_cli.py covers feed add/list commands
  2. test_cli.py covers article list/detail commands
  3. test_cli.py covers tag commands
  4. All tests use CliRunner.invoke() with isolated_filesystem()
  5. Error cases tested (invalid URL, duplicate feed, not found)
**Plans**: 1 plan
  - [ ] 29-PLAN.md - CLI集成测试

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
| 23. nanoid Code Changes | 1/1 | ✅ Complete | 2026-03-25 |
| 24. Migration Script | 0/1 | Deferred | - |
| 25. Verification | 0/1 | In progress | - |
| 26. pytest框架搭建 | 1/1 | Complete    | 2026-03-24 |
| 27. Provider单元测试 | 0/1 | Not started | - |
| 28. Storage层单元测试 | 0/1 | Not started | - |
| 29. CLI集成测试 | 0/1 | Not started | - |

---
_For completed milestone details, see `.planning/milestones/`_
