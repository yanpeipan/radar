# Provider System

## Provider Interface

```python
class ContentProvider(Protocol):
    def match(self, url: str) -> bool:
        """Return True if this provider handles the URL."""

    def priority(self) -> int:
        """Higher = tried first. Default RSS returns 50."""

    def crawl(self, url: str) -> List[Raw]:
        """Fetch raw content from URL."""

    def parse(self, raw: Raw) -> Article:
        """Convert raw item to Article dict."""

    def feed_meta(self, url: str) -> FeedMeta:
        """Fetch feed metadata (title, etag) WITHOUT crawling full content."""

    def tag_parsers(self) -> List[TagParser]:
        """Return tag parsers for articles from this provider."""
```

## TagParser Interface

```python
class TagParser(Protocol):
    def parse_tags(self, article: Article) -> List[str]:
        """Return tags for this article."""
```

Tag merging: union of all tags from all tag parsers, deduplicated.

## Providers

### RSSProvider (priority 50)

Fallback provider for RSS 2.0, Atom 1.0, RDF feeds.

- `match(url)` returns `False` (only matched as fallback)
- `priority()` returns `50` (lowest)
- `feed_meta()` does lightweight HEAD request only
- Supports ETag/Last-Modified conditional fetching

### GitHubReleaseProvider (priority 200)

Handles GitHub repository release pages.

- `match(url)` detects `github.com/*/releases`
- Returns releases as articles with `tag` field set to version
- No tag parsers needed (tags from release versions)

### DefaultProvider

Fallback when no provider matches. Handles arbitrary URLs via HTML scraping.

## Registration

Providers register in `src/providers/__init__.py`. Higher priority = tried first.

**Rule**: Providers must not import each other (avoid circular deps). Shared logic goes in `src/providers/base.py`.
