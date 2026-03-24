---
gsd_state_version: 1.0
milestone: v1.5
milestone_name: uvloop并发支持
status: Milestone complete — v1.5 shipped
stopped_at: Completed Phase 22 CLI Integration — v1.5 milestone shipped
last_updated: "2026-03-25T00:00:00.000Z"
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 3
  completed_plans: 3
---

# Project State

## Project Reference

See: .planning/PROJECT.md (v1.5 milestone started)

**Core value:** 用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。
**Current focus:** Phase 22 — cli-integration

## Current Position

Phase: 22 (cli-integration) — EXECUTING
Plan: 1 of 1

## v1.5 Phase Structure

| Phase | Goal | Requirements |
|-------|------|--------------|
| 19 | uvloop Setup + crawl_async Protocol | UVLP-01, UVLP-02 |
| 20 | RSSProvider Async HTTP | UVLP-03 |
| 21 | Concurrent Fetch + SQLite Serialization | UVLP-04, UVLP-05 |
| 22 | CLI Integration | UVLP-06, UVLP-07 |

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

**v1.5 estimated:**

- 4 phases, ~4 plans (coarse granularity)

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

### Blockers/Concerns

- uvloop cannot run in non-main thread (certain Click invocations, IDE integrations)
- feedparser.parse() blocks event loop - must run in thread pool

## Session Continuity

Last session: 2026-03-25T00:00:00.000Z
Stopped at: Completed Phase 22 CLI Integration — v1.5 milestone shipped

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
| 2026-03-24 | 260324-x3k | articles.py, config.py, crawl.py | Moved to application module, imports updated across codebase |
| 2026-03-25 | 260324-x78 | 删除无用的文件 | Deleted 9 orphaned .pyc files from deleted modules |
| 2026-03-25 | milestone-v1.4 | MILESTONE_SUMMARY-v1.4.md | Generated milestone summary to .planning/reports/ |
| 260325-5mi | 增加Rich Progress bar到async fetch | 2026-03-24 | 33ea0e4 | ✅ | [260325-5mi-rich-progress-bar-async-fetch](./quick/260325-5mi-rich-progress-bar-async-fetch/) |
| Phase 19 P19-01 | 53 | 3 tasks | 3 files |
| Phase 19 P19-02 | 1 | 2 tasks | 2 files |
| Phase 20 P01 | 72 | 3 tasks | 1 files |
| Phase 21 P01 | <1 | 4 tasks | 4 files |
