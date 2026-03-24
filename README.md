# rss-reader

A personal information system for collecting, subscribing to, and organizing information sources from the internet.

[![Python >=3.10](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **RSS/Atom feed subscription and parsing** - Subscribe to any RSS or Atom feed and automatically fetch new articles
- **GitHub releases tracking** - Track GitHub repository releases and get notified of new versions
- **Web article extraction with readability** - Crawl any webpage and extract the main content using Readability algorithm
- **SQLite local storage** - All data stored locally in a single SQLite database file
- **CLI tool with intuitive commands** - Full-featured command-line interface with rich formatting
- **Tag-based organization with AI auto-tagging** - Organize articles with tags, supports both manual tagging and AI-powered clustering
- **Full-text search across articles** - Fast FTS5-powered search across all article content

## Tech Stack

| Component | Technology |
|-----------|------------|
| Feed Parsing | feedparser 6.0.x |
| HTTP Client | httpx 0.28.x |
| HTML Parsing | BeautifulSoup4 4.12.x, lxml 5.x |
| Readability | readability-lxml |
| CLI Framework | click 8.1.x |
| Database | sqlite3 (built-in) |
| GitHub API | PyGithub 2.0.x |
| Rich Output | rich 13.x |
| Configuration | dynaconf 3.2.x |
| Clustering | scikit-learn, numpy |
| Sentence Embeddings | sentence-transformers (optional) |

## Installation

### Requirements

- Python >= 3.10
- pip or uv

### Standard Install

```bash
pip install rss-reader
```

### Install with uv

```bash
uv pip install rss-reader
```

### Install with Optional Dependencies

```bash
# With ML/AI features for auto-tagging
pip install rss-reader[ml]

# With Cloudflare bypass for restricted sites
pip install rss-reader[cloudflare]

# With all features
pip install rss-reader[ml,cloudflare]
```

## Quick Start

### Add a Feed

```bash
rss-reader feed add <url>
```

Examples:
```bash
# Add an RSS feed
rss-reader feed add https://example.com/feed.xml

# Add a GitHub repository releases
rss-reader feed add https://github.com/python/cpython
```

### List Feeds

```bash
rss-reader feed list
```

### Fetch All Feeds

```bash
rss-reader fetch --all
```

### Fetch a Single Feed

```bash
rss-reader feed refresh <feed-id>
```

### List Articles

```bash
rss-reader article list
rss-reader article list --limit 50
rss-reader article list --feed-id <feed-id>
rss-reader article list --tag AI
```

### View Article

```bash
rss-reader article view <article-id>
```

### Open Article in Browser

```bash
rss-reader article open <article-id>
```

### Tag Articles

```bash
# Manual tagging
rss-reader article tag <article-id> <tag-name>

# Auto-tag with AI clustering
rss-reader article tag --auto

# Apply keyword/regex rules to untagged articles
rss-reader article tag --rules
```

### Search Articles

```bash
rss-reader search "machine learning"
rss-reader search "python" --limit 10
```

### Crawl a Webpage

```bash
rss-reader crawl https://example.com/article
```

### Manage Tags

```bash
# Create a tag
rss-reader tag add AI

# List all tags
rss-reader tag list

# Remove a tag
rss-reader tag remove AI
```

### Tag Rules

```bash
# Add a keyword rule
rss-reader tag rule add AI --keyword "machine learning" --keyword "deep learning"

# Add a regex rule
rss-reader tag rule add Security --regex "CVE-\\d+"

# List all rules
rss-reader tag rule list

# Edit a rule
rss-reader tag rule edit AI --add-keyword "neural network"

# Remove a rule
rss-reader tag rule remove AI --keyword "machine learning"
```

## Configuration

Configuration is managed via `config.yaml` using dynaconf.

Default config location: `~/.config/rss-reader/` (Linux/macOS) or `%APPDATA%\rss-reader\` (Windows)

### Example config.yaml

```yaml
settings:
  database_path: ~/.local/share/rss-reader/data.db
  log_level: INFO
  fetch:
    timeout: 30
    max_articles_per_feed: 100
  crawl:
    respect_robots_txt: true
    user_agent: "rss-reader/1.0"
```

## Project Structure

```
src/
├── __init__.py           # Package init
├── cli.py                # CLI entry point and all commands
├── articles.py           # Article operations (list, search, view)
├── db.py                 # Database connection and schema
├── crawl.py              # Web crawling and content extraction
├── ai_tagging.py         # AI clustering for auto-tagging
├── tag_rules.py          # Keyword/regex tagging rules
├── models.py             # Data models (Feed, Article, Tag)
├── config.py             # Configuration loading
├── github_utils.py       # GitHub URL parsing utilities
├── application/
│   └── feed.py           # Feed business logic (add, list, remove, fetch)
├── providers/
│   ├── __init__.py       # Provider registry
│   ├── base.py           # Provider base classes and protocols
│   ├── rss_provider.py   # RSS/Atom feed provider
│   └── github_release_provider.py  # GitHub releases provider
├── tags/
│   ├── __init__.py       # Tag parser registry
│   ├── default_tag_parser.py   # Keyword/regex tag parser
│   └── release_tag_parser.py   # GitHub release tag parser
└── utils/
    └── id.py             # ID generation utilities
```

### Architecture

- **Plugin-based providers**: RSS and GitHub providers are loaded dynamically
- **Provider priority**: GitHub (200) > RSS (50) - higher priority providers are tried first
- **Tag chaining**: Multiple tag parsers can contribute tags to a single article
- **FTS5 search**: Full-text search using SQLite's FTS5 virtual table

## License

MIT License

Copyright (c) 2024

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
