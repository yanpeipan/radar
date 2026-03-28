# Feed System

## Overview

Feed fetch is powered by a **plugin-based provider system**. Each URL type (RSS, GitHub, etc.) has its own provider that handles fetching, parsing, and tagging.

## Architecture

```
fetch --all
  └─ fetch_all_async()
       │
       ├─ feeds = list_feeds()
       │
       └─ concurrent fetch per feed:
            │
            ├─ discover_or_default(url) → provider (priority match)
            │
            ├─ provider.crawl(url) → raw items
            │
            ├─ provider.parse(raw) → Article dicts
            │
            ├─ store_article() with nanoid
            │    ├─ INSERT OR IGNORE into articles (dedup by guid)
            │    ├─ INSERT into articles_fts (FTS5)
            │    └─ apply tag_rules post-commit
            │
            └─ uvloop at CLI boundary
```

## Providers

| Provider | Priority | URL Pattern |
|----------|----------|-------------|
| GitHubReleaseProvider | 200 | github.com/*/releases |
| RSSProvider | 50 | (fallback) |

## Fetch Flow

- **Concurrency**: `asyncio.Semaphore` limits concurrent fetches (default 10, max 100)
- **Dedup**: Articles identified by guid, `INSERT OR IGNORE` prevents duplicates
- **FTS5 sync**: New articles indexed immediately after INSERT
- **Tag rules**: Applied post-commit to avoid DB lock contention
- **Conditional fetch**: ETag/Last-Modified headers for RSS feeds

## Async Pattern

All async operations use `uvloop.run()` at CLI boundaries only. Internal async code uses `asyncio.to_thread()` for blocking I/O to avoid "database is locked" errors.
