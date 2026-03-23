# Project Research Summary

**Project:** Personal Information System (个人资讯系统)
**Domain:** CLI tool for RSS subscription and website crawling
**Researched:** 2026-03-23
**Confidence:** HIGH

## Executive Summary

This is a Python CLI tool for collecting, organizing, and reading information from RSS feeds and websites. The system stores content locally in SQLite for offline reading and retrieval. The existing codebase has been through v1.0 and v1.1, with v1.2 (article list enhancements and detail view) currently in research phase.

The recommended tech stack is mature and well-documented: feedparser for RSS parsing, httpx + BeautifulSoup4 + lxml for HTML scraping, Playwright/scrapling for JavaScript-rendered pages, sqlite3 for database, click for CLI framework, and rich for terminal formatting. Python >=3.10 is required due to scrapling dependency.

Key risks identified through research: (1) N+1 query performance problem in tag display that must be fixed with JOIN or batch queries, (2) missing content field in article detail SELECT clause, (3) GitHub releases cannot be tagged due to schema limitation. These must be addressed during implementation to ship a complete feature.

## Key Findings

### Recommended Stack

**Summary from STACK.md**

All core technologies are well-established with HIGH confidence official documentation. The v1.2 addition introduces rich (13.x) for terminal display enhancement - handling both table formatting in list view AND panel/markdown rendering in detail view. html2text is conditional - only needed if `article.content` stores raw HTML.

**Core technologies:**
- **feedparser 6.0.x**: Universal RSS/Atom parser with bozo detection for malformed feeds
- **httpx 0.27.x**: HTTP client for fetching pages and GitHub API calls with async support
- **BeautifulSoup4 4.12.x + lxml 5.x**: HTML parsing with fast C-based backend
- **scrapling 0.4.2**: Adaptive web scraping with JS support (requires Python >=3.10)
- **sqlite3** (built-in): Local database, no external dependencies
- **click 8.1.x**: CLI framework with decorator-based commands
- **rich 13.x**: Terminal formatting for tables, panels, markdown (v1.2 addition)

### Expected Features

**Summary from FEATURES.md**

**Must have (table stakes):**
- **Article ID column** - Show truncated ID (8 chars) to enable reference for tagging operations
- **Tags column** - Separate column for tags (currently inline with title, hard to scan)
- **Detail view command** - `article view <id>` showing full article without opening browser

**Should have (competitive):**
- **Open in browser** - `article open <id>` to open article link in default browser
- **Full content in detail** - Show stored `content` field (not just `description`)

**Defer (v2+):**
- JSON output option for scripting (`article list --format json`)
- Export article to file (markdown, HTML)
- Share article (copy link to clipboard)

### Architecture Approach

**Summary from ARCHITECTURE.md**

The system follows a clear layered architecture: CLI commands (click) -> Business logic (articles.py) -> Data layer (db.py with sqlite3). Existing components already have most building blocks - `get_article()` and `get_article_tags()` exist but need enhancement. Minimal changes required: modify `article list` output formatting, add `get_article_detail()` function that includes content field, and resolve GitHub release tagging schema.

**Major components:**
1. **cli.py** (existing, MODIFY): Click commands, output formatting - add detail command, modify list display
2. **articles.py** (existing, MODIFY): Article queries - add `get_article_detail()` function
3. **db.py** (existing, NO CHANGE): Connection, schema, tag CRUD - `get_article_tags()` already exists
4. **models.py** (existing, EXTEND): Dataclass definitions - add `ArticleDetail` if needed

### Critical Pitfalls

**Top 5 from PITFALLS.md:**

1. **N+1 Query Problem** - Current code calls `get_article_tags()` per article in loop. For 20 articles = 21 queries. Fix with JOIN or batch query. Must address in Phase implementing article list with tags.

2. **Missing Content Field** - `get_article()` SELECT omits `content` column even though it exists in DB. Detail view will show empty content. Add to SELECT clause when implementing detail view.

3. **GitHub Releases Cannot Be Tagged** - `article_tags` table FK points to `articles.id`, but GitHub releases are in separate `github_releases` table. Schema change or error handling needed before v1.2 release.

4. **ID Column Width** - Truncated IDs (8 chars) shown in list don't work for commands like `article tag <id>`. Need `--verbose` flag for full ID display.

5. **Tags Column Truncation** - Inline tags in title push title column to <20 chars when article has 3+ tags. Move tags to separate column or limit display with `+N` indicator.

## Implications for Roadmap

Based on research, the article list enhancements and detail view should be split into 4 phases that address dependencies and avoid known pitfalls.

