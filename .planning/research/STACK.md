# Technology Stack: Personal Information System

**Project Type:** CLI tool for RSS subscription and website crawling
**Researched:** 2026-03-22 (v1.0), 2026-03-23 (v1.1 additions), 2026-03-23 (v1.2 additions), 2026-03-23 (v1.3 plugin architecture), 2026-03-25 (v1.5 uvloop concurrency), 2026-03-25 (v1.6 nanoid)
**Confidence:** HIGH

## Recommended Stack

### RSS Parsing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **feedparser** | 6.0.x | Universal feed parser | Handles RSS 0.9x, RSS 1.0, RSS 2.0, CDF, Atom 0.3, Atom 1.0. The de-facto standard for feed parsing in Python. Active maintenance, Python >=3.6 support. |

**Installation:** `pip install feedparser`

**Basic Usage:**
```python
import feedparser
feed = feedparser.parse('https://example.com/feed.xml')
for entry in feed.entries:
    print(entry.title, entry.link)
```

---

### HTML Scraping

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **httpx** | 0.27.x | HTTP client | Modern async/sync HTTP client with requests-compatible API. HTTP/2 support. Use for fetching HTML pages. |
| **BeautifulSoup4** | 4.12.x | HTML parsing | Intuitive navigation of parsed HTML. Works with multiple parsers (html.parser built-in, lxml, html5lib). |
| **lxml** | 5.x | Fast parser | C-based HTML/XML parser. Recommended backend for BeautifulSoup (faster than html.parser). |
| **Playwright** | 1.49.x | Browser automation | For JavaScript-rendered pages. Supports Chromium, WebKit, Firefox. Headless or headed. Use as fallback for SPA sites. |

**Installation:**
```bash
pip install httpx beautifulsoup4 lxml
pip install playwright && playwright install  # Optional, for JS sites
```

**Basic Usage (static pages):**
```python
import httpx
from bs4 import BeautifulSoup

response = httpx.get('https://example.com')
soup = BeautifulSoup(response.text, 'lxml')
for link in soup.find_all('a', class_='article-link'):
    print(link.get('href'))
```

**Basic Usage (JavaScript-rendered pages):**
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://example.com')
    content = page.content()
    browser.close()
```

---

### SQLite Database

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **sqlite3** | (built-in) | Database | No external dependencies. DB-API 2.0 compliant. Sufficient for personal information system with moderate data volumes. |
| **SQLAlchemy** | 2.0.x | ORM (optional) | Only if you need complex relationships, migrations, or prefer ORM-style code. Adds dependency overhead. |

**Recommendation:** Start with `sqlite3` (built-in). Add SQLAlchemy only if relationships or migration tooling become necessary.

**sqlite3 Basic Usage:**
```python
import sqlite3

con = sqlite3.connect('data.db')
cur = con.cursor()

# Create table
cur.execute('''CREATE TABLE IF NOT EXISTS feeds
               (id INTEGER PRIMARY KEY, url TEXT UNIQUE, title TEXT)''')

# Insert with parameterized query (prevents SQL injection)
cur.execute('INSERT OR IGNORE INTO feeds (url, title) VALUES (?, ?)',
            ('https://example.com/feed.xml', 'Example Feed'))

# Query
for row in cur.execute('SELECT * FROM feeds'):
    print(row)

con.commit()
con.close()
```

**Row Factory for dict-like access:**
```python
con.row_factory = sqlite3.Row
row = cur.execute('SELECT * FROM feeds').fetchone()
print(row['url'])  # Access by column name
```

---

### CLI Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **click** | 8.1.x | CLI framework | Decorator-based, composable, automatic help generation. Most popular modern CLI framework for Python. |
| **argparse** | (built-in) | CLI framework | Standard library. More verbose than click. Use only if avoiding dependencies is critical. |

**Recommendation:** **click** for its clean decorator syntax and widespread adoption.

**Installation:** `pip install click`

**Basic Usage:**
```python
import click

@click.group()
def cli():
    """Personal Information System CLI."""
    pass

@cli.command()
@click.option('--count', default=1, help='Number of items to process')
@click.argument('url')
def fetch(count, url):
    """Fetch entries from a feed URL."""
    click.echo(f'Fetching {count} entries from {url}')

@cli.command()
def list():
    """List all subscribed feeds."""
    click.echo('Listing all feeds...')

if __name__ == '__main__':
    cli()
