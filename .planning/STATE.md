---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: Ready to execute
stopped_at: Completed 10-01-PLAN.md
last_updated: "2026-03-23T08:25:00.000Z"
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 4
  completed_plans: 3
---

# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** 用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。
**Current focus:** Phase 10 — article-detail-view

## Current Position

Phase: 10
Plan: 01 planned

### Phase Status

| Phase | Status | Plans | Completed |
|-------|--------|-------|-----------|
| 9. Enhanced Article List | Complete | 1/1 | 2026-03-23 |
| 10. Article Detail View | Ready to execute | 1/1 | - |
| 11. GitHub Release Tagging | Not started | 0/1 | - |

## Performance Metrics

**v1.0 velocity:**

- 3 phases, 9 plans, ~3 hours

**v1.1 velocity:**

- 4 phases, 10 plans, ~1 day

**v1.2 (current):**

- 3 phases planned

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
- UNION ALL pattern for combining feed articles and GitHub releases in list_articles
- LIKE search for GitHub releases (body not in FTS5) - avoids schema changes
- Tag auto-creation: When tagging an article with non-existent tag, tag is automatically created
- OR tag filtering: Multiple tags in filter use OR logic
- Keyword/regex tag rules stored in ~/.radar/tag-rules.yaml with case-insensitive matching

**v1.2 decisions:**

- Using `rich` library for terminal table formatting (Phase 9)
- Detail view via rich Panel/Markdown rendering (Phase 10)
- GitHub release tagging requires schema decision (Phase 11)

### Technical Notes

**Phase 9 (Enhanced Article List):**

- N+1 query problem: current `article list` calls `get_article_tags()` per article
- Fix: JOIN or batch query in `list_articles_with_tags()`
- Truncated ID (8 chars) for display, full ID (32 chars) for commands

**Phase 10 (Detail View):**

- `get_article()` missing `content` field in SELECT clause
- Must add `content` to SELECT when implementing detail view
- Open in browser: `open` (macOS) / `xdg-open` (Linux)

**Phase 11 (GitHub Release Tagging):**

- `article_tags` table FK points to `articles.id`
- GitHub releases are in separate `github_releases` table
- Schema change or error handling needed before tagging works

### Blockers/Concerns

None identified.

## Session Continuity

Last session: 2026-03-23T08:25:00Z
Stopped at: Completed 10-01-PLAN.md
Resume file: None
