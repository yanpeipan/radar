---
gsd_state_version: 1.0
milestone: v1.9
milestone_name: Automatic Discovery Feed
status: verifying
stopped_at: Completed Phase 37-01 plan - Deep Crawling (37-01-SUMMARY.md)
last_updated: "2026-03-27T12:46:12.000Z"
last_activity: 2026-03-27 - Completed quick task 260327-tpu: Replace httpx with Scrapling Fetcher in deep_crawl
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 6
  completed_plans: 6
---

# Project State

## Project Reference

See: .planning/PROJECT.md (v1.9 milestone started)

**Core value:** 用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。
**Current focus:** Phase 37 — deep-crawling

## Current Position

Phase: 37
Plan: Not started
Status: Phase complete — ready for verification
Last activity: 2026-03-27

## v1.9 Phase Structure

| Phase | Goal | Requirements | Status |
|-------|------|--------------|--------|
| 34. Discovery Core Module | Core discovery engine | DISC-01, DISC-02, DISC-03, DISC-04 | ✅ Complete |
| 35. Discovery CLI Command | `discover <url>` command | DISC-05 | ✅ Complete |
| 36. Feed Add Integration | `--discover` and `--automatic` flags | DISC-06 | ✅ Complete |
| 37. Deep Crawling | BFS crawler, robots.txt, documentation | DISC-07, DISC-08, DISC-09 | Pending |

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

**v1.9 velocity:**

- 4 phases, 9 requirements (roadmap defined)

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
- [v1.9]: Discovery is a separate service module (src/discovery/), NOT a Provider plugin
- [v1.9]: Phase order: Core module → CLI → Integration → Deep crawl
- [Phase 35]: discover CLI uses uvloop.run() pattern consistent with feed.py fetch commands
- [Phase 36]: feed add --discover/--automatic/--discover-deep integration; _display_feeds() extended with numbered parameter; Selection UI via "a/s/c" prompt with range parsing
- [Phase 37]: RobotExclusionRulesParser (not RobotFileParser) - correct import name from robotexclusionrulesparser package
- [Phase 37]: robots.txt lazy mode per plan spec: only check when depth > 1
- [Phase 37]: asyncio.Semaphore(5) limits concurrent requests to 5 per depth level

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

**v1.9 Discovery Architecture (planned):**

- Discovery service module: `src/discovery/`
- No new dependencies (uses existing httpx, BeautifulSoup)
- Discovery flow: HTML parse → link tags + path probing → URL resolution → feed validation
- Deep crawl: BFS with visited-set, rate limiting (2s/host), robots.txt via robotexclusionrulesparser

### Blockers/Concerns

- uvloop cannot run in non-main thread (certain Click invocations, IDE integrations)
- feedparser.parse() blocks event loop - must run in thread pool
- ChromaDB model download may block CLI startup (mitigate with background download)

## Session Continuity

Last session: 2026-03-27T12:46:12.000Z
Stopped at: Completed Quick Task 260327-sp3 - regex-based feed path matching

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
| 2026-03-24 | fast | Added OpenAI RSS feed | — |
| Phase 16-github-release-provider P01 | 180 | 3 tasks | 2 files |
| 2026-03-25 | 260324-x3k | articles.py, config.py, crawl.py | Moved to application module, imports updated across codebase |
| 2026-03-25 | 260324-x78 | 删除无用的文件 | Deleted 9 orphaned .pyc files from deleted modules |
| 2026-03-25 | 260324-x78 | 删除无用的文件 | Deleted 9 orphaned .pyc files from deleted modules |
| 2026-03-25 | 260324-x78 | milestone-v1.4 | MILESTONE_SUMMARY-v1.4.md | Generated milestone summary to .planning/reports/ |
| 260325-5mi | 增加Rich Progress bar到async fetch | 2026-03-24 | 33ea0e4 | — | [260325-5mi-rich-progress-bar-async-fetch](./quick/260325-5mi-rich-progress-bar-async-fetch/) |
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
| 260327-ghv | src/cli/article.py 保持代码行数少于200，cli层不做业务逻辑 | 2026-03-27 | e535741 | Verified | [260327-ghv-src-cli-article-py-200-cli-application](./quick/260327-ghv-src-cli-article-py-200-cli-application/) |
| 260327-h4z | Refactor CLI fetch command to use fetch_ids_async from application layer | 2026-03-27 | a844ee4 | Verified | [260327-h4z-src-cli-feed-py-200-cli-application](./quick/260327-h4z-src-cli-feed-py-200-cli-application/) |
| 260327-hmk | 删除 feed_refresh 命令，和 fetch <id> 功能重叠 | 2026-03-27 | fc212a8 | Verified | [260327-hmk-feed-refresh-fetch-ids](./quick/260327-hmk-feed-refresh-fetch-ids/) |
| 260327-jju | 优化 fetch <feed_id> 响应速度，使用 async-native 路径 | 2026-03-27 | bd03fef | Verified | [260327-jju-python-m-src-cli-fetch-feed-id](./quick/260327-jju-python-m-src-cli-fetch-feed-id/) |
| 260327-jt7 | 删除全部 tag 功能（CLI 命令、storage 函数、models、providers、tests） | 2026-03-27 | d75f37d | Verified | [260327-jt7-tag-dead-code](./quick/260327-jt7-tag-dead-code/) |
| Phase 35 P35-01 | 3 | 3 tasks | 2 files |
| Phase 36 P36-01 | ~5 | 3 tasks | 2 files |
| Phase 37 P37-01 | <5 | 4 tasks | 5 files |
| 260327-sp3 | Implement regex-based feed path matching with generate_feed_candidates() | 2026-03-27 | e5e38d9 | Verified | [260327-sp3-implement-regex-based-feed-path-matching](./quick/260327-sp3-implement-regex-based-feed-path-matching/) |
| 260327-t7d | Refactor src/discovery HTML parsing from BeautifulSoup to Scrapling | 2026-03-27 | b12cf01 | Verified | [260327-t7d-scrapling-src-discovery](./quick/260327-t7d-scrapling-src-discovery/) |
| 260327-tpu | Replace httpx with Scrapling Fetcher in deep_crawl | 2026-03-27 | bbe0da8 | Verified | [260327-tpu-replace-beautifulsoup-with-scrapling-in-](./quick/260327-tpu-replace-beautifulsoup-with-scrapling-in-/) |