```

---

## v1.1 Addition: GitHub Monitoring

### GitHub Releases API (httpx - already installed)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| httpx | 0.27.x | GitHub REST API calls | Already in use. Direct REST calls with Bearer token auth are straightforward. No new dependency needed. |

**No new installation required** - use existing httpx.

**Basic Usage:**
```python
import httpx

headers = {
    "Authorization": f"Bearer {github_token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

# List releases
response = httpx.get(
    f"https://api.github.com/repos/{owner}/{repo}/releases",
    headers=headers,
    timeout=10.0
)
releases = response.json()

# Get latest release
response = httpx.get(
    f"https://api.github.com/repos/{owner}/{repo}/releases/latest",
    headers=headers
)
latest = response.json()
# Fields: tag_name, name, body (markdown), published_at, html_url, author
```

**Rate Limits:** 60 req/hr unauthenticated, 5000 req/hr authenticated (with personal access token).

**For unauthenticated (rate limited):**
```python
# Works without token, 60 req/hr limit
response = httpx.get(
    f"https://api.github.com/repos/{owner}/{repo}/releases/latest",
    headers={"Accept": "application/vnd.github+json"}
)
```

---

### GitHub Changelog Scraping

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **scrapling** | 0.4.2 | Adaptive web scraping with JS support | Handles dynamic content, undetected scraping, flexible extraction. Already decided in PROJECT.md. Python >=3.10 required. |

**Installation:**
```bash
pip install scrapling==0.4.2
```

**IMPORTANT:** scrapling 0.4.2 requires **Python >=3.10**. Verify your project minimum before adding.

**Basic Usage:**
```python
from scrapling import PySpider

# Initialize spider (auto-installs browser drivers if needed)
spider = PySpider(auto_install_drivers=True)

# Option 1: Raw content URL (no JS needed)
url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/CHANGELOG.md"
page = spider.fetch(url)
content = page.find("body").text if page.find("body") else page.text

# Option 2: GitHub web view (JS rendering for rendered markdown)
url = f"https://github.com/{owner}/{repo}/blob/main/CHANGELOG.md"
page = spider.fetch(url)
# Find rendered markdown body
content = page.find(".markdown-body").text
```

**With fetchers extra (recommended for GitHub):**
```bash
pip install "scrapling[fetchers]"
```

```python
from scrapling import PySpider

spider = PySpider(auto_install_drivers=True)  # Uses Playwright under the hood

# Fetch GitHub page with JS rendering
page = spider.fetch(f"https://github.com/{owner}/{repo}/blob/main/CHANGELOG.md")
content = page.find(".markdown-body").text
```

**Changelog file patterns to try:**
- `CHANGELOG.md` (most common)
- `CHANGELOG`
- `HISTORY.md`
- `CHANGES.md`
- `RELEASES.md`

---

## v1.2 Addition: Article List Enhancements and Detail View

### Rich Terminal Display

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **rich** | 13.x | Terminal formatting | All-in-one solution for tables, panels, markdown rendering. Single dependency handles both id/tags columns in list AND detail view. Drop-in enhancement with click integration. |

**Installation:**
```bash
pip install rich
```

**For article list with id/tags columns:**
```python
from rich.console import Console
from rich.table import Table

console = Console()

table = Table(show_header=True, header_style="bold magenta")
table.add_column("ID", style="dim", width=8)
table.add_column("Tags", max_width=15)
table.add_column("Title")
table.add_column("Source", max_width=20)
table.add_column("Date", max_width=10)

for article in articles:
    tags = ",".join(get_article_tags(article.id)) or "-"
    table.add_row(
        article.id[:8],
        tags,
        article.title or "No title",
        article.feed_name[:20],
        (article.pub_date or "")[:10]
    )

console.print(table)
```

**For detail subcommand:**
```python
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

# Option 1: Plain text panel
console.print(Panel(article.content or article.description, title=article.title))

# Option 2: If content is HTML, convert to markdown first
import html2text
h = html2text.HTML2Text()
h.ignore_links = False
markdown_content = h.handle(article.content)
console.print(Panel(Markdown(markdown_content), title=article.title))
```

**Why rich over alternatives:**
- `tabulate` - Only handles tables, no panels/colors for detail view
- `textwrap` - Too low-level, manual formatting
- `urwid` - Full TUI framework, overkill for this use case
- `blessed` - Lower-level, less Pythonic API than rich

### Supporting Library (Conditional)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **html2text** | 2024.x | HTML to Markdown conversion | Only if `articles.content` stores raw HTML that needs conversion for terminal display |

**Check before adding:** Examine stored article content. If `content` is already plain text or markdown, html2text is unnecessary.

**Installation (if needed):**
```bash
pip install html2text
```

**Basic Usage:**
```python
import html2text

h = html2text.HTML2Text()
h.ignore_links = False  # Preserve links in output
markdown = h.handle(html_content)
```

---

## v1.3 Addition: Plugin/Provider Architecture

### Core Plugin Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pluggy** | 1.5.0 (installed) | Hook specification and plugin management | Industry standard (pytest, tox, devpi). Provides `PluginManager` with `load_setuptools_entrypoints()` for discovery. Active maintenance, MIT license. |
| **importlib.metadata** | built-in (Python 3.9+) | Plugin discovery via entry points | Standard library for discovering installed packages and their entry points. `entry_points()` returns `EntryPoints` object. |

**No new dependencies required** - pluggy is already installed.

### Hook Specification Pattern (using pluggy)

Define what providers must implement via hook specs:

```python
# src/providers/hooks.py
from pluggy import HookspecMarker, HookimplMarker

hookspec = HookspecMarker("rss_reader")
hookimpl = HookimplMarker("rss_reader")

class SourceProviderSpec:
    """Hook specification for content source providers."""

    @hookspec
    def provider_name(self) -> str:
        """Return unique provider identifier."""

    @hookspec
    def add_source(self, url: str) -> "SourceResult":
        """Add a new source by URL."""

    @hookspec
    def refresh_source(self, source_id: str) -> "RefreshResult":
        """Refresh a source to fetch new content."""

    @hookspec
    def list_sources(self) -> list["Source"]:
        """List all managed sources."""
```

### Provider Implementation Pattern

Each provider implements the hooks:

```python
# src/providers/rss_provider.py
from pluggy import HookimplMarker

class RSSProvider:
    """RSS/Atom feed provider implementation."""

    @HookimplMarker("rss_reader")
    def provider_name(self) -> str:
        return "rss"

    @HookimplMarker("rss_reader")
    def add_source(self, url: str):
        # ... existing add_feed logic
        return result

    # ... other implementations
```

### Plugin Manager Pattern

Central manager loads and coordinates providers:

```python
# src/providers/manager.py
from pluggy import PluginManager

class ProviderManager:
    """Manages all content source providers."""

    def __init__(self):
        self.pm = PluginManager("rss_reader")
        # Load built-in providers
        self.pm.register(RSSProvider(), name="rss")
        self.pm.register(GitHubProvider(), name="github")
        # Load external plugins via entry points
        self.pm.load_setuptools_entrypoints("rss_reader")

    def get_provider(self, name: str):
        return self.pm.get_plugin(name)

    def hook(self, name: str, **kwargs):
        """Call a hook across all providers."""
        return getattr(self.pm.hook, name)(**kwargs)
```

### Circular Import Avoidance Patterns

**Pattern 1: TYPE_CHECKING Guard**
```python
# src/providers/hooks.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models import Feed, Article  # Only for type hints
```

**Pattern 2: Lazy Import (Import Inside Function)**
```python
# src/providers/base.py
class ProviderBase:
    def some_method(self):
        from src.db import get_connection  # Deferred import
        conn = get_connection()
```

**Pattern 3: Protocol/ABC with String Annotations**
```python
# src/providers/protocols.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class SourceProvider(Protocol):
    def provider_name(self) -> str: ...
    def add_source(self, url: str) -> "dict": ...  # String annotation
```

### Discovery Mechanisms

**Entry Points (Recommended for External Plugins)**

In `pyproject.toml`:
```toml
# For the main app
[project.entry-points."rss_reader.providers"]
rss = "src.providers.rss:RSSProvider"
github = "src.providers.github:GitHubProvider"

# For external plugins (third-party)
[project.entry-points."rss_reader.providers"]
hackernews = "hackernews_provider:HackerNewsProvider"
```

Loading in code:
```python
pm.load_setuptools_entrypoints("rss_reader.providers")
```

**Directory Scanning (For Built-in/Local Plugins)**
```python
import pkgutil
import importlib
from pathlib import Path

def discover_local_providers():
    """Discover providers in src/providers/ directory."""
    providers = []
    package_dir = Path(__file__).parent
    for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
        if module_name.endswith("_provider"):
            module = importlib.import_module(f"src.providers.{module_name}")
            # Find provider class and register
    return providers
```

### Provider Interface Contract

For v1.3, each provider must implement:

| Method | Purpose | Returns |
|--------|---------|---------|
| `provider_name()` | Unique identifier | `str` |
| `add_source(url)` | Add a new source | `dict` with success/error |
| `refresh_source(source_id)` | Fetch new content | `dict` with new_articles count |
| `list_sources()` | List managed sources | `list[dict]` |
| `remove_source(source_id)` | Remove a source | `bool` |

### Proposed Directory Structure for v1.3

```
src/
├── providers/              # NEW: Plugin architecture
│   ├── __init__.py         # ProviderManager exports
│   ├── hooks.py            # Hook specifications (pluggy)
│   ├── manager.py          # Provider registry
│   ├── rss_provider.py     # RSS/Atom provider (migrated from feeds.py)
│   └── github_provider.py  # GitHub provider (migrated from github.py)
├── cli.py                  # Updated to use ProviderManager
├── feeds.py                # Deprecate after migration
└── github.py              # Deprecate after migration
```

---

## v1.5 Addition: uvloop Async Concurrency

### Overview

Adding async concurrency to the existing sync codebase requires **minimal stack changes**. uvloop and anyio are already installed. httpx has built-in async support. The primary work is architectural (converting sync to async patterns).

### Current State

| Package | Current Version | Status |
|---------|----------------|--------|
| uvloop | 0.22.1 | Already installed |
| httpx | 0.28.1 | Sync only currently |
| anyio | 4.7.0 | Already installed (httpx dependency) |
| feedparser | 6.0.12 | No async version |
| sqlite3 | built-in | Not async-safe |

### Required Changes

| Change | Purpose | Complexity |
|--------|---------|------------|
| `uvloop.install()` at app entry | Replace asyncio event loop with uvloop | Trivial (1 line) |
| `httpx.AsyncClient` | Replace sync `httpx.get()` calls | Moderate (multiple call sites) |
| `asyncio.Semaphore(10)` | Concurrency limit (default 10x) | Trivial |
| `asyncio.Queue` for writes | Serialize SQLite writes | Moderate |

### No New Dependencies

**All necessary packages are already installed.** The changes are architectural, not dependency additions.

### httpx Async Client Pattern

**Current sync code:**
```python
import httpx
response = httpx.get(url, headers=BROWSER_HEADERS, timeout=30.0, follow_redirects=True)
```

**Async replacement:**
```python
import httpx

async def fetch_url(url: str) -> httpx.Response:
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=BROWSER_HEADERS, timeout=30.0, follow_redirects=True)
        return response
