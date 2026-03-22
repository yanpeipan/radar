# Requirements: 个人资讯系统

**Defined:** 2026-03-22
**Core Value:** 用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。

## v1 Requirements

### Feed Management

- [x] **FEED-01**: User can add RSS/Atom feed by URL
- [x] **FEED-02**: User can list all subscribed feeds
- [x] **FEED-03**: User can remove a feed
- [x] **FEED-04**: User can refresh a feed to fetch new articles

### Content Fetching

- [x] **FETCH-01**: System can parse RSS 2.0 and Atom feeds
- [x] **FETCH-02**: System extracts title, link, guid, pubDate, description from articles
- [x] **FETCH-03**: System handles malformed XML gracefully (bozo detection)
- [x] **FETCH-04**: System stores articles in SQLite with UNIQUE(feed_id, guid) deduplication
- [x] **FETCH-05**: System supports conditional fetching (ETag/Last-Modified) — Implemented in Phase 1

### Web Crawling

- [x] **CRAWL-01**: User can add a website URL to crawl
- [x] **CRAWL-02**: System fetches HTML and extracts article-like content
- [x] **CRAWL-03**: System respects robots.txt directives
- [x] **CRAWL-04**: System implements rate limiting (1-2s delay between requests)

### Storage

- [x] **STOR-01**: SQLite database with WAL mode enabled
- [x] **STOR-02**: Feeds table with name, url, last_fetched, etag, modified
- [x] **STOR-03**: Articles table with feed_id, title, link, guid, pubDate, content
- [x] **STOR-04**: FTS5 virtual table for full-text search

### CLI Interface

- [x] **CLI-01**: `feed add <url>` - Add a new feed
- [x] **CLI-02**: `feed list` - List all feeds
- [x] **CLI-03**: `feed remove <id>` - Remove a feed
- [ ] **CLI-04**: `crawl <url>` - Fetch and store content from URL
- [x] **CLI-05**: `article list` - List recent articles
- [x] **CLI-06**: `article search <query>` - Search articles via FTS5
- [x] **CLI-07**: `fetch --all` - Refresh all feeds

## v2 Requirements

### Enhanced Features

- **CRAWL-05**: XPath-based selective content extraction
- **FETCH-06**: OPML import/export for feed subscription backup
- **STOR-05**: Read state persistence (mark as read/unread)
- **STOR-06**: Article bookmarking
- **CLI-08**: Multiple output formats (JSON, CSV)

### Automation

- **AUTO-01**: Scheduled fetching via cron integration
- **AUTO-02**: Configurable fetch interval per feed
- **AUTO-03**: Deduplication across all sources

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-user support | Personal tool, single user |
| Cloud sync | Local-first design |
| Mobile app | CLI-first, web interface later |
| Social features | Out of scope |
| OAuth/API authentication | Not needed for personal use |
| Content extraction (Readability) | High complexity, defer to v2 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FEED-01 | Phase 1 | Complete |
| FEED-02 | Phase 1 | Complete |
| FEED-03 | Phase 1 | Complete |
| FEED-04 | Phase 1 | Complete |
| FETCH-01 | Phase 1 | Complete |
| FETCH-02 | Phase 1 | Complete |
| FETCH-03 | Phase 1 | Complete |
| FETCH-04 | Phase 1 | Complete |
| FETCH-05 | Phase 1 | Complete |
| STOR-01 | Phase 1 | Complete |
| STOR-02 | Phase 1 | Complete |
| STOR-03 | Phase 1 | Complete |
| STOR-04 | Phase 2 | Complete |
| CLI-01 | Phase 1 | Complete |
| CLI-02 | Phase 1 | Complete |
| CLI-03 | Phase 1 | Complete |
| CLI-04 | Phase 3 | Pending |
| CLI-05 | Phase 1 | Complete |
| CLI-06 | Phase 2 | Complete |
| CLI-07 | Phase 1 | Complete |
| CRAWL-01 | Phase 3 | Complete |
| CRAWL-02 | Phase 3 | Complete |
| CRAWL-03 | Phase 3 | Complete |
| CRAWL-04 | Phase 3 | Complete |

**Coverage:**
- v1 requirements: 21 total
- Mapped to phases: 21
- Unmapped: 0

---
*Requirements defined: 2026-03-22*
*Last updated: 2026-03-23 after roadmap creation*
