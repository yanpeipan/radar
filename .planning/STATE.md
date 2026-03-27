---
gsd_state_version: 1.0
milestone: v1.8
milestone_name: ChromaDB 语义搜索
status: completed
stopped_at: Completed quick task 260327-g38
last_updated: "2026-03-27T03:38:00.000Z"
last_activity: "2026-03-27 — Completed quick task 260327-g38: 删除 orphaned crawl module files"
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 6
  completed_plans: 6
---

# Project State

## Project Reference

See: .planning/PROJECT.md (v1.8 milestone started)

**Core value:** 用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。
**Current focus:** Milestone v1.8 complete - ChromaDB semantic search

## Current Position

Phase: All 4 phases complete
Plan: —
Status: Milestone v1.8 complete
Last activity: 2026-03-27 — Completed quick task 260327-feu: remove preload_embedding_model from CLI init

## v1.8 Phase Structure

| Phase | Goal | Requirements |
|-------|------|--------------|
| 30 | Semantic Search Infrastructure | SEM-01, SEM-02, SEM-03 |
| 31 | Write Path - Incremental Embedding | SEM-06 |
| 32 | Query Path - Semantic Search CLI | SEM-04, SEM-05 |
| 33 | Polish - Error Handling | SEM-07 |

| Phase | Goal | Requirements |
|-------|------|--------------|
| 26 | pytest框架搭建 | TEST-01 |
| 27 | Provider单元测试 | TEST-02 |
| 28 | Storage层单元测试 | TEST-03 |
| 29 | CLI集成测试 | TEST-04 |

## Performance Metrics

**v1.0 velocity:**

- 3 phases, 9 plans, ~3 hours

**v1.1 velocity:**

- 4 phases, 10 plans, ~1 day

**v1.2 velocity:**

- 4 phases, 5 plans, ~1 day

**v1.4 velocity:**

- 3 phases (16, 17, 18), 4 plans, ~20 min
- Phase 16: GitHubReleaseProvider + ReleaseTagParser
- Phase 17: CLI package split + DB context manager
- Phase 18: Storage layer enforcement (16 new storage functions)

**v1.5 velocity:**

- 4 phases, 4 plans

**v1.7 velocity:**

- 4 phases, 4 plans (shipped 2026-03-25)

**v1.8 velocity:**

- 4 phases, 5 plans (ChromaDB semantic search shipped 2026-03-27)
- Phase 30: ChromaDB PersistentClient + sentence-transformers infrastructure
- Phase 31: Incremental embedding on fetch
- Phase 32: search --semantic + article related CLI commands
- Phase 33: Graceful error handling for ChromaDB edge cases

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.

- [Phase 16 added]: github_release_provider using pygithub repo.get_latest_release
- [Phase 12]: github_repos data migrated to feeds.metadata JSON
- [Phase 12]: migrate_drop_github_repos only runs if DB-02 actually migrated data
- [Phase 12]: Migration call wrapped in try/except for read-only database resilience
- [Phase 12]: Used @runtime_checkable Protocol for ContentProvider (structural typing)
- [Phase 12]: Self-registration via PROVIDERS.append() at module import time
- [Phase 12]: Error isolation at load time with try/except around importlib.import_module
- [Phase 13]: RSSProvider.match() uses httpx HEAD request to detect RSS/Atom content types
- [Phase 13]: GitHubProvider.match() supports both HTTPS and git@ SSH URL formats
- [Phase 13]: Both providers return [] for tag_parsers() and parse_tags() - chaining wired in Plan 02
- [Phase 13]: Providers sorted by priority descending: GitHub(100) > RSS(50) > Default(0)
- [Phase 13]: Circular import resolved via TYPE_CHECKING and lazy tag parser loading
- [Phase 14]: discover_or_default() is a module-level function in src.providers, not a class method
- [Phase 14-cli-integration]: Used discover_or_default() function directly rather than ProviderRegistry class
- [Phase 15]: Extracted parse_github_url to github_utils.py (pure URL parsing, no external deps)
- [Phase 15]: Extracted DB ops and changelog functions to github_ops.py using httpx/raw.githubusercontent.com
- [Phase 17-anti-refactoring]: RSSProvider.feed_meta uses httpx.get with 5s timeout instead of crawl()
- [Phase 18]: Added get_all_embeddings() and get_articles_without_embeddings() helper functions to storage to eliminate remaining get_db() calls in ai_tagging.py
- [Phase 18]: Storage layer enforcement: get_db() is internal to src/storage/ only - no direct database calls outside storage layer
- [Phase 21]: Used asyncio.Lock singleton + asyncio.to_thread() for SQLite write serialization (UVLP-05)
- [Phase 21]: Used asyncio.Semaphore for concurrency limiting, default 10 (UVLP-04)
- [Phase 23]: nanoid is a separate package (nanoid>=2.0.0), NOT part of uuid module
- [Phase 24]: FTS5 uses rowid linkage, NOT article id - FTS table does NOT need migration
- [Phase 24]: article_tags and article_embeddings reference article_id via FK - must update together
- [Phase 24]: Migration must use UPDATE not DELETE+INSERT to preserve FTS rowid linkage
- [Phase 23]: store_article() line 334 and add_tag() line 181 need uuid->nanoid replacement
- [Phase 27-01]: Used unittest.mock.patch for httpx mocking at module level (src.providers.rss_provider.httpx.head)
- [Phase 27-01]: Async mocking via async function returning coroutine for httpx.AsyncClient.get()
- [Phase 28-storage-unit-tests]: Used real SQLite via initialized_db fixture (tmp_path) for all storage tests - no mocking
- [Phase 30]: ChromaDB PersistentClient for local vector storage alongside SQLite
- [Phase 30]: sentence-transformers all-MiniLM-L6-v2 for 384-dim article embeddings
- [Phase 30]: Embedding model pre-downloaded at startup (not on first query)
- [Phase 31]: Incremental embedding on fetch - new articles automatically embedded
- [Phase 32]: search --semantic CLI using ChromaDB similarity search
- [Phase 32]: article related <id> using ChromaDB query_by_ids for similar articles
- [Phase 33]: Graceful error handling for articles without embeddings (pre-v1.8)
- [Phase 30]: D-03: ChromaDB uses sentence_transformers.SentenceTransformer(all-MiniLM-L6-v2)
- [Phase 30]: D-04: Model pre-download triggered during CLI startup alongside init_db()
- [Phase 30]: D-05: get_embedding_function() as public API with module-level caching
- [Phase ?]: [260327-ef6]: Extracted search result formatting logic to src/application/search.py - format_semantic_results converts L2 distance to cosine similarity, format_fts_results truncates fields for display