```

### Integration Points (src/providers/rss_provider.py)

| Line | Current | Replace With |
|------|---------|--------------|
| 55 | `httpx.get(url, ...)` | `httpx.AsyncClient().get(url)` |
| 135 | `httpx.head(url, ...)` | `httpx.AsyncClient().head(url)` |
| 318 | `httpx.get(url, ...)` | `httpx.AsyncClient().get(url)` |

### Integration Points (src/application/crawl.py)

| Line | Current | Replace With |
|------|---------|--------------|
| 233 | `httpx.get(robots_url, ...)` | async client |
| 263 | `httpx.get(robots_check_url, ...)` | async client |

### Concurrency Control Pattern

```python
import asyncio
import httpx

# Semaphore limits concurrent requests (default 10x)
concurrency_limit = asyncio.Semaphore(10)

async def fetch_with_limit(url: str, client: httpx.AsyncClient) -> httpx.Response:
    async with concurrency_limit:
        return await client.get(url, timeout=30.0)

async def fetch_feed_batch(urls: list[str]) -> list[httpx.Response]:
    async with httpx.AsyncClient() as client:
        tasks = [fetch_with_limit(url, client) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=True)
```

### feedparser: Run in Thread Pool

feedparser has no async version. Use `run_in_executor` to avoid blocking:

```python
import asyncio
import feedparser
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=10)

