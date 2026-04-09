# Architecture

**Analysis Date:** 2026-03-31

## Pattern Overview

**Overall:** Layered architecture with plugin-based content providers

**Key Characteristics:**
- **CLI layer**: Click-based command interface with subcommands
- **Application layer**: Business logic orchestrating feed/Article operations
- **Provider layer**: Plugin architecture for extensible content sources
- **Storage layer**: SQLite (relational) + ChromaDB (vector) storage
- **Discovery layer**: Feed auto-discovery from website URLs

## Layers

**CLI Layer (`src/cli/`):**
- Purpose: User-facing command interface
- Location: `src/cli/`
- Contains: Click command groups and subcommands (feed, article, discover)
- Depends on: Application layer
- Entry point: `src/cli/__main__.py` → `src/cli/__init__.py:cli()`

**Application Layer (`src/application/`):**
- Purpose: Business logic orchestration for feeds and articles
- Location: `src/application/`
- Contains: `articles.py`, `feed.py`, `fetch.py`, `search.py`, `config.py`
- Depends on: Providers, Storage
- Used by: CLI layer

**Provider Layer (`src/providers/`):**
- Purpose: Plugin architecture for fetching content from different source types
- Location: `src/providers/`
- Contains: `base.py` (protocol), `rss_provider.py`, `github_release_provider.py`, `webpage_provider.py`
- Depends on: Discovery models, HTTP fetching utilities
- Used by: Application layer, CLI discovery
- Pattern: `ContentProvider` protocol with `match()`, `fetch_articles()`, `parse_feed()`, `discover()` methods

**Storage Layer (`src/storage/`):**
- Purpose: Persistent data storage (SQLite relational + ChromaDB vector)
- Location: `src/storage/`, `src/storage/sqlite/`, `src/storage/vector.py`
- Contains: SQLite implementation, database initialization, ChromaDB vector storage
- Depends on: Models (Feed, Article)
- Used by: Application layer

**Discovery Layer (`src/discovery/`):**
- Purpose: Feed auto-discovery from website URLs
- Location: `src/discovery/`
- Contains: `parser.py`, `models.py`, `common_paths.py`, `deep_crawl.py`, `parallel_probe.py`
- Depends on: Providers, HTTP utilities
- Used by: CLI (feed add command)

**Models (`src/models.py`):**
- Purpose: Core data structures
- Contains: `Feed`, `Article`, `FeedType`, `FeedMetaData` dataclasses

## Data Flow

**Adding a feed (CLI → Discovery → Provider → Storage):**
1. User runs `feedship feed add <url>`
2. CLI calls `discovery.discover_feeds(url)` to find feeds
3. Discovery probes URL via providers (RSS, GitHub, Webpage)
4. User selects feeds to add
5. Application `register_feed()` saves to SQLite via `upsert_feed()`
6. Articles fetched later via `fetch` command

**Fetching articles (Application → Provider → Storage):**
1. User runs `feedship fetch --all` or `feedship fetch <feed_id>`
2. Application `fetch_all_async()` or `fetch_one_async()` called
3. Provider `match_first()` finds appropriate provider for feed URL
4. Provider `fetch_articles()` fetches and parses content
5. Articles stored in SQLite via `upsert_articles_async()`
6. Embeddings added to ChromaDB via `add_article_embeddings()`

**Searching articles:**
1. User runs `feedship article list` or `feedship article search <query>`
2. FTS5 search via `search_articles_fts()` or semantic search via `search_articles_semantic()`
3. Results formatted for CLI display

## Key Abstractions

**ContentProvider Protocol (`src/providers/base.py`):**
- Purpose: Plugin interface for content sources
- Methods: `match()`, `priority()`, `fetch_articles()`, `parse_feed()`, `discover()`
- Invariant: `match(url, response=None)` must work without HTTP requests when response=None

**DiscoveredFeed (`src/discovery/models.py`):**
- Purpose: Represents a discovered RSS/Atom/RDF feed from a website URL
- Fields: url, title, feed_type, source, page_url, valid, metadata

**FetchedResult (`src/providers/base.py`):**
- Purpose: Result wrapper from provider fetch operations
- Fields: articles list, etag, modified_at (for conditional fetching)

**Feed/Article (`src/models.py`):**
- Purpose: Core domain entities stored in SQLite

## Entry Points

**CLI Entry (`src/cli/__main__.py`):**
- Location: `src/cli/__main__.py`
- Triggers: `python -m src.cli` or `feedship` command
- Responsibilities: Initializes uvloop, database, loads subcommands

**CLI Root Group (`src/cli/__init__.py`):**
- Location: `src/cli/__init__.py:cli()`
- Subcommands: `feed`, `discover`, `article` (lazy-loaded)

**Fetch Command (`src/cli/feed.py`):**
- Location: `src/cli/feed.py:fetch()`
- Triggers: `feedship fetch --all` or `feedship fetch <id>...`
- Responsibilities: Async feed fetching with concurrency control

**Feed Add Command (`src/cli/feed.py`):**
- Location: `src/cli/feed.py:feed_add()`
- Triggers: `feedship feed add <url>`
- Responsibilities: Feed discovery, selection, registration

## Error Handling

**Strategy:** Exception propagation with graceful degradation

**Patterns:**
- Provider failures: Caught and logged, next provider tried
- Database errors: Propagate as exceptions, CLI exits with error code
- Network errors: Logged at ERROR level, result includes error message
- Embedding failures: Non-critical, logged but don't fail the fetch

## Cross-Cutting Concerns

**Logging:** Standard `logging.getLogger(__name__)` module loggers

**Validation:** URL validation via `discovery.normalize_url()`, feed validation via providers

**Authentication:** GitHub token via metadata JSON in Feed record

**Concurrency:** asyncio.Semaphore for HTTP concurrency, asyncio.Lock + to_thread for SQLite writes

---

*Architecture analysis: 2026-03-31*
