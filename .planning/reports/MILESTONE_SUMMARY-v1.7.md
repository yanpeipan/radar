# Milestone v1.7 — pytest测试框架 Summary

**Generated:** 2026-03-25
**Purpose:** Team onboarding and project review

---

## 1. Project Overview

**个人资讯系统** — A CLI tool for collecting, subscribing to, and organizing information sources from the internet. Users add RSS feeds or website URLs, the system crawls content and stores it in a local SQLite database for reading and retrieval.

**Core value:** Users can centrally manage all information sources in one place without visiting each website individually.

**v1.7 milestone scope:** Introduced pytest testing framework with comprehensive unit tests for Provider plugin architecture, Storage SQLite layer, and CLI commands.

---

## 2. Architecture & Technical Decisions

- **pytest 9.0.2 + plugins:** pytest-asyncio, pytest-cov, pytest-mock, pytest-click, pytest-httpx
  - **Why:** Standard Python testing ecosystem with async support and Click CLI testing
  - **Phase:** 26

- **Real SQLite via tmp_path fixture:** No mocking of sqlite3 — tests use actual temporary databases
  - **Why:** Ensures integration correctness between storage layer and SQLite
  - **Phase:** 26, 28

- **unittest.mock.patch for HTTP mocking:** Patches httpx functions at module level rather than using httpx_mock fixture
  - **Why:** Providers call httpx directly, not through abstraction; matches existing patterns
  - **Phase:** 27, 29

- **CliRunner.invoke() for CLI testing:** Isolated filesystem + database patching via initialized_db fixture
  - **Why:** Full CLI command testing with database isolation without real filesystem
  - **Phase:** 29

- **Class-based test organization:** Test classes mirror storage module structure
  - **Why:** Logical grouping, easy to find related tests
  - **Phase:** 27, 28, 29

- **FK-first test setup:** Create Feed before Article in each test due to foreign key constraint
  - **Why:** articles.feed_id FK requires parent feed to exist first
  - **Phase:** 28

---

## 3. Phases Delivered

| Phase | Name | Status | One-Liner |
|-------|------|--------|-----------|
| 26 | pytest框架搭建 | ✅ Complete | pytest 9.0.2 + conftest.py fixtures (temp_db_path, initialized_db, sample_feed, sample_article, cli_runner) |
| 27 | Provider单元测试 | ✅ Complete | 24 tests for RSSProvider, GitHubReleaseProvider, ProviderRegistry |
| 28 | Storage层单元测试 | ✅ Complete | 42 tests for Article, Feed, Tag SQLite CRUD operations |
| 29 | CLI集成测试 | ✅ Complete | 19 tests for feed/article/tag CLI commands |

---

## 4. Requirements Coverage

All TEST-0x requirements from v1.7 pytest测试框架 milestone:

- ✅ **TEST-01:** 引入pytest测试框架，配置conftest.py和基础fixtures
- ✅ **TEST-02:** 为Provider插件架构编写单元测试
- ✅ **TEST-03:** 为Storage层SQLite操作编写单元测试
- ✅ **TEST-04:** 为CLI命令编写集成测试

---

## 5. Key Decisions Log

| ID | Decision | Phase | Rationale |
|----|----------|-------|-----------|
| K26-1 | temp_db_path uses pytest's tmp_path for isolation | 26 | Each test gets fresh temporary directory |
| K26-2 | initialized_db patches src.storage.sqlite._DB_PATH | 26 | Allows CLI and storage to use test database |
| K26-3 | cli_runner uses session scope (stateless) | 26 | CliRunner has no state to preserve between tests |
| K27-1 | patch httpx at module level (src.providers.rss_provider.httpx) | 27 | Providers call httpx directly, not through abstraction |
| K27-2 | Async mocking via async function returning coroutine | 27 | For awaitable methods like AsyncClient.get() |
| K28-1 | Real SQLite via initialized_db (no mocking) | 28 | Ensures integration correctness |
| K28-2 | FK-first setup (feed → article → tag) | 28 | FK constraints require parent before child |
| K29-1 | patch instead of httpx_mock for CLI HTTP mocking | 29 | httpx_mock fixture not intercepting in CLI context |
| K29-2 | FTS5 queries avoid hyphens | 29 | Hyphens are exclusion operators in FTS5 syntax |

---

## 6. Tech Debt & Deferred Items

**Deferred from v1.7:**
- Phase 24 (Migration Script) — deferred; historical URL-like IDs will be addressed in future milestone
- Phase 25 (Verification) — deferred; nanoid verification postponed

**Deferred from prior milestones:**
- None

---

## 7. Getting Started

### Run the project
```bash
# Add a feed
python -m src.cli feed add https://example.com/feed.xml

# List feeds
python -m src.cli feed list

# Fetch all feeds
python -m src.cli fetch --all

# Search articles
python -m src.cli article search "keyword"

# Tag an article
python -m src.cli tag add <article-prefix> <tag>
```

### Key directories
- `src/cli/` — CLI command modules (feed, article, tag, fetch, search)
- `src/storage/` — SQLite storage layer (sqlite.py)
- `src/providers/` — RSS and GitHub content providers
- `src/tags/` — Tag parsing plugins
- `tests/` — All pytest tests

### Tests
```bash
# Run all tests
python -m pytest -v

# Run with coverage
python -m pytest --cov=src --cov-report=term-missing

# Run specific test files
python -m pytest tests/test_cli.py -v
python -m pytest tests/test_storage.py -v
python -m pytest tests/test_providers.py -v
```

### Where to look first
- `src/cli/__init__.py` — CLI entry point
- `src/storage/sqlite.py` — All database operations
- `tests/conftest.py` — Test fixtures and conventions

---

## Stats

- **Timeline:** 2026-03-24 → 2026-03-25 (~1 day)
- **Phases:** 4/4 complete
- **Commits:** 27 commits across milestone scope
- **Files changed:** 27 (+4740 insertions / -1601 deletions)
- **Tests:** 85 total (24 provider + 42 storage + 19 CLI)
- **Contributors:** Claude Code (automated)
