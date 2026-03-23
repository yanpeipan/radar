# Milestones

## v1.2 Article List Enhancements (Shipped: 2026-03-23)

**Phases completed:** 4 phases, 5 plans, 11 tasks

**Key accomplishments:**

- GitHub blob URL feeds now work via `feed add` - routes to changelog storage, `fetch --all` refreshes without error
- Unified store_article() function in db.py replacing 70+ lines of inline SQL in store_changelog_as_article()
- Rich table formatting with batch tag fetching - N+1 query problem fixed
- GitHub releases can now be tagged using article tag commands with auto-detection

---

## v1.0 MVP (Shipped: 2026-03-22)

**Phases completed:** 3 phases, 9 plans, 12 tasks

**Key accomplishments:**

- SQLite database with WAL mode, Feed/Article dataclasses, and project dependencies configured
- Feed CRUD operations with RSS/Atom parsing, bozo detection, and article deduplication via GUID/UNIQUE constraint
- Click-based CLI with feed management and article listing commands with ANSI colors and per-feed error isolation
- Article search subcommand added to CLI with FTS5-powered full-text search via search_articles() function
- crawl_url() function with Readability extraction, robots.txt lazy compliance, and 2-second per-host rate limiting
- `crawl` CLI command with --ignore-robots flag wrapping crawl_url() for web content extraction

---

## v1.1 GitHub Monitoring + Tagging (Shipped: 2026-03-23)

**Phases completed:** 4 phases, 10 plans

**Key accomplishments:**

- GitHub API client with Bearer token auth, rate limit handling
- Changelog detection and scraping via raw.githubusercontent.com
- Unified display and refresh integration for GitHub releases and feed articles
- Tag and article tagging infrastructure with SQLite many-to-many relationship, CLI commands, and tag filtering
- Keyword/regex rule matching and AI clustering for automatic article tagging
- `tag rule edit` command to modify existing tag rules

---

## v1.2 Article List Enhancements (Shipped: 2026-03-23)

**Phases completed:** 5 phases, 5 plans, 14 tasks

**Key accomplishments:**

- GitHub blob URL support in `feed add` - routes to changelog storage automatically
- Unified `store_article()` function replacing 70+ lines of inline SQL
- Rich table formatting for article list with ID and tags columns
- `article view` and `article open` commands for article details
- GitHub release tagging with auto-detection (release vs article IDs)
