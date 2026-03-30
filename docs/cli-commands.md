# Feedship CLI Commands

Complete reference for all Feedship CLI commands.

## Table of Contents

- [Global Options](#global-options)
- [feed add](#feed-add)
- [feed list](#feed-list)
- [feed remove](#feed-remove)
- [fetch](#fetch)
- [article list](#article-list)
- [article view](#article-view)
- [article open](#article-open)
- [article related](#article-related)
- [search](#search)
- [discover](#discover)

---

## Global Options

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Enable verbose output |
| `--version` | Show version |
| `-h, --help` | Show help |

---

## feed add

Add a new feed by URL with automatic feed type detection.

```bash
feedship feed add <url> [options]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `<url>` | Website URL or direct feed URL |

### Options

| Option | Description |
|--------|-------------|
| `--auto-discover/--no-auto-discover` | Enable feed auto-discovery (default: enabled) |
| `--automatic` | Automatically add all discovered feeds (on/off, default: off) |
| `--discover-depth` | Discovery crawl depth 1-10 (default: 1) |
| `--weight FLOAT` | Feed weight for semantic search (default: 0.3) |

### Behavior

1. Connects to the URL and discovers available feeds
2. If `--automatic on`: Adds all discovered feeds automatically
3. Otherwise: Shows feed list and prompts for selection
4. GitHub URLs are automatically detected and handled by GitHub provider

### Examples

```bash
# Add a website with auto-discovery
feedship feed add https://example.com

# Add and auto-accept all discovered feeds
feedship feed add https://example.com --automatic on

# Add with deeper discovery crawl
feedship feed add https://example.com --discover-depth 3

# Add a direct feed URL
feedship feed add https://example.com/feed.xml

# Add GitHub releases feed
feedship feed add https://github.com/python/cpython
```

### Output

```
Discovered 2 feed(s) in 0.5s
#  Type    Title                     URL
1  RSS     Example Blog              https://example.com/feed.xml
2  Atom    Example Site News         https://example.com/atom.xml

Select feeds to add:
  a - Add all feeds
  s - Select individually
  c - Cancel
```

---

## feed list

List all subscribed feeds with their status.

```bash
feedship feed list [options]
```

### Options

| Option | Description |
|--------|-------------|
| `-v, --verbose` | Show detailed output for each feed |

### Output (default)

| Column | Description |
|--------|-------------|
| Id | Feed ID (8 characters) |
| Name | Feed name/title |
| Type | Provider type (RSS/GitHub) |
| Articles | Number of articles |
| Weight | Semantic search weight |
| Last Fetched | Timestamp of last fetch (YYYY-MM-DD) |

### Output (verbose)

Detailed view with full ID, URL, type, article count, weight, and last fetched timestamp.

### Examples

```bash
# List all feeds
feedship feed list

# List with full details
feedship feed list --verbose
feedship feed list -v
```

---

## feed remove

Remove a subscribed feed by ID.

```bash
feedship feed remove <feed-id>
```

### Arguments

| Argument | Description |
|----------|-------------|
| `<feed-id>` | Feed ID to remove |

### Behavior

- Removes the feed and all associated articles from the database
- Cannot be undone

### Examples

```bash
# Remove a feed by ID
feedship feed remove abc12345
```

---

## fetch

Fetch new articles from subscribed feeds.

```bash
feedship fetch [options] [ids...]
```

### Options

| Option | Description |
|--------|-------------|
| `--all` | Fetch all subscribed feeds |
| `--concurrency` | Max concurrent fetches 1-100 (default: 10) |

### Arguments

| Argument | Description |
|----------|-------------|
| `<ids>` | Specific feed IDs to fetch (optional) |

### Behavior

- **Single ID**: Fetches one feed directly with detailed output
- **Multiple IDs**: Fetches specified feeds with concurrency control
- **--all flag**: Fetches all subscribed feeds with concurrency control
- Uses Rich progress bar to show fetch progress

### Examples

```bash
# Fetch all feeds
feedship fetch --all

# Fetch specific feed
feedship fetch abc12345

# Fetch multiple feeds
feedship fetch abc12345 def67890

# Fetch all with higher concurrency
feedship fetch --all --concurrency 20
```

### Output

```
Fetching 5 feeds (concurrency:10)...
✓ Fetched 12 articles from Feed Name (3.2s)
  • 5 new, 7 updated

Summary:
  ✓ 4 feeds succeeded
  ✗ 1 feed failed
  Total: 15 new articles
```

---

## article list

List articles with optional filtering.

```bash
feedship article list [options]
```

### Options

| Option | Description |
|--------|-------------|
| `--limit` | Maximum articles to show (default: 20) |
| `--feed-id` | Filter by specific feed ID |
| `--since` | Start date (YYYY-MM-DD) |
| `--until` | End date (YYYY-MM-DD) |
| `--on` | Specific date (YYYY-MM-DD, can repeat for multiple) |

### Output

| Column | Description |
|--------|-------------|
| ID | Article ID (8 characters) |
| Title | Article title (clickable link) |
| Source | Feed name (truncated) |
| Date | Publication date (YYYY-MM-DD) |

### Examples

```bash
# List recent articles
feedship article list

# List last 50 articles
feedship article list --limit 50

# Articles from specific feed
feedship article list --feed-id abc12345

# Articles from date range
feedship article list --since 2026-03-01 --until 2026-03-30

# Articles on specific date
feedship article list --on 2026-03-30

# Multiple specific dates
feedship article list --on 2026-03-28 --on 2026-03-29 --on 2026-03-30
```

---

## article view

View full article content and metadata.

```bash
feedship article view <article-id>
```

### Arguments

| Argument | Description |
|----------|-------------|
| `<article-id>` | Article ID to view |

### Output

- **Header**: Article title in panel
- **Metadata table**: Source, Type, Date, Link
- **Content**: Full article text (if available)

### Examples

```bash
# View article content
feedship article view abc12345
```

---

## article open

Open article in system browser.

```bash
feedship article open <article-id>
```

### Arguments

| Argument | Description |
|----------|-------------|
| `<article-id>` | Article ID to open |

### Behavior

Opens the article's URL in the default system browser:
- macOS: Uses `open` command
- Linux: Uses `xdg-open` command
- Windows: Uses `start` command

### Examples

```bash
# Open article in browser
feedship article open abc12345
```

---

## article related

Find articles related to a specific article using semantic similarity.

```bash
feedship article related <article-id> [options]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `<article-id>` | Article ID to find related articles for |

### Options

| Option | Description |
|--------|-------------|
| `--limit` | Maximum related articles to show (default: 5) |

### Behavior

Uses ChromaDB vector similarity search to find articles with similar content to the specified article.

### Examples

```bash
# Find 5 related articles
feedship article related abc12345

# Find 10 related articles
feedship article related abc12345 --limit 10
```

---

## search

Search articles using full-text or semantic search.

```bash
feedship search <query> [options]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `<query>` | Search query string |

### Options

| Option | Description |
|--------|-------------|
| `--limit` | Maximum results (default: 20) |
| `--feed-id` | Filter by specific feed ID |
| `--semantic` | Use semantic search instead of keyword search |
| `--rerank` | Apply Cross-Encoder reranking to results |
| `--since` | Start date (YYYY-MM-DD) |
| `--until` | End date (YYYY-MM-DD) |
| `--on` | Specific date (YYYY-MM-DD, can repeat) |

### Search Modes

1. **FTS5 (default)**: Full-text search using SQLite FTS5
   - Fast keyword matching
   - `--feed-id` filter available
   - Uses BM25 scoring combined with other signals

2. **Semantic**: Vector similarity search using sentence-transformers
   - Understands meaning, not just keywords
   - Requires `[ml]` extra installed
   - Combined score: alpha=0.3 (FTS5), beta=0.3 (freshness), gamma=0.2 (semantic), delta=0.0

3. **With reranking**: Cross-Encoder model reorders results
   - More accurate but slower
   - Works with both FTS5 and semantic modes

### Examples

```bash
# Basic keyword search
feedship search "machine learning"

# Limit results
feedship search "python" --limit 10

# Semantic search
feedship search "machine learning" --semantic

# Semantic search with reranking
feedship search "machine learning" --semantic --rerank

# Search in specific feed
feedship search "python" --feed-id abc12345

# Search with date filter
feedship search "news" --since 2026-03-01

# Combined: semantic + reranking + date filter
feedship search "machine learning" --semantic --rerank --since 2026-03-01
```

---

## discover

Discover RSS/Atom/RDF feeds from a website without subscribing.

```bash
feedship discover <url> [options]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `<url>` | Website URL to discover feeds from |

### Options

| Option | Description |
|--------|-------------|
| `--discover-depth` | Crawl depth 1-10 (default: 1) |

### Behavior

- Crawls the website to find all available feeds
- Depth 1: Only current page
- Depth 2+: BFS crawl to discover feeds across the site
- Shows feed type (RSS/Atom/RDF), title, and URL

### Examples

```bash
# Discover feeds on current page
feedship discover example.com

# Deeper crawl to find more feeds
feedship discover example.com --discover-depth 3
```

### Output

```
#  Type    Title                     URL
1  RSS     Example Blog              https://example.com/feed.xml
2  Atom    Example Site News         https://example.com/atom.xml

Discovered 2 feed(s) in 1.2s
```
