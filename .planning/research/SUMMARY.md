# Research Summary: Personal RSS Reader and Website Crawler

**Synthesized:** 2026-03-23
**Source Files:** STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md

---

## 1. Key Findings by Research Area

### Stack (Libraries)
- **feedparser** is the standard for RSS/Atom parsing (handles bozo detection, encoding issues)
- **httpx** + **BeautifulSoup4** + **lxml** for HTTP fetching and HTML parsing
- **Playwright** as fallback for JavaScript-rendered SPAs
- **sqlite3** (built-in) sufficient for personal use; add SQLAlchemy only if needed
- **click** for CLI framework (decorator-based, composable)

### Architecture
- Pipeline pattern: sources → fetcher → parser → storage → CLI
- Repository pattern for storage abstraction
- Service layer for business logic encapsulation
- SQLite WAL mode enabled, foreign keys ON, proper indexing
- FTS5 virtual table with triggers for full-text search
- Structured logging with retry logic for error handling

### Features
- **Table stakes:** feed add/list/remove, RSS/Atom parsing, article storage, read/unread/bookmark, help/list commands, full-text search, OPML export
- **Differentiators:** website crawling, XPath scraping, scheduled fetching, content extraction, deduplication, ETag/Last-Modified, multiple output formats
- **Anti-features (avoid):** multi-user support, authentication, social features, cloud sync, podcast support, built-in AI

### Pitfalls (Top 5 Critical)
1. **Malformed feed parsing** - Use feedparser with bozo detection; implement fallback strategies
2. **GUID deduplication issues** - Fall back to link+pubDate hash when GUID missing; use SHA256 for content hashing
3. **SQLite concurrent writes** - Enable WAL mode, busy_timeout=5000, batch writes
4. **Rate limiting/blocking** - 1-2s delay between requests, respect robots.txt, polite User-Agent
5. **Date/time parsing chaos** - Normalize to UTC, handle RFC 822 and ISO 8601, log unparseable dates

---

## 2. Recommended Stack

| Component | Library | Version | Notes |
|-----------|---------|---------|-------|
| Feed parsing | feedparser | 6.0.x | RSS 0.9x-2.0, Atom, CDF |
| HTTP client | httpx | 0.27.x | Async/sync, HTTP/2 |
| HTML parsing | BeautifulSoup4 + lxml | 4.12.x / 5.x | Fast C-based parser |
| Browser automation | Playwright | 1.49.x | JS-rendered pages (optional) |
| Database | sqlite3 | (built-in) | WAL mode, FTS5 |
| CLI framework | click | 8.1.x | Decorator-based |
| ID generation | nanoid | - | Compact, URL-safe IDs |

**Minimal dependencies for MVP:**
```toml
dependencies = [
    "feedparser>=6.0.0",
    "httpx>=0.27.0",
    "beautifulsoup4>=4.12.0",
    "lxml>=5.0.0",
    "click>=8.1.0",
]
```

---

## 3. Table Stakes vs Differentiating Features

### Table Stakes (Must Have)
| Category | Feature |
|----------|---------|
| Feed Management | Add/list/remove feeds by URL, OPML import/export |
| Content Fetching | Parse RSS 2.0, Atom; extract title, URL, content, date |
| Data Storage | SQLite persistence, feed metadata, article storage |
| Read State | Mark read/unread, bookmark articles |
| CLI Interface | Help, list, add, remove, refresh commands |
| Search | Full-text search (FTS5), filter by feed/date/read status |

### Differentiating (Nice to Have)
| Category | Feature | Complexity |
|----------|---------|------------|
| Web Scraping | Website crawling, XPath extraction | High |
| Automation | Scheduled fetching, ETag/Last-Modified | Medium |
| Content | Content extraction (boilerplate stripping) | High |
| Deduplication | GUID/URL hash-based duplicate detection | Medium |
| Output | JSON/CSV/HTML export, multiple formats | Medium |
| Monitoring | Feed health tracking, change detection | Medium |

### MVP Phases
1. **Phase 1 (Core):** Feed subscription, refresh, article listing, read state, basic search, SQLite storage
2. **Phase 2 (Enhancement):** OPML import, bookmarking, output formats, better search filters, error handling
3. **Phase 3 (Differentiation):** Website crawling, XPath scraping, scheduled fetching, deduplication, content extraction

---

## 4. Critical Pitfalls to Watch

### Must Avoid (Rewrite-Level Impact)

| Pitfall | Impact | Prevention |
|---------|--------|------------|
| **Malformed XML/feed parsing** | Silent failures, missed items | Use feedparser bozo flag, fallback parsing, sanitize HTML |
| **Missing/unreliable GUID** | Duplicate floods | Fall back to link+pubDate hash; normalize URLs |
| **SQLite write contention** | Database locks, data loss | WAL mode, busy_timeout=5000, batch writes |
| **Rate limiting/blocking** | Feed unavailable, IP banned | 1-2s delay, polite User-Agent, robots.txt compliance |
| **robots.txt ignoring** | Legal risk, blocking | RFC 9309 parsing, cache max 24h, respect crawl-delay |

### Important (Rework-Level Impact)

| Pitfall | Impact | Prevention |
|---------|--------|------------|
| Date/time parsing | Wrong order, future dates | Normalize to UTC, handle RFC 822 and ISO 8601 |
| Deduplication hash collisions | Missed/new items | SHA256 for content, URL normalization (trailing slash, case) |
| CLI prompts in scripts | Automation breaks | TTY detection, --yes/--force flags, env var for secrets |
| CDATA handling | Content corruption | Use proper XML parser; feedparser handles correctly |
| Encoding mismatch | Mojibake | Default UTF-8, chardet fallback, handle Windows-1252 |

### SQLite Configuration (Critical)
```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=5000;
PRAGMA cache_size=-4000;  -- 4MB
PRAGMA foreign_keys=ON;
```

---

## 5. Quick Reference

### Project Structure
```
src/
├── cli.py              # CLI commands (click)
├── db.py               # Database operations (sqlite3)
├── feeds.py            # Feed parsing (feedparser)
├── scraper.py           # HTML scraping (httpx + bs4)
└── services/           # Business logic layer
```

### Database Indexes (Essential)
```sql
CREATE INDEX idx_articles_feed_id ON articles(feed_id);
CREATE INDEX idx_articles_published_at ON articles(published_at);
CREATE INDEX idx_articles_is_read ON articles(is_read);
```

### Phase-Specific Pitfall Mapping
| Phase | Primary Pitfalls |
|-------|------------------|
| Feed parsing | Malformed XML, missing GUID, date chaos, CDATA |
| Database schema | Write contention, hash collisions, pagination |
| HTTP fetching | Rate limiting, robots.txt, feed discovery |
| CLI interface | Interactive prompts, secret exposure, NO_COLOR |

---

**Confidence:** MEDIUM-HIGH (STACK), MEDIUM (ARCHITECTURE, FEATURES), MEDIUM-HIGH (PITFALLS)
