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
- [x] **v2.0 Search Ranking Architecture** — Phases 41-44 (shipped 2026-03-28)
- [ ] **v2.1 Discovery & Providers Refactor** — Phases 45-47 (in progress)

## Phases

- [ ] **Phase 45: Discovery Core Architecture** - feed_meta pattern, provider-verified feeds, deep_crawl delegation
- [ ] **Phase 46: Provider Contract & match() Semantics** - match() edge cases, parse_feed() docstring
- [ ] **Phase 47: Code Quality & Consistency** - BROWSER_HEADERS, async patterns, duplicate code cleanup

---

## Phase Details

### Phase 45: Discovery Core Architecture

**Goal**: Discovery module uses feed_meta() pattern for validation; all discovered feeds are provider-verified

**Depends on**: Phase 44 (v2.0 shipped)

**Requirements**: ARCH-01, ARCH-02, ARCH-03, API-02, API-03

**Files affected**:
- `src/providers/__init__.py` (providers.discover())
- `src/discovery/__init__.py` (discover_feeds())
- `src/discovery/deep_crawl.py` (deep_crawl())
- `src/discovery/fetcher.py` (validate_feed, _quick_validate_feed_sync)
- `src/providers/rss_provider.py` (RSSProvider)

**Success Criteria** (what must be TRUE):
  1. `providers.discover()` calls `feed_meta()` (not `parse_feed()`) to validate discovered feeds
  2. `discover_feeds()` returns only feeds that a provider confirms it can handle via `match()`
  3. `deep_crawl()` performs URL discovery only; all feed validation delegated to `providers.discover()`
  4. `providers.discover()` returns feeds deduplicated by URL
  5. `DiscoveredFeed.valid=True` means provider confirmed handleable; no invalid feeds reach `register_feed()`

**Plans**:
- [x] 045-01-PLAN.md — feed_meta pattern, provider-verified feeds, deep_crawl delegation

---

### Phase 46: Provider Contract & match() Semantics

**Goal**: Provider match() contract documented and consistent; parse_feed() behavior clarified

**Depends on**: Phase 45

**Requirements**: ARCH-04, API-01

**Files affected**:
- `src/providers/__init__.py` (ContentProvider docstring)
- `src/providers/rss_provider.py` (match())
- `src/providers/github_release_provider.py` (match())
- `src/providers/github_provider.py` (match())
- `src/providers/webpage_provider.py` (match())

**Success Criteria** (what must be TRUE):
  1. All providers' `match()` handles `response=None` gracefully (URL-only matching)
  2. ContentProvider docstring documents that `match(response=None)` is URL-only (no new HTTP requests)
  3. `parse_feed()` docstring clarifies it raises `ValueError`/`Exception` on invalid feeds

**Plans**:
- [x] 045-01-PLAN.md — feed_meta pattern, provider-verified feeds, deep_crawl delegation

---

### Phase 47: Code Quality & Consistency

**Goal**: Consistent HTTP headers and async patterns across all modules

**Depends on**: Phase 46

**Requirements**: QUAL-01, QUAL-02, QUAL-03

**Files affected**:
- `src/constants.py` (BROWSER_HEADERS)
- `src/providers/*.py` (all providers)
- `src/discovery/*.py` (all discovery modules)
- `src/application/fetch.py`

**Success Criteria** (what must be TRUE):
  1. All HTTP requests use `BROWSER_HEADERS` from `src/constants.py`; no hardcoded User-Agent strings
  2. All blocking HTTP calls in async functions use `asyncio.to_thread()`; no blocking `Fetcher.get()` in async context
  3. Duplicate feed validation code (`validate_feed()` in fetcher.py and `_quick_validate_feed_sync()` in RSSProvider) consolidated into a single shared utility

**Plans**:
- [x] 045-01-PLAN.md — feed_meta pattern, provider-verified feeds, deep_crawl delegation

---

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 41-44 | v2.0 | 8/8 | Complete | 2026-03-28 |
| 45. Discovery Core | v2.1 | 1/1 | In progress | - |
| 46. Provider Contract | v2.1 | 0/TBD | Not started | - |
| 47. Code Quality | v2.1 | 0/TBD | Not started | - |

---

## Coverage

**v2.1 Requirements Map:**

| Requirement | Phase | Description |
|-------------|-------|-------------|
| ARCH-01 | Phase 45 | providers.discover() uses feed_meta() pattern |
| ARCH-02 | Phase 45 | discover_feeds() returns provider-verified feeds only |
| ARCH-03 | Phase 45 | deep_crawl() delegates validation to providers |
| ARCH-04 | Phase 46 | match() edge cases (response=None handling) |
| QUAL-01 | Phase 47 | BROWSER_HEADERS used consistently everywhere |
| QUAL-02 | Phase 47 | asyncio.to_thread() for blocking HTTP calls |
| QUAL-03 | Phase 47 | Duplicate feed validation code cleanup |
| API-01 | Phase 46 | parse_feed() docstring clarifies it raises on failure |
| API-02 | Phase 45 | providers.discover() returns only unique feeds by URL |
| API-03 | Phase 45 | DiscoveredFeed.valid field semantics clarified |

**Coverage:** 10/10 requirements mapped

---

## Milestone Details

<details>
<summary>✅ v2.0 Search Ranking Architecture (Phases 41-44) — SHIPPED 2026-03-28</summary>

- [x] Phase 41: ArticleListItem & Semantic Search Core (1/1 plans) — completed 2026-03-28
- [x] Phase 42: Storage Scoring Fixes (1/1 plans) — completed 2026-03-28
- [x] Phase 43: Scoring Infrastructure (1/1 plans) — completed 2026-03-28
- [x] Phase 44: CLI Integration (1/1 plans) — completed 2026-03-28

**Key features:** Route A unified search ranking — raw signals from storage, combine_scores at application layer, optional Cross-Encoder reranking, Newton's cooling law freshness

</details>

---

### v2.1 Discovery & Providers Refactor (Phases 45-47) — IN PROGRESS

**Milestone Goal:** Clean up and harden the feed discovery architecture using best practices.

- [ ] Phase 45: Discovery Core Architecture
- [ ] Phase 46: Provider Contract & match() Semantics
- [ ] Phase 47: Code Quality & Consistency

---

_For completed milestone details, see `.planning/milestones/`_
