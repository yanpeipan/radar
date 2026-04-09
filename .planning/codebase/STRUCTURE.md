# Codebase Structure

**Analysis Date:** 2026-03-31

## Directory Layout

```
/Users/y3/feedship/
├── src/                      # Main source code
│   ├── __init__.py          # Package marker
│   ├── models.py            # Core domain dataclasses (Feed, Article)
│   ├── constants.py         # Constants (BROWSER_HEADERS, etc.)
│   ├── application/         # Business logic layer
│   ├── cli/                 # CLI commands (Click-based)
│   ├── discovery/           # Feed auto-discovery
│   ├── providers/           # Content provider plugins
│   ├── storage/             # SQLite + ChromaDB storage
│   └── utils/              # Utility functions
├── tests/                   # Test suite
│   ├── conftest.py         # Pytest fixtures
│   ├── test_cli.py         # CLI tests
│   ├── test_config.py      # Config tests
│   ├── test_fetch.py       # Fetch logic tests
│   ├── test_providers.py   # Provider tests
│   └── test_storage.py     # Storage tests
├── docs/                    # Project documentation
├── bin/                     # Executable scripts
├── data/                    # Data directory (SQLite DB, ChromaDB)
├── config.yaml             # Configuration file
├── pyproject.toml          # Project metadata and dependencies
├── README.md               # Project overview
└── CLAUDE.md               # Claude agent instructions
```

## Directory Purposes

**`src/application/`:**
- Purpose: Business logic orchestration
- Contains: `articles.py`, `feed.py`, `fetch.py`, `search.py`, `combine.py`, `rerank.py`, `related.py`, `config.py`
- Key files: `src/application/feed.py` (feed CRUD), `src/application/fetch.py` (async fetch orchestration)

**`src/cli/`:**
- Purpose: Click-based CLI commands
- Contains: `__init__.py` (cli group), `__main__.py` (entry point), `feed.py`, `article.py`, `discover.py`, `ui.py`
- Key files: `src/cli/__init__.py` (root command), `src/cli/feed.py` (feed management, fetch command)

**`src/discovery/`:**
- Purpose: Feed auto-discovery from website URLs
- Contains: `__init__.py`, `models.py`, `parser.py`, `common_paths.py`, `deep_crawl.py`, `parallel_probe.py`
- Key files: `src/discovery/__init__.py` (public API), `src/discovery/parser.py` (HTML link parsing)

**`src/providers/`:**
- Purpose: Plugin architecture for content sources
- Contains: `__init__.py` (provider registry), `base.py` (protocol), `rss_provider.py`, `github_release_provider.py`, `webpage_provider.py`
- Key files: `src/providers/__init__.py` (PROVIDERS list, load_providers(), discover())

**`src/storage/`:**
- Purpose: Persistent storage (SQLite + ChromaDB)
- Contains: `__init__.py`, `vector.py`, `sqlite/__init__.py`, `sqlite/impl.py`, `sqlite/init.py`
- Key files: `src/storage/sqlite/impl.py` (all database operations), `src/storage/vector.py` (ChromaDB)

**`src/utils/`:**
- Purpose: Shared utility functions
- Contains: `__init__.py`, `asyncio_utils.py`, `scraping_utils.py`, `github.py`
- Key files: `src/utils/__init__.py` (generate_feed_id, generate_article_id)

## Key File Locations

**Entry Points:**
- `src/cli/__main__.py`: Entry point for `python -m src.cli`
- `src/cli/__init__.py`: Root `cli()` command group

**Configuration:**
- `config.yaml`: Dynaconf settings (timezone, BM25 factor, defaults)
- `src/application/config.py`: Config access functions

**Core Logic:**
- `src/application/feed.py`: Feed CRUD operations (add_feed, register_feed, fetch_one)
- `src/application/fetch.py`: Async fetch orchestration (fetch_all_async, fetch_one_async)
- `src/providers/__init__.py`: Provider registry and discovery

**Storage:**
- `src/storage/sqlite/impl.py`: SQLite operations (store_article, upsert_feed, list_articles, search_articles_fts)
- `src/storage/vector.py`: ChromaDB operations (add_article_embeddings, search_articles_semantic)

**Models:**
- `src/models.py`: Feed, Article, FeedType, FeedMetaData dataclasses
- `src/discovery/models.py`: DiscoveredFeed, DiscoveredResult, LinkSelector

## Naming Conventions

**Files:**
- Python modules: `lowercase_with_underscores.py`
- Test files: `test_<module_name>.py`
- Provider modules: `<name>_provider.py` (e.g., `rss_provider.py`)

**Functions:**
- Modules: `lowercase_with_underscores`
- Classes: `PascalCase`
- Methods: `snake_case`
- CLI commands: `snake_case` (Click decorators)

**Variables:**
- snake_case for locals
- UPPER_SNAKE_CASE for constants

**Types:**
- Dataclasses: `PascalCase` (Feed, Article)
- Enums: `PascalCase` with UPPER values (FeedType.RSS)

## Where to Add New Code

**New Feature (business logic):**
- Primary code: `src/application/<feature>.py`
- Tests: `tests/test_<feature>.py`

**New CLI Command:**
- Implementation: `src/cli/<command>.py`
- Registration: Import in `src/cli/__init__.py`
- Tests: `tests/test_cli.py`

**New Content Provider:**
- Implementation: `src/providers/<name>_provider.py`
- Protocol: Implement `ContentProvider` from `src/providers/base.py`
- Self-registration: Add to end of file `PROVIDERS.append(<ProviderClass>())`
- Tests: `tests/test_providers.py`

**New Storage Operation:**
- SQLite: Add to `src/storage/sqlite/impl.py`
- Vector: Add to `src/storage/vector.py`
- Export from: `src/storage/__init__.py`

**Utilities:**
- Shared helpers: `src/utils/<purpose>.py`
- ID generation: `src/utils/__init__.py`

## Special Directories

**`.planning/`:**
- Purpose: GSD workflow planning artifacts
- Generated: Yes
- Committed: Yes

**`data/`:**
- Purpose: Runtime data (SQLite DB, ChromaDB storage)
- Generated: Yes
- Committed: No (.gitignore)

**`docs/`:**
- Purpose: Project documentation
- Generated: No
- Committed: Yes

---

*Structure analysis: 2026-03-31*
