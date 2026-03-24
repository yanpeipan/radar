# Milestone v1.4 Summary

**个人资讯系统 (Personal Information System)**
v1.4 — Storage Layer Enforcement + GitHubReleaseProvider
*Completed: 2026-03-25*

---

## 1. Overview

v1.4 stabilizes the architecture built in v1.3 through two refactoring phases and one new feature. The milestone focuses on code quality (anti-屎山 refactoring), a dedicated GitHub release provider, and enforcing the storage layer as the sole database access boundary.

**Core value delivered:** A CLI tool that aggregates RSS feeds, websites, and GitHub repositories into a searchable local SQLite database — now with cleaner architecture and a dedicated provider for GitHub releases.

---

## 2. Architecture

```
src/
├── storage/           # ✅ NEW: Single database access boundary
│   ├── __init__.py   # Exports all storage functions
│   └── sqlite.py     # All SQL operations (get_db() internal only)
├── providers/         # Plugin-based content providers
│   ├── rss_provider.py
│   ├── github_provider.py
│   └── github_release_provider.py  # ✅ NEW: Priority 200
├── tags/             # Tag parsing plugins
│   ├── default_tag_parser.py
│   ├── release_tag_parser.py  # ✅ NEW: Semantic versioning
│   └── ai_tagging.py
├── application/      # Business logic (delegates to storage)
│   ├── feed.py
│   ├── articles.py
│   └── crawl.py
├── cli/              # ✅ REFACTORED: cli.py → src/cli/
│   ├── __init__.py
│   ├── article.py
│   ├── feed.py
│   ├── tag.py
│   └── context.py
└── utils/
    ├── rss.py
    └── github.py
```

**Key invariant:** `get_db()` is internal to `src/storage/sqlite.py` only. No module outside `storage/` calls `get_db()` directly.

---

## 3. Phases

### Phase 16: GitHubReleaseProvider *(1 plan, ~3 min)*
**Goal:** Dedicated provider using PyGithub `repo.get_latest_release()` with semantic versioning tag parser.

- `GitHubReleaseProvider` (priority=200) coexists with `GitHubProvider` (priority=100)
- `ReleaseTagParser` extracts `owner`, `version`, `release-type` tags
- Release type auto-detection: release → "release", prerelease → "pre-release", draft → "draft"

**Auto-fixed bug:** Release type logic was inverted — releases were tagged "pre-release" and prereleases "release". Fixed in the same commit.

### Phase 17: Anti-屎山 Refactoring *(2 plans, ~10 min)*
**Goal:** Split monolithic cli.py, adopt DB context manager, fix feed_meta().

- `cli.py` (798 lines) → `src/cli/` package with 5 modules
- DB context manager (`_get_connection` → `get_db()` with context manager protocol)
- `feed_meta()` now uses `httpx.get` with 5s timeout instead of `crawl()`

### Phase 18: Storage Layer Enforcement *(1 plan, ~7 min)*
**Goal:** Make `get_db()` internal to `src/storage/`.

- 16 new storage functions added covering embeddings, feeds, articles, crawl/CLI
- All consumer modules refactored: `ai_tagging.py`, `feed.py`, `articles.py`, `crawl.py`, `cli/article.py`
- Storage functions return domain objects (Feed, ArticleListItem) rather than raw rows

**Auto-fixed issue:** `get_all_embeddings()` and `get_articles_without_embeddings()` added to storage to eliminate remaining `get_db()` calls in `ai_tagging.py` — discovered during regression gate.

---

## 4. Decisions

| Decision | Rationale | Status |
|----------|-----------|--------|
| GitHubReleaseProvider priority=200 | Runs first for all GitHub URLs, separate concern from GitHubProvider | ✅ |
| ReleaseTagParser with semver | Structured tags enable filtering and future grouping | ✅ |
| cli.py → src/cli/ package | Maintainability, single responsibility, easier testing | ✅ |
| Storage functions return domain objects | Avoids leaking DB schema into business logic | ✅ |
| get_db() internal to storage only | Enforces single database access boundary | ✅ |
| Helper functions for ai_tagging | Success criteria required no get_db() in ai_tagging.py | ✅ |

---

## 5. Requirements

All requirements from prior milestones remain validated. v1.4 adds no new functional requirements.

**Continuing requirements from v1.0–v1.3:**
- RSS subscription and parsing
- Website URL crawling with Readability extraction
- GitHub repository monitoring via PyGithub
- SQLite storage with FTS5 full-text search
- Tag-based article organization
- Article list with ID and tags columns
- Article detail view and open-in-browser

---

## 6. Tech Debt

| Item | Severity | Notes |
|------|----------|-------|
| embedding/clustering removed from tags | Low | Can be re-added as provider if needed |
| `github_repos` table not yet dropped | Low | Data migrated to `feeds.metadata`; table persists harmlessly |

**No blockers.** Architecture is clean and extensible for v1.5.

---

## 7. Getting Started

```bash
# Add a feed
python -m src.cli feed add https://example.com/feed.xml

# List articles
python -m src.cli article list

# Search
python -m src.cli article search "query"

# Add GitHub repo
python -m src.cli feed add https://github.com/owner/repo

# Refresh all
python -m src.cli feed refresh --all

# Auto-tag articles
python -m src.cli tag auto
```

---

## Stats

| Metric | Value |
|--------|-------|
| Phases | 3 (16, 17, 18) |
| Plans | 4 (16-01, 17-01, 17-02, 18-01) |
| Commits | 43 |
| Files changed | 15 |
| Lines added | +2,599 |
| Lines removed | −24 |
| Duration | ~20 min total |

---

*Generated 2026-03-25*
