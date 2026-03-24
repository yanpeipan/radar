# Feed Provider Architecture

## Overview

Feed fetch is powered by a **plugin-based provider system**. Each URL type (RSS, GitHub, etc.) has its own provider that handles fetching, parsing, and tagging. No more `github_repos` table — everything is unified under `feeds` with provider logic handling type-specific behavior.

## Application Structure

```
src/
├── cli.py                    # CLI — thin wrappers (arg parsing + output)
├── application/
│   └── feed.py              # fetch_one(), fetch_all()
├── providers/
│   ├── rss_provider.py       # RSS/Atom feeds (priority 50)
│   └── github_release_provider.py  # GitHub releases (priority 200)
├── tags/
│   └── *.py                 # Tag parsers
└── utils/
    └── github.py             # GitHub API client singleton
```

## Fetch Flow

```
fetch --all
  └─ fetch_all()
       │
       ├─ feeds = list_feeds()
       │
       └─ for each feed:
            │
            └─ fetch_one(feed)
                 │
                 ├─ discover_or_default(feed.url) → provider (highest priority match)
                 │    └─ if no match: default RSS provider
                 │
                 ├─ raw_items = provider.crawl(feed.url)
                 │
                 ├─ articles = provider.parse(raw) for raw in raw_items
                 │
                 ├─ for article in articles:
                 │    ├─ INSERT OR IGNORE into articles (dedup by guid)
                 │    └─ if new: INSERT into articles_fts (FTS5 sync)
                 │
                 └─ apply tag_rules to new articles (post-commit, avoids DB lock)
```

```
feed refresh <feed_id>
  └─ fetch_one(feed_id)
       └─ (same as above, single feed)
```

**FTS5 sync:** New articles are synced to `articles_fts` shadow table immediately after INSERT. Tag rules run after commit to avoid "database is locked" from nested connections.

**No feed_rules stage:** Unlike the old flow, tagging is not provider-driven. All new articles after INSERT get `apply_rules_to_article()` called post-commit.

## Provider Interface

```python
class ContentProvider(ABC):
    @abstractmethod
    def match(self, url: str) -> bool:
        """Return True if this provider handles the URL."""

    @abstractmethod
    def priority(self) -> int:
        """Higher = tried first. Default RSS returns 50."""

    @abstractmethod
    def crawl(self, url: str) -> List[Raw]:
        """Fetch raw content from URL. Return list of raw items (may be empty)."""

    @abstractmethod
    def parse(self, raw: Raw) -> Article:
        """Convert raw item to Article dict."""

    def tag_parsers(self) -> List[TagParser]:
        """Return tag parsers for articles from this provider."""

    def parse_tags(self, article: Article) -> List[str]:
        """Parse tags for an article using all loaded tag parsers."""

    def feed_meta(self, url: str) -> Feed:
        """Fetch feed metadata (title, etc.) from URL without storing. Raises if unavailable."""
```

**Article dict shape:**
```python
{
    "title": str,
    "link": str,
    "guid": str,
    "pub_date": str | None,   # ISO 8601
    "description": str | None,
    "content": str | None,
}
```

## TagParser Interface

```python
class TagParser(ABC):
    @abstractmethod
    def parse_tags(self, article: Article) -> List[str]:
        """Return tags for this article."""
```

Tag merging: union of all tags from all tag parsers, deduplicated.
`['a', 'b'] + ['a', 'c'] = ['a', 'b', 'c']`

## Provider Registration

Providers register themselves by appending to `PROVIDERS` list in `src/providers/__init__.py`. Each provider class is instantiated once at module load time.

**Rule: Providers must not import each other** (avoid circular deps). Shared logic goes in `src/providers/base.py`.

## Database Schema

### feeds table

```sql
feeds (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  url TEXT NOT NULL,
  etag TEXT,
  last_modified TEXT,
  last_fetched TEXT,
  created_at TEXT NOT NULL,
  metadata TEXT  -- JSON, e.g. {"github_token": "ghp_xxx"}
)
```

### github_repos table — superseded

The `github_repos` table is no longer used. GitHub releases are fetched via `GitHubReleaseProvider` which calls the GitHub API directly (no local storage of release data).

## CLI Changes

| Command | Behavior |
|---------|----------|
| `feed add <url>` | Detects GitHub URLs → `add_feed` with GitHub routing; otherwise standard RSS add |
| `feed list` | List all subscribed feeds |
| `feed remove <id>` | Remove feed by ID |
| `feed refresh <id>` | Fetch new articles for one feed via `fetch_one()` |
| `fetch --all` | Fetch all feeds via `fetch_all()` |
| `crawl <url>` | Crawl arbitrary URL via Readability |

## Default RSS Provider

- `match(url)` returns `False` (only matched as fallback)
- When no provider matches: `discover_or_default` returns `[default_rss_provider]`
- `priority()` returns `50` (lowest; providers with higher priority are tried first)
