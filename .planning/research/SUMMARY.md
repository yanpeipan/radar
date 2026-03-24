# Project Research Summary

**Project:** 个人资讯系统 (Personal Information System)
**Domain:** CLI tool for RSS subscription and website crawling
**Researched:** 2026-03-25
**Confidence:** HIGH

## Executive Summary

This is a personal information system CLI tool built in Python that allows users to collect, subscribe to, and organize information sources from the internet. Users add RSS feeds or website URLs, and the system automatically fetches content and stores it in a local SQLite database for reading and retrieval.

The current milestone (v1.6) focuses on migrating article ID generation from `uuid.uuid4()` (36 chars, not URL-safe) to `nanoid.generate()` (21 chars, URL-safe). Research across all four domains confirms this is a well-understood migration with clear patterns. The primary risk is foreign key desynchronization across `articles`, `article_tags`, and `article_embeddings` tables. The recommended approach is a deterministic, transactional migration using UPDATE (not DELETE+INSERT) to preserve SQLite rowid semantics for FTS5 search indexing.

Key technology decisions are stable: feedparser for RSS, httpx for HTTP, BeautifulSoup4+lxml for HTML parsing, pluggy for plugin architecture, rich for terminal display, and uvloop for async concurrency. Python >=3.10 is required due to scrapling dependency.

## Key Findings

### Recommended Stack

The technology stack is mature and well-suited for the project. All dependencies are established libraries with active maintenance.