async def parse_feed_async(content: bytes) -> list:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, feedparser.parse, content)
```

### SQLite Write Serialization

SQLite writes must remain serial per project requirements. Use an asyncio Queue:

```python
import asyncio
import sqlite3
from typing import Tuple

write_queue: asyncio.Queue = asyncio.Queue()

async def enqueue_write(sql: str, params: tuple):
    """Queue a write operation for serial processing."""
    await write_queue.put((sql, params))

async def write_worker(db_path: str):
    """Single writer processes queue serially."""
    conn = sqlite3.connect(db_path)
    while True:
        sql, params = await write_queue.get()
        conn.execute(sql, params)
        conn.commit()
        write_queue.task_done()

async def init_write_worker(db_path: str):
    """Start the serial write worker."""
    asyncio.create_task(write_worker(db_path))
```

### CLI Integration with uvloop

click 8.1.x supports `@click.async_command()`:

```python
import asyncio
import click
import uvloop

@click.command()
@click.argument('url')
async def fetch(ctx: click.Context, url: str):
    """Fetch a feed URL."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        click.echo(response.text[:200])

def main():
    uvloop.install()
    asyncio.run(fetch())

if __name__ == '__main__':
    main()
```

However, for existing sync commands like `fetch --all`, wrap in `asyncio.run()`:

```python
# In src/cli/feed.py fetch command
def fetch(ctx: click.Context, do_fetch_all: bool, urls: tuple):
    if do_fetch_all:
        uvloop.install()
        asyncio.run(fetch_all_async())
```

### Recommended Architecture

```
src/
├── async/                      # NEW: Async utilities
│   ├── __init__.py
│   ├── client.py              # httpx.AsyncClient wrapper
│   ├── concurrency.py        # Semaphore, queue management
│   └── executor.py           # Thread pool for feedparser
├── providers/
│   ├── rss_provider.py        # Convert crawl/feed_meta to async
│   └── github_provider.py    # Convert to async if needed
├── application/
│   ├── feed.py                # fetch_all becomes async
│   └── crawl.py              # crawl_url becomes async
└── cli/
    └── feed.py                # Wrap async calls with asyncio.run()
```

---

## v1.6 Addition: nanoid ID Generation

### Overview

Replacing `uuid.uuid4()` with `nanoid.generate()` for shorter (21 chars vs 36 chars) URL-safe article IDs.

### Current State

| Package | Current Version | Status |
|---------|----------------|--------|
| nanoid | NOT INSTALLED | **Must add to dependencies** |
| uuid | built-in | Currently used for article IDs |

**Important:** Quality gate states "nanoid v3.16.0 installed" but verification shows:
```bash
$ python3 -c "import nanoid"
ModuleNotFoundError: No module named 'nanoid'
```

### Required Changes

#### 1. Add Dependency to pyproject.toml

Add to `dependencies` array:
```toml
nanoid = ">=3.16.0"
```

#### 2. Replace uuid.uuid4() in sqlite.py

**File:** `src/storage/sqlite.py`

**Line 334 (store_article function) - INSERT new article:**
```python
# Before:
import uuid
article_id = str(uuid.uuid4())

# After:
from nanoid import generate
article_id = generate()
```

**Line 181 (add_tag function):**
```python
# Before:
import uuid
tag_id = str(uuid.uuid4())

# After:
from nanoid import generate
tag_id = generate()
```

### nanoid API

```python
from nanoid import generate

# Default: 21-char URL-safe ID using alphabet A-Za-z0-9_-
article_id = generate()

# Custom size (if shorter IDs desired)
short_id = generate(size=12)
```

### No Conflicts with Existing Code

**generate_article_id() in src/utils/__init__.py:**
This function derives an ID from feed entry data (guid/link/hash). It does NOT generate the database `id` column. It is NOT affected by this migration.

**feed_id in utils:**
`generate_feed_id()` at line 15 of `src/utils/__init__.py` uses `uuid.uuid4()`. Decision needed: migrate feed IDs or leave as-is (feeds are fewer, URL-like IDs less problematic for feeds).

### Migration Considerations

**Existing articles (~2479) with URL-like IDs:**
- articles table has `UNIQUE(feed_id, id)` constraint
- article_tags table has foreign key to articles(id)
- articles_fts FTS5 table references articles by id

**Migration approach:**
1. Generate new nanoid for each existing article
2. Update article_tags first (FK dependency)
3. Update articles table
4. Re-sync FTS5 table

### Alternatives Considered

| Option | Status | Why Not |
|--------|--------|---------|
| `uuid.uuid4()` (current) | Rejected | 36 chars, not URL-safe |
| `hashlib` + timestamp | Rejected | Collision risk, not random enough |
| `secrets.token_urlsafe()` | Alternative | Built-in, but nanoid is shorter (21 vs 22 chars) |

---

## Project Structure Best Practices

```
my_rss_tool/
├── pyproject.toml          # Package metadata, dependencies
├── src/
│   └── my_rss_tool/
│       ├── __init__.py
│       ├── cli.py          # CLI commands (click)
│       ├── db.py           # Database operations (sqlite3)
│       ├── feeds.py        # Feed parsing (feedparser)
│       ├── scraper.py      # HTML scraping (httpx + bs4)
│       ├── github.py       # GitHub API + changelog (httpx + scrapling) [v1.1]
│       ├── monitors.py     # Monitor management [v1.1]
│       └── providers/      # Plugin architecture [v1.3]
│           ├── __init__.py
│           ├── hooks.py
│           ├── manager.py
│           └── ...
├── tests/
│   └── ...
├── data/                   # SQLite database storage
│   └── .gitkeep
└── README.md
```

**pyproject.toml dependencies (v1.6):**
```toml
[project]
dependencies = [
    "feedparser>=6.0.0",
    "httpx>=0.27.0",
    "beautifulsoup4>=4.12.0",
    "lxml>=5.0.0",
    "click>=8.1.0",
    "scrapling>=0.4.2",     # v1.1: Changelog scraping
    "rich>=13.0.0",         # v1.2: Terminal display enhancement
    "pluggy>=1.5.0",        # v1.3: Plugin framework (already installed)
    "nanoid>=3.16.0",      # v1.6: Shorter URL-safe IDs
    # "html2text>=2024.0.0", # v1.2: Only if article.content is HTML
]
requires-python = ">=3.10"   # v1.1: Bumped from 3.6+ to 3.10+
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| HTTP Client | httpx | requests | httpx has async support and HTTP/2. requests is fine if sync-only needed. |
| Feed Parser | feedparser | planet (aggregator) | planet is an aggregator framework, not a parser. feedparser is the standard parsing library. |
| HTML Parser | BeautifulSoup4 + lxml | lxml directly | BeautifulSoup provides more convenient navigation API. |
| Browser Automation | Playwright | Selenium | Playwright has better Python support and faster execution. |
| Database | sqlite3 | PostgreSQL, MySQL | Personal tool doesn't need server-based database. |
| ORM | sqlite3 (built-in) | SQLAlchemy, Django ORM | Adds complexity. sqlite3 is sufficient for personal use cases. |
| CLI Framework | click | typer | Both are good. click has larger ecosystem and more examples. typer is more Pythonic but adds dependency on fastapi utilities. |
| GitHub API Client | httpx (direct) | PyGithub | httpx handles REST API fine with simple Bearer token auth. PyGithub adds unnecessary dependency. |
| Changelog Scraping | scrapling | Playwright only | scrapling is adaptive wrapper around Playwright with easier API. Keep Playwright for complex cases. |
| Terminal Display | rich | tabulate + manual | rich handles both tables AND detail view (panels, markdown). Single dep over multiple. |
| Plugin Framework | pluggy | stevedore | stevedore is more complex (OpenStack). pluggy is simpler and already installed. |
| Plugin Framework | pluggy | yapsy | yapsy is older with less active maintenance. pluggy is the pytest standard. |
| Plugin Discovery | Entry points | Directory scanning | Entry points better for extensible plugins. Directory scanning OK for built-ins. |
| Plugin Pattern | Hook spec | ABC inheritance | Hook pattern is more flexible, allows optional methods. ABC forces implementation. |
| Async Runtime | uvloop | Default asyncio | uvloop is 2-4x faster. Already installed. No downside. |
| ID Generation | nanoid | uuid | nanoid: 21 chars URL-safe vs uuid: 36 chars with hyphens |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| PyGithub | Adds another dependency when httpx handles REST perfectly. Bearer token auth is 5 lines. | httpx directly |
| Python <3.10 with scrapling | scrapling 0.4.2 requires 3.10+ | Upgrade Python or use Playwright for JS rendering instead |
| Unauthenticated GitHub API in production | 60 req/hr limit is restrictive | Use personal access token for 5000 req/hr |
| tabulate for article list | Only handles tables, no detail view support | rich (handles both) |
| Multiple display libraries | Complexity of managing tabulate + html2text + custom formatting | rich (all-in-one) |
| zipimport | Overly complex for local plugins | File-based discovery or entry points |
| importlib.reload | Causes issues with already-imported modules | Structured plugin lifecycle management |
| Global plugin registry singleton | Hard to test, creates hidden state | Dependency injection via PluginManager |
| Plugin that mutates core state | Breaks isolation | Plugins only interact via hooks |
| stevedore | More complex, designed for OpenStack | pluggy (simpler, already installed) |
| yapsy | Older, less active maintenance | pluggy (pytest standard) |
| aiohttp | Redundant HTTP client alongside httpx | httpx.AsyncClient (handles both sync/async) |
| aiodns | Only for high-volume DNS resolution | uvloop handles DNS via libuv; not needed at RSS reader scale |
| uvloop[dev] | Dev extras not needed | Just `uvloop` package |
| anyio as direct dependency | httpx already depends on it transitively | It's already installed |
| uuid (built-in) | 36 chars with hyphens, not URL-safe | nanoid (21 chars, URL-safe) |

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| scrapling 0.4.2 | Python >=3.10 | Hard requirement. Bumps project minimum from ~3.6 to 3.10. |
| httpx 0.27.x | Python >=3.8 | Already in use. Compatible with scrapling. |
| feedparser 6.0.x | Python >=3.6 | Existing. Works with Python 3.10+. |
| rich 13.x | Python >=3.7 | Compatible with existing Python 3.10+ requirement. |
| html2text 2024.x | Python >=3.8 | If needed. |
| pluggy 1.5.0 | Python >=3.8 | Already installed. Standard for plugin systems. |
| **uvloop 0.22.1** | Python >=3.9, specifically 3.13.5 | Already installed. Full support for Python 3.13.5. |
| **httpx 0.28.1** | Python >=3.10 | Built-in AsyncClient. Already installed. |
| **anyio 4.7.0** | Python >=3.9 | httpx dependency. Already installed. |
| **nanoid 3.16.x** | Python >=3.7 | Must add to dependencies. URL-safe ID generation. |

---

## Sources

- [feedparser Documentation](https://feedparser.readthedocs.io/en/latest/) (HIGH confidence)
- [BeautifulSoup4 Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/) (HIGH confidence)
- [Playwright for Python](https://playwright.dev/python/docs/intro) (HIGH confidence)
- [httpx Documentation](https://www.python-httpx.org/) (HIGH confidence)
- [Python sqlite3 Documentation](https://docs.python.org/3/library/sqlite3.html) (HIGH confidence)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/en/20/) (HIGH confidence)
- [Click Documentation](https://click.palletsprojects.com/en/8.1.x/) (HIGH confidence)
- [Typer Documentation](https://typer.tiangolo.com/) (HIGH confidence)
- [argparse Documentation](https://docs.python.org/3/library/argparse.html) (HIGH confidence)
- [PyPI: scrapling](https://pypi.org/project/scrapling/) - Version 0.4.2, Python >=3.10 (HIGH confidence)
- [PyPI: PyGithub](https://pypi.org/project/PyGithub/) - Version 2.8.1, Python >=3.8 (HIGH confidence)
- [GitHub REST API: Releases](https://docs.github.com/en/rest/releases/releases) - Endpoint specs, auth headers (HIGH confidence)
- [GitHub REST API: Contents](https://docs.github.com/en/rest/repos/contents) - File content endpoint (HIGH confidence)
- [rich documentation](https://rich.readthedocs.io/) - Terminal formatting (MEDIUM confidence - training data)
- [html2text PyPI](https://pypi.org/project/html2text/) - HTML to markdown (MEDIUM confidence - training data)
- [pluggy GitHub](https://github.com/pytest-dev/pluggy) - Plugin framework (HIGH confidence - verified installed)
- [Python importlib.metadata docs](https://docs.python.org/3/library/importlib.metadata.html) - Entry points (HIGH confidence - built-in)
- [packaging.python.org plugin guide](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/) - Plugin discovery best practices (HIGH confidence)
- **PyPI JSON API (curl)** - uvloop 0.22.1, httpx 0.28.1, anyio 4.7.0 confirmed (HIGH confidence)
- **PyPI: nanoid** (https://pypi.org/project/nanoid/) - UNVERIFIED, network restricted. API from training data.
