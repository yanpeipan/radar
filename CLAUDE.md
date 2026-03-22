<!-- GSD:project-start source:PROJECT.md -->
## Project

**个人资讯系统**

一个个人资讯系统，帮助用户收集、订阅和组织来自互联网的信息来源。用户添加 RSS 订阅源或网站 URL，系统自动抓取内容并存储到本地 SQLite 数据库中，便于后续阅读和检索。

**Core Value:** 用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。

### Constraints

- **Tech**: Python (CLI 工具)
- **Storage**: SQLite（单一数据库文件）
- **No API**: 纯本地应用，无后端服务
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### RSS Parsing
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **feedparser** | 6.0.x | Universal feed parser | Handles RSS 0.9x, RSS 1.0, RSS 2.0, CDF, Atom 0.3, Atom 1.0. The de-facto standard for feed parsing in Python. Active maintenance, Python >=3.6 support. |
### HTML Scraping
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **httpx** | 0.27.x | HTTP client | Modern async/sync HTTP client with requests-compatible API. HTTP/2 support. Use for fetching HTML pages. |
| **BeautifulSoup4** | 4.12.x | HTML parsing | Intuitive navigation of parsed HTML. Works with multiple parsers (html.parser built-in, lxml, html5lib). |
| **lxml** | 5.x | Fast parser | C-based HTML/XML parser. Recommended backend for BeautifulSoup (faster than html.parser). |
| **Playwright** | 1.49.x | Browser automation | For JavaScript-rendered pages. Supports Chromium, WebKit, Firefox. Headless or headed. Use as fallback for SPA sites. |
### SQLite Database
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **sqlite3** | (built-in) | Database | No external dependencies. DB-API 2.0 compliant. Sufficient for personal information system with moderate data volumes. |
| **SQLAlchemy** | 2.0.x | ORM (optional) | Only if you need complex relationships, migrations, or prefer ORM-style code. Adds dependency overhead. |
# Create table
# Insert with parameterized query (prevents SQL injection)
# Query
### CLI Framework
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **click** | 8.1.x | CLI framework | Decorator-based, composable, automatic help generation. Most popular modern CLI framework for Python. |
| **argparse** | (built-in) | CLI framework | Standard library. More verbose than click. Use only if avoiding dependencies is critical. |
## Project Structure Best Practices
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
- [PyPI feedparser](https://pypi.org/project/feedparser/) (HIGH confidence)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
