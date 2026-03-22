# Requirements: 个人资讯系统

**Defined:** 2026-03-23
**Core Value:** 用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。

## v1 Requirements

### GitHub Monitoring

- [x] **GH-01**: User can add a GitHub repository URL to monitor
- [x] **GH-02**: System fetches release information using GitHub API (tag_name, body, published_at, html_url)
- [x] **GH-03**: System supports GitHub token authentication via environment variable (GITHUB_TOKEN)
- [x] **GH-04**: System handles GitHub API rate limits gracefully (60 req/hour unauthenticated, 5000 req/hour with token)
- [ ] **GH-05**: System detects changelog files (CHANGELOG.md, HISTORY.md, etc.) via raw.githubusercontent.com
- [ ] **GH-06**: System scrapes changelog content and stores as article
- [ ] **GH-07**: New releases and changelog changes are displayed in unified format
- [ ] **GH-08**: System reuses existing refresh mechanism (fetch --all includes GitHub sources)

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

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| GH-01 | Phase 4 | Complete |
| GH-02 | Phase 4 | Complete |
| GH-03 | Phase 4 | Complete |
| GH-04 | Phase 4 | Complete |
| GH-05 | Phase 5 | Pending |
| GH-06 | Phase 5 | Pending |
| GH-07 | Phase 6 | Pending |
| GH-08 | Phase 6 | Pending |
| FEED-01 | Phase 1 (v1.0) | Complete |
| FEED-02 | Phase 1 (v1.0) | Complete |
| FEED-03 | Phase 1 (v1.0) | Complete |
| FEED-04 | Phase 1 (v1.0) | Complete |
| FETCH-01 | Phase 1 (v1.0) | Complete |
| FETCH-02 | Phase 1 (v1.0) | Complete |
| FETCH-03 | Phase 1 (v1.0) | Complete |
| FETCH-04 | Phase 1 (v1.0) | Complete |
| FETCH-05 | Phase 1 (v1.0) | Complete |
| CRAWL-01 | Phase 3 (v1.0) | Complete |
| CRAWL-02 | Phase 3 (v1.0) | Complete |
| CRAWL-03 | Phase 3 (v1.0) | Complete |
| CRAWL-04 | Phase 3 (v1.0) | Complete |
| STOR-01 | Phase 1 (v1.0) | Complete |
| STOR-02 | Phase 1 (v1.0) | Complete |
| STOR-03 | Phase 1 (v1.0) | Complete |
| STOR-04 | Phase 2 (v1.0) | Complete |
| CLI-01 | Phase 1 (v1.0) | Complete |
| CLI-02 | Phase 1 (v1.0) | Complete |
| CLI-03 | Phase 1 (v1.0) | Complete |
| CLI-04 | Phase 3 (v1.0) | Complete |
| CLI-05 | Phase 1 (v1.0) | Complete |
| CLI-06 | Phase 2 (v1.0) | Complete |
| CLI-07 | Phase 1 (v1.0) | Complete |

**Coverage:**
- v1 requirements: 35 total
- Mapped to phases: 35
- Unmapped: 0

---

*Requirements defined: 2026-03-23*
*Last updated: 2026-03-23 after v1.1 requirements definition*