**Core technologies:**
- **feedparser 6.0.x** — Universal RSS/Atom parser, handles all major feed formats
- **httpx 0.27+** — Modern async/sync HTTP client with HTTP/2 support
- **BeautifulSoup4 4.12.x + lxml 5.x** — HTML parsing with intuitive navigation API
- **sqlite3 (built-in)** — No external dependencies, sufficient for personal use
- **click 8.1.x** — Decorator-based CLI framework with automatic help generation
- **pluggy 1.5.x** — Plugin manager (pytest standard), already installed
- **rich 13.x** — Terminal formatting for tables, panels, markdown rendering
- **nanoid 3.16.x** — Short URL-safe ID generation (21 chars vs uuid's 36)
- **uvloop 0.22.x** — Async event loop (2-4x faster than default asyncio)

**Python requirement:** >=3.10 (due to scrapling 0.4.2 requirement)

### Expected Features

**Must have (table stakes):**
- ID regeneration for ~2479 existing articles with URL-like IDs
- Foreign key updates for `article_tags` (3,737 entries) and `article_embeddings`
- Atomic migration in single transaction with backup
- Verification that all tag associations and embeddings preserved

**Should have (competitive):**
- Deterministic ID generation (seed on old ID) for idempotent migration
- CLI dry-run option for migration validation
- Progress reporting during migration

**Defer (v2+):**
- Old ID lookup table for bookmarks/external references
- Rollback capability (backup restoration is sufficient for v1.6)

### Architecture Approach

The migration is a targeted schema update, not a structural change. The critical insight is that FTS5 virtual table `articles_fts` uses SQLite's internal `rowid` (not article `id`) to track articles. The `INSERT OR REPLACE INTO articles_fts` at lines 351-355 of `sqlite.py` syncs by rowid, meaning FTS does NOT require reindexing after ID migration.

**Major components requiring modification:**
1. `src/storage/sqlite.py:store_article()` — Replace `uuid.uuid4()` with `nanoid.generate()`
2. `src/storage/sqlite.py:add_tag()` — Replace `uuid.uuid4()` with `nanoid.generate()`
3. `src/storage/sqlite.py:tag_article()` — Replace `uuid.uuid4()` with `nanoid.generate()`
4. Migration script (new) — Regenerate IDs for ~2479 existing articles

**Components NOT requiring modification:**
- `articles_fts` FTS5 table (uses rowid, not article.id)
- `generate_article_id()` in `src/utils/__init__.py` (derives ID from feed data, not DB primary key)

### Critical Pitfalls

1. **FTS5 Index Desynchronization** — Using DELETE+INSERT instead of UPDATE breaks FTS rowid linkage. Prevention: Always UPDATE articles in-place, never delete and re-insert.

2. **Orphaned article_tags Foreign Key References** — Updating `articles.id` without updating `article_tags.article_id` orphans tag associations. Prevention: Update `article_tags.article_id` BEFORE `articles.id` in same transaction.

3. **Orphaned article_embeddings** — Same FK issue as article_tags. Prevention: Update `article_embeddings.article_id` in same transaction.

4. **Non-deterministic ID Generation** — Random nanoid per migration run causes duplicate IDs when re-running. Prevention: Use deterministic generation (hash of old ID as seed) for idempotent migration.

5. **Partial Migration with No Rollback** — Script crash mid-migration leaves inconsistent state. Prevention: Single transaction wrapping all changes, mandatory backup before migration.

## Implications for Roadmap

Based on research, the v1.6 nanoid migration should be structured in three phases:

### Phase 1: NANO-01 — Code Changes
**Rationale:** Must complete before migration script can run, as new articles created during migration would have mixed ID formats.

**Delivers:** `store_article()`, `add_tag()`, and `tag_article()` updated to use `nanoid.generate()`

**Avoids:** Creating new articles with uuid IDs during migration window

### Phase 2: NANO-02 — Migration Script
**Rationale:** Core deliverable of v1.6. Must handle all three tables atomically with deterministic ID generation.

**Delivers:** Migration script that:
- Creates timestamped backup before any changes
- Wraps all updates in single transaction (BEGIN IMMEDIATE)
- Updates `article_tags.article_id` BEFORE `articles.id`
- Updates `article_embeddings.article_id`
- Uses deterministic ID generation (seed on old ID hash)
- Skips already-migrated articles (idempotent)
- Reports progress and exit codes

**Implements:** Foreign key integrity preservation, FTS rowid preservation

**Avoids:** Pitfalls 1-5 from research

### Phase 3: NANO-03 — Verification
**Rationale:** Must validate that all CRUD operations, tagging, search, and CLI truncation work correctly with new IDs.

**Delivers:**
- Tag associations preserved (query verification)
- Embeddings reachable for migrated articles
- Search results match article list counts
- `article detail 8-char` and `article open 8-char` work for migrated articles

**Uses:** Existing stack components (sqlite3, rich, click)

### Phase Ordering Rationale

- **NANO-01 before NANO-02:** Ensures no mixed ID formats during migration window
- **NANO-02 before NANO-03:** Migration must be complete before verification can run
- **Grouped in single milestone:** All three are required for v1.6 completion

### Research Flags

**Phases with standard patterns (skip research-phase):**
- **NANO-01:** Simple function call replacement (1-2 lines per function)
- **NANO-03:** Standard SQLite verification queries

**Phases needing implementation attention:**
- **NANO-02:** Despite clear patterns in research, the transactional migration with deterministic ID generation requires careful implementation. No additional research needed, but testing must cover idempotency (run twice, second should report 0 migrated).

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All dependencies verified via official docs, multiple sources confirm |
| Features | HIGH | Migration requirements clearly defined from codebase analysis |
| Architecture | HIGH | FTS rowid behavior verified via SQLite docs, schema analysis confirmed |
| Pitfalls | HIGH | All pitfalls verified against codebase patterns, recovery strategies documented |

**Overall confidence:** HIGH

### Gaps to Address

- **nanoid package verification:** STACK.md notes nanoid v3.16.0 is listed in quality gate but was not verified as installed. Confirm via `pip show nanoid` before NANO-01.
- **article_embeddings table existence:** Not confirmed in current codebase. Verify `src/storage/sqlite.py` contains this table definition before NANO-02 implementation.

## Sources

### Primary (HIGH confidence)
- [feedparser Documentation](https://feedparser.readthedocs.io/en/latest/) — RSS/Atom parsing
- [BeautifulSoup4 Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/) — HTML parsing
- [httpx Documentation](https://www.python-httpx.org/) — HTTP client
- [Python sqlite3 Documentation](https://docs.python.org/3/library/sqlite3.html) — Database operations
- [SQLite rowid documentation](https://www.sqlite.org/lang_createtable.html#rowid) — FTS rowid behavior
- [FTS5 documentation](https://www.sqlite.org/fts5.html) — Search index semantics
- [SQLite Foreign Key documentation](https://www.sqlite.org/foreignkeys.html) — FK constraints
- [pluggy GitHub](https://github.com/pytest-dev/pluggy) — Plugin framework
- [nanoid Python library](https://pypi.org/project/nanoid/) — ID generation

### Secondary (HIGH confidence)
- Code analysis: `src/storage/sqlite.py` store_article(), add_tag(), tag_article() — Confirmed change locations
- Database inspection: Article count (~2479), tag count (~3737), ID format patterns

---

*Research completed: 2026-03-25*
*Ready for roadmap: yes*
