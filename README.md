# feedship

Personal information system for collecting, subscribing to, and organizing information sources from the internet.

## Features

- **Feed subscription** - RSS/Atom feeds and GitHub releases
- **Web article extraction** - Crawl webpages with Readability
- **Full-text search** - FTS5-powered search across all content
- **Semantic search** - Vector embeddings with ChromaDB
- **CLI tool** - Full-featured command-line interface

## Tech Stack

Python 3.10+ | click | feedparser | httpx | BeautifulSoup4 | sqlite3 | ChromaDB | sentence-transformers

## Installation

```bash
pip install feedship
# or
uv pip install feedship
```

### Optional Dependencies

```bash
# ML/AI features for auto-tagging
pip install feedship[ml]

# All features
pip install feedship[ml]
```

## Quick Start

### Add a Feed

```bash
feedship feed add <url> [options]

# Examples:
feedship feed add https://example.com/feed.xml
feedship feed add https://github.com/python/cpython

# Options:
--discover [on|off]          Enable feed discovery (default: on)
--automatic [on|off]          Auto-add all discovered feeds (default: off)
--discover-depth N           Discovery depth 1-10 (default: 1)
--weight FLOAT               Feed weight for semantic search (default: 0.3)
```

### Fetch & List

```bash
feedship fetch --all        # Fetch all feeds
feedship feed list          # List all feeds
feedship article list        # List articles
feedship article list --limit 50
```

### Search

```bash
feedship search "machine learning"
feedship search "python" --limit 10
```

## Documentation

- @docs/feed.md - Feed provider architecture, fetch flow, refactoring status
- @docs/providers.md - Provider/TagParser interfaces, registration
- @docs/structure.md - Application structure, source files, structural rules
- @docs/cli.md - CLI command reference
- @docs/Automatic Discovery Feed.md - Automatic feed discovery system
