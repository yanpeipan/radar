# Requirements: 个人资讯系统

**Defined:** 2026-03-23
**Core Value:** 用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。

## v1 Requirements

All v1.0 and v1.1 requirements have been completed and archived in milestones.

| Requirement | Phase | Status |
|-------------|-------|--------|
| GH-01 through GH-08 | Phase 4-6 (v1.1) | Complete |
| FEED-01 through FEED-04 | Phase 1 (v1.0) | Complete |
| FETCH-01 through FETCH-05 | Phase 1 (v1.0) | Complete |
| CRAWL-01 through CRAWL-04 | Phase 3 (v1.0) | Complete |
| STOR-01 through STOR-04 | Phase 1-2 (v1.0) | Complete |
| CLI-01 through CLI-07 | Phase 1-3 (v1.0) | Complete |

See `.planning/milestones/` for archived requirement sets.

## v1.2 Requirements

**Milestone:** Article List Enhancements
**Goal:** Show id/tags in article list, add detail view, enable GitHub release tagging

### Article List Display

- [ ] **ARTICLE-01**: User can see article ID (truncated to 8 chars) in `article list` output
- [ ] **ARTICLE-02**: User can see tags in a separate column in `article list` output
- [ ] **ARTICLE-03**: Fix N+1 query performance when loading tags (batch query or JOIN)
- [ ] **ARTICLE-04**: `article list --verbose` shows full article IDs for command usage

### Article Detail View

- [x] **ARTICLE-05**: User can view full article detail with `article view <id>` command
- [x] **ARTICLE-06**: Detail shows title, source/feed, date, tags, link, and full content

### GitHub Release Tagging

- [x] **GITHUB-01**: User can tag GitHub releases using `article tag <id>`
- [x] **GITHUB-02**: Tags work for both feed articles and GitHub releases (unified tagging)

### Open in Browser

- [x] **ARTICLE-07**: User can open article link in browser with `article open <id>`

## Future (Backlog)

- [ ] JSON/CSV export format for article list
- [ ] OPML import/export
- [ ] Read/unread status
- [ ] Article bookmarks
- [ ] Scheduled auto-crawl (cron)

## Out of Scope

- Complex classification/categorization beyond tags
- Multi-user support
- Cloud sync
- Share functionality
- Mobile app

## Traceability

| REQ-ID | Phase | Description |
|--------|-------|-------------|
| ARTICLE-01 | 9 | Article list ID column |
| ARTICLE-02 | 9 | Article list tags column |
| ARTICLE-03 | 9 | N+1 query fix |
| ARTICLE-04 | 9 | Verbose flag for full IDs |
| ARTICLE-05 | 10 | Article detail view command |
| ARTICLE-06 | 10 | Full content in detail |
| ARTICLE-07 | 10 | Open in browser |
| GITHUB-01 | 11 | GitHub release tagging |
| GITHUB-02 | 11 | Unified tag operations |

---
*Requirements created: 2026-03-23 for v1.2 milestone*
