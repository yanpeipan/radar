---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: Phase complete — ready for verification
stopped_at: Completed 08-01-PLAN.md
last_updated: "2026-03-23T05:28:09.791Z"
progress:
  total_phases: 9
  completed_phases: 8
  total_plans: 21
  completed_plans: 20
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-23)

**Core value:** 用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。
**Current focus:** Phase 08 — github-url-metadata

## Current Position

Phase: 08 (github-url-metadata) — EXECUTING
Plan: 1 of 1

## Performance Metrics

**Velocity (v1.0):**

- Total plans completed: 9
- Total execution time: ~3 hours

**By Phase (v1.0):**

| Phase | Plans | Avg/Plan |
|-------|-------|----------|
| 1. Foundation | 3 | ~8 min |
| 2. Search & Refresh | 4 | ~32 min |
| 3. Web Crawling | 2 | ~2 min |
| Phase 04-github-api-client-releases-integration P04-01 | 2 | 3 tasks | 3 files |
| Phase 04-github-api-client-releases-integration P04-02 | 1 min | 2 tasks | 2 files |
| Phase 05-changelog-detection-scraping P05-01 | 48 | 2 tasks | 2 files |
| Phase 05-changelog-detection-scraping P05-02 | 2 | 1 tasks | 1 files |
| Phase 06-unified-display-refresh-integration P06-01 | 2 | 3 tasks | 1 files |
| Phase 06-unified-display-refresh-integration P06-02 | 5 | 3 tasks | 1 files |
| Phase 06-unified-display-refresh-integration P06-03 | 1 | 1 tasks | 1 files |
| Phase 07-tagging-system P07-01 | 4 | 7 tasks | 4 files |
| Phase 08 P01 | 5 | 3 tasks | 1 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.

**v1.0 decisions:**

- GUID fallback chain: guid -> link -> SHA256(link:pubDate) ensures unique article IDs
- Bozo detection via feed.bozo flag logs malformed XML but continues processing
- INSERT OR IGNORE + UNIQUE(feed_id, guid) handles duplicate articles silently
- Shadow FTS5 approach: articles_fts virtual table indexes title, description, content with porter tokenizer
- FTS5 query syntax exposed directly (space-separated = AND)
- Multiple keywords default to AND behavior
- Results sorted by bm25 ranking (relevance)
- Same format as article list command (title | feed | date columns)
- article search subcommand with --limit and --feed-id filter options
- crawl command accepts URL argument and --ignore-robots flag
- CLI echoes errors in red, no-content in yellow, success in green

**v1.1 decisions:**

- GitHub Releases using GitHub API
- GitHub Changelog using Scrapling web scraping
- Phase 4: GitHub API Client + Releases Integration (GH-01, GH-02, GH-03, GH-04)
- Phase 5: Changelog Detection + Scraping (GH-05, GH-06)
- Phase 6: Unified Display + Refresh Integration (GH-07, GH-08)
- [Phase 06-unified-display-refresh-integration]: UNION ALL pattern for combining feed articles and GitHub releases in list_articles
- [Phase 06-unified-display-refresh-integration]: LIKE search for GitHub releases (body not in FTS5) - avoids schema changes
- [Phase 07-tagging-system]: Tag auto-creation: When tagging an article with non-existent tag, tag is automatically created
- [Phase 07-tagging-system]: OR tag filtering: Multiple tags in filter use OR logic (article has tag A OR tag B)
- [Phase 07]: Keyword/regex tag rules stored in ~/.radar/tag-rules.yaml with case-insensitive matching
- [Phase 08]: D-GH01: Detect GitHub URL type BEFORE fetching using URL pattern matching
- [Phase 08]: D-GH02: Use GitHub Contents API for blob URLs to get file metadata
- [Phase 08]: D-GH03: Title format {owner}/{repo} / {H1} or {owner}/{repo} / {filename}
- [Phase 08]: D-GH04: Use GitHub Commits API for pub_date on commits URLs
- [Phase 08]: D-GH05: Graceful fallback on GitHub API failure (rate limit, network error)

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-03-23T05:28:09.786Z
Stopped at: Completed 08-01-PLAN.md
Resume file: None