### Technical Notes

**Provider Architecture (v1.3):**

- Plugin directory: `src/providers/` and `src/tags/`
- Discovery: `glob()` + dynamic import, alphabetical order
- Rule: Providers must not import each other (avoid circular deps)
- Provider interface: match/priority/crawl/parse/tag_parsers/parse_tags
- Crawl failure: log.error and continue to next provider
- Tag merging: union of all tag parsers, deduplicated
- Default RSS: match() returns False, only used as fallback
- Database: feeds.metadata JSON field for provider-specific data

**v1.5 Async Architecture:**

- uvloop replaces asyncio event loop for 2-4x I/O improvement
- ContentProvider protocol extends with crawl_async() method
- Default crawl_async() uses run_in_executor to wrap sync crawl()
- RSSProvider.crawl_async() uses httpx.AsyncClient directly
- fetch_all_async() uses asyncio.Semaphore (default 10 concurrent)
- SQLite writes serialized via asyncio.to_thread() to avoid "database is locked"
- CLI wraps async code with uvloop.run()

**v1.8 ChromaDB Semantic Search Architecture:**

- ChromaDB PersistentClient with local directory storage
- sentence-transformers all-MiniLM-L6-v2 model (384-dim embeddings)
- Model pre-downloaded at startup via sentence_transformers pretrained
- ChromaDB collection: "articles" with id, content, title, url metadata
- Incremental embedding during fetch (async, non-blocking)
- Semantic search via ChromaDB query() with cosine similarity
- Related articles via query_by_ids() for similarity search

### Blockers/Concerns

- uvloop cannot run in non-main thread (certain Click invocations, IDE integrations)
- feedparser.parse() blocks event loop - must run in thread pool
- ChromaDB model download may block CLI startup (mitigate with background download)

## Session Continuity

Last session: 2026-03-27T02:41:22.010Z
Stopped at: Completed quick task 260327-eqg

## Quick Tasks Completed

| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|
| 260325-2am | src.cli fetch支持指定一个或多个链接 | 2026-03-24 | (pending) | Gaps | [260325-2am-src-cli-fetch](./quick/260325-2am-src-cli-fetch/) |
| 2026-03-25 | 260325-0a9 | db.py → src/storage/sqlite.py | Moved db.py to storage/, made _get_connection private, updated all imports, removed broken get_release_detail code |
| 2026-03-25 | 260325-035 | ai_tagging.py, tag_rules.py → src/tags/ | Moved to src/tags/, updated imports in default_tag_parser, feed, article, tag, test |
| 2026-03-24 | 260324-xau | github_utils.py → utils/github.py | Merged parse_github_url into utils/github.py, updated imports, deleted github_utils.py |
| 2026-03-24 | 260324-waj | README.md (259 lines) | Created comprehensive README with badges, features, tech stack, installation, CLI usage, config, project structure |
| 2026-03-24 | 260324-v34 | Refactor feeds.py to modules | Migrated generate_article_id/generate_feed_id to utils, add_feed/list_feeds/get_feed/remove_feed to application/feed.py, fetch_feed_content/parse_feed to rss_provider.py, deleted feeds.py |
| 2026-03-24 | 260324-0u6 | Remove github.py, github tables, github CLI commands, embedding code | Deleted 808-line github.py, removed github_repos/releases/release_tags tables from db.py, cleaned articles.py JOINs, removed repo command group from cli.py, removed embedding/clustering from tags.py, removed GitHub models |
| 2026-03-24 | 260324-fast | Fix feeds.py src.github import error | Removed src.github imports from feeds.py, deleted add_github_blob_feed function, removed github_blob handling from add_feed and refresh_feed |
| Phase 13 P01 | 62 | 2 tasks | 2 files |
| Phase 13 P02 | 12 | 3 tasks | 5 files |
| Phase 14 P01 | 2 | 1 tasks | 1 files |
| Phase 14 P03 | 2 | 1 tasks | 1 files |
| Phase 14-cli-integration P02 | 1774288413 | 2 tasks | 1 files |
| Phase 15-pygithub-refactor P01 | 3 | 4 tasks | 4 files |
| 2026-03-24 | fast | Added OpenAI RSS feed | ✅ |
| Phase 16-github-release-provider P01 | 180 | 3 tasks | 2 files |
| 2026-03-25 | 260324-x3k | articles.py, config.py, crawl.py | Moved to application module, imports updated across codebase |
| 2026-03-25 | 260324-x78 | 删除无用的文件 | Deleted 9 orphaned .pyc files from deleted modules |
| 2026-03-25 | 260324-x78 | 删除无用的文件 | Deleted 9 orphaned .pyc files from deleted modules |
| 2026-03-25 | milestone-v1.4 | MILESTONE_SUMMARY-v1.4.md | Generated milestone summary to .planning/reports/ |
| 260325-5mi | 增加Rich Progress bar到async fetch | 2026-03-24 | 33ea0e4 | ✅ | [260325-5mi-rich-progress-bar-async-fetch](./quick/260325-5mi-rich-progress-bar-async-fetch/) |
| Phase 19 P19-01 | 53 | 3 tasks | 3 files |
| Phase 19 P19-02 | 1 | 2 tasks | 2 files |
| Phase 20 P01 | 72 | 3 tasks | 1 files |
| Phase 21 P01 | <1 | 4 tasks | 4 files |
| Phase 27-provider-unit-tests P01 | 200 | 3 tasks | 1 files |
| Phase 28-storage-unit-tests P28-01 | 3min | 3 tasks | 1 files |
| 260326-t0b | 查看 bigmodel.cn glm-coding 套餐价格 | 2026-03-26 | 5f7e757 | Verified | [260326-t0b-bigmodel-cn-glm-coding](./quick/260326-t0b-bigmodel-cn-glm-coding/) |
| Phase 30 P30-01 | 0 | 2 tasks | 2 files |
| Phase 30 P30-02 | (see 30-02-SUMMARY.md) | 1 task | 1 files |
| Phase 30 P30-03 | 5min | 1 task | 3 files |
| Phase 31 P31-01 | <1 | 2 tasks | 2 files |
| Phase 31 P31-02 | <1 | 1 task | 1 files |
| Phase 32 P32-01 | 5 | 2 tasks | 3 files |
| Phase 33 P33-01 | 1 | 2 tasks | 2 files |
| 260327-dzr | search --semantic results include SQLite article ID | 2026-03-27 | a170354 | Verified | [260327-dzr-search-semantic-results-include-sqlite-a](./quick/260327-dzr-search-semantic-results-include-sqlite-a/) |
| 260327-e6m | Fix preload_embedding_model SSL errors crash CLI | 2026-03-27 | bcc4ff0 | Verified | [260327-e6m-fix-preload-embedding-model-ssl-errors-c](./quick/260327-e6m-fix-preload-embedding-model-ssl-errors-c/) |
| 260327-ef6 | Extract search logic from src/cli/article.py | 2026-03-27 | 6dd928a | Verified | [260327-ef6-extract-search-logic-from-src-cli-articl](./quick/260327-ef6-extract-search-logic-from-src-cli-articl/) |
| 260327-eqg | Move src/application/asyncio_utils.py to src/utils | 2026-03-27 | b6256bb | Verified | [260327-eqg-move-src-application-asyncio-utils-py-to](./quick/260327-eqg-move-src-application-asyncio-utils-py-to/) |
| 260327-f1q | Refactor fetch command URL case to use async loop with storage/embedding/tags | 2026-03-27 | 25dc28b | Verified | [260327-f1q-src-cli-feed-py-fetch-urls-should-also-c](./quick/260327-f1q-src-cli-feed-py-fetch-urls-should-also-c/) |
| 260327-feu | Remove preload_embedding_model from CLI init | 2026-03-27 | e091ed5 | Verified | [260327-feu-remove-preload-embedding-model-from-cli-](./quick/260327-feu-remove-preload-embedding-model-from-cli-/) |
| 260327-fsm | src/cli/feed.py 参数urls改为ids | 2026-03-27 | 00b3c16 | Verified | [260327-fsm-src-cli-feed-py-urls-ids](./quick/260327-fsm-src-cli-feed-py-urls-ids/) |
| 260327-g38 | 删除 orphaned crawl module files (src/application/crawl.py, src/cli/crawl.py) | 2026-03-27 | c3da6d0 | Verified | [260327-g38-remove-src-application-crawl-py-and-src-](./quick/260327-g38-remove-src-application-crawl-py-and-src-/) |