### Phase 1: List Display + N+1 Fix
**Rationale:** Article list is the entry point. Must show IDs and tags properly but current implementation has N+1 performance issue. This phase fixes the foundation.

**Delivers:**
- `article list` with ID column (8 chars truncated) and separate tags column
- N+1 query fix via JOIN or batch query in `list_articles_with_tags()`
- `--verbose` flag showing full IDs for command usage

**Addresses:** Pitfall 1 (N+1), Pitfall 4 (ID truncation), Pitfall 5 (Tags truncation)
**Uses:** rich for table formatting
**Avoids:** Performance degradation as article count grows

### Phase 2: Detail View Command
**Rationale:** Depends on Phase 1 (users need IDs shown in list to reference articles). Must include content field fetch.

**Delivers:**
- `article view <id>` command showing title, source, date, tags, link, description/content
- `get_article_detail()` function that includes `content` in SELECT
- Full content display (not just description)

**Addresses:** Pitfall 2 (missing content field)
**Uses:** rich for Panel/Markdown rendering

### Phase 3: GitHub Release Tagging (Schema Decision)
**Rationale:** Independent of list/detail views. Requires schema decision (Option A: new table, Option B: error handling, Option C: unify storage).

**Delivers:**
- Tags work for GitHub releases OR clear error message
- Potential `github_release_tags` table migration if Option A

**Addresses:** Pitfall 3 (GitHub release tagging)
**Research flag:** May need `/gsd:research-phase` for migration strategy

### Phase 4: Open in Browser + Polish
**Rationale:** Independent enhancement. Add after core is stable.

**Delivers:**
- `article open <id>` command using `open` (macOS) / `xdg-open` (Linux)
- Markdown rendering in detail view (optional)

**Addresses:** Feature - open in browser, markdown rendering

### Phase Ordering Rationale

- **Phase 1 before 2:** Detail view needs IDs shown in list to be usable
- **Phase 3 independent but flagged:** GitHub tagging is separate concern but must ship with solution (error or feature)
- **Phase 4 last:** Polish features that don't block core functionality
- **N+1 fix in Phase 1:** Performance issues cascade - fix early
- **Each phase maps to specific pitfalls:** Prevention strategies are implemented in the phase where pitfall would occur

### Research Flags

Phases with standard patterns (skip research-phase):
- **Phase 1, 2:** Well-documented CLI conventions, existing codebase references
- **Phase 4:** CLI patterns established in existing `feed list`, `repo list`

Phases likely needing deeper research during planning:
- **Phase 3:** GitHub release tagging schema decision. May need research for migration path if Option A chosen (adding `github_release_tags` table with backfill).

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All technologies have official documentation, established in v1.0/v1.1 |
| Features | HIGH | Based on existing codebase patterns and CLI conventions |
| Architecture | HIGH | Clear layered design, existing components well-understood |
| Pitfalls | HIGH | All identified via code inspection and known SQLite patterns |

**Overall confidence:** HIGH

### Gaps to Address

- **GitHub release tagging schema:** Not decided yet. Options presented but implementation path needs planning decision. Flag for Phase 3.
- **html2text dependency:** May be needed if `article.content` stores HTML. Check stored content format before adding dependency.
- **scrapling vs Playwright for changelog:** scrapling is chosen but Playwright fallback exists if scrapling causes issues. Monitor during implementation.

## Sources

### Primary (HIGH confidence)
- [feedparser Documentation](https://feedparser.readthedocs.io/en/latest/) - RSS/Atom parsing
- [BeautifulSoup4 Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/) - HTML parsing
- [Playwright for Python](https://playwright.dev/python/docs/intro) - Browser automation
- [httpx Documentation](https://www.python-httpx.org/) - HTTP client
- [Python sqlite3 Documentation](https://docs.python.org/3/library/sqlite3.html) - Database
- [Click Documentation](https://click.palletsprojects.com/en/8.1.x/) - CLI framework
- [scrapling PyPI](https://pypi.org/project/scrapling/) - Changelog scraping (Python >=3.10)
- [GitHub REST API: Releases](https://docs.github.com/en/rest/releases/releases) - API specs, auth headers
- [SQLite Query Planner](https://www.sqlite.org/queryplanner.html) - N+1 prevention
- [rich documentation](https://rich.readthedocs.io/) - Terminal formatting

### Codebase References
- `src/cli.py` - Existing CLI patterns (feed list, repo list)
- `src/articles.py` - Article queries, `get_article()` function
- `src/db.py` - `get_article_tags()` function, schema

---
*Research completed: 2026-03-23*
*Ready for roadmap: yes*
