# Requirements: 个人资讯系统

**Defined:** 2026-03-22
**Core Value:** 用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。

## v1 Requirements

### Feed Management

- [ ] **FEED-01**: User can add RSS/Atom feed by URL
- [ ] **FEED-02**: User can list all subscribed feeds
- [ ] **FEED-03**: User can remove a feed
- [ ] **FEED-04**: User can refresh a feed to fetch new articles

### Content Fetching

- [ ] **FETCH-01**: System can parse RSS 2.0 and Atom feeds
- [ ] **FETCH-02**: System extracts title, link, guid, pubDate, description from articles
- [ ] **FETCH-03**: System handles malformed XML gracefully (bozo detection)
- [ ] **FETCH-04**: System stores articles in SQLite with UNIQUE(feed_id, guid) deduplication
- [ ] **FETCH-05**: System supports conditional fetching (ETag/Last-Modified)

### Web Crawling

- [ ] **CRAWL-01**: User can add a website URL to crawl
- [ ] **CRAWL-02**: System fetches HTML and extracts article-like content
- [ ] **CRAWL-03**: System respects robots.txt directives
- [ ] **CRAWL-04**: System implements rate limiting (1-2s delay between requests)

### Storage

- [ ] **STOR-01**: SQLite database with WAL mode enabled
- [ ] **STOR-02**: Feeds table with name, url, last_fetched, etag, modified
- [ ] **STOR-03**: Articles table with feed_id, title, link, guid, pubDate, content
- [ ] **STOR-04**: FTS5 virtual table for full-text search

### CLI Interface

- [ ] **CLI-01**: `feed add <url>` - Add a new feed
- [ ] **CLI-02**: `feed list` - List all feeds
- [ ] **CLI-03**: `feed remove <id>` - Remove a feed
- [ ] **CLI-04**: `crawl <url>` - Fetch and store content from URL
- [ ] **CLI-05**: `article list` - List recent articles
- [ ] **CLI-06**: `article search <query>` - Search articles via FTS5
- [ ] **CLI-07**: `fetch --all` - Refresh all feeds

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
| FEED-01 | Phase 1 | Pending |
| FEED-02 | Phase 1 | Pending |
| FEED-03 | Phase 1 | Pending |
| FEED-04 | Phase 1 | Pending |
| FETCH-01 | Phase 1 | Pending |
| FETCH-02 | Phase 1 | Pending |
| FETCH-03 | Phase 1 | Pending |
| FETCH-04 | Phase 1 | Pending |
| FETCH-05 | Phase 2 | Pending |
| STOR-01 | Phase 1 | Pending |
| STOR-02 | Phase 1 | Pending |
| STOR-03 | Phase 1 | Pending |
| STOR-04 | Phase 2 | Pending |
| CLI-01 | Phase 1 | Pending |
| CLI-02 | Phase 1 | Pending |
| CLI-03 | Phase 1 | Pending |
| CLI-04 | Phase 2 | Pending |
| CLI-05 | Phase 1 | Pending |
| CLI-06 | Phase 2 | Pending |
| CLI-07 | Phase 1 | Pending |
| CRAWL-01 | Phase 2 | Pending |
| CRAWL-02 | Phase 2 | Pending |
| CRAWL-03 | Phase 2 | Pending |
| CRAWL-04 | Phase 2 | Pending |

**Coverage:**
- v1 requirements: 21 total
- Mapped to phases: 21
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-22*
*Last updated: 2026-03-22 after initial definition*
