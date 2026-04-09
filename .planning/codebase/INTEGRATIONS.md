# External Integrations

**Analysis Date:** 2026-03-31

## APIs & External Services

**GitHub API:**
- Used by: `src/providers/github_release_provider.py`, `src/utils/github.py`
- SDK: PyGithub 2.0.x
- Auth: `GITHUB_TOKEN` environment variable (optional, supports unauthenticated with rate limits)
- Endpoints: Repository releases, repository metadata
- Rate limiting: Handled via PyGithub exceptions (RateLimitExceededException)

**Web Scraping:**
- scrapling 0.4.x - Primary HTTP fetching library
- Fetcher - Fast synchronous HTTP client
- StealthyFetcher - Browser automation for anti-bot protection
- Fallback strategy: Basic Fetcher -> StealthyFetcher on 403/429/block page detection
- Caching: 5-min TTL per URL (TTLCache, 1000 entries)
- Rate limiting: Per-host sliding window (1 request/sec default)

## Data Storage

**SQLite (Primary):**
- Location: `~/.local/share/feedship/feedship.db` (via platformdirs)
- Client: sqlite3 (built-in Python module)
- Features: WAL journal mode, FTS5 full-text search, BM25 ranking
- Schema: `feeds` table, `articles` table, `articles_fts` FTS5 virtual table
- Async: Writes serialized via asyncio.Lock to prevent "database is locked" errors

**ChromaDB (Vector Store - Optional ml extra):**
- Location: `~/.local/share/feedship/chroma/` (via platformdirs)
- Client: chromadb PersistentClient
- Model: all-MiniLM-L6-v2 (384-dimensional embeddings)
- Collection: "articles" with cosine similarity
- Offline mode: HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1

## Authentication & Identity

**GitHub Token:**
- Env var: `GITHUB_TOKEN`
- Purpose: GitHub API authentication (higher rate limits)
- Location in code: `src/utils/github.py` line 19

**Feed Metadata:**
- Stored in SQLite `feeds.metadata` JSON field
- May contain per-provider data (e.g., github_token per feed)

## Monitoring & Observability

**Error Tracking:** None (no external error tracking service)

**Logs:**
- Python logging (logging.getLogger)
- Structured logging via Rich for CLI output
- Log levels: DEBUG, INFO, WARNING, ERROR

## CI/CD & Deployment

**GitHub Actions:**
- Workflows in `.github/workflows/`:
  - `lint.yml` - Code linting with ruff
  - `release.yml` - Package release

**Pre-commit Hooks:**
- Service: pre-commit.com / GitHub
- Hooks: trailing-whitespace, end-of-file-fixer, check-yaml, detect-private-key, ruff, ruff-format

## Environment Configuration

**Environment Variables:**
- `GITHUB_TOKEN` - GitHub API authentication (optional)
- `HF_HUB_OFFLINE=1` - Force offline mode for HuggingFace (set in code)
- `TRANSFORMERS_OFFLINE=1` - Force offline mode for transformers (set in code)
- `RADAR_*` - Dynaconf environment variable prefix (any RADAR_* var overrides config.yaml)

**Config File:**
- `config.yaml` - Application configuration
  - `timezone` - Application timezone (default: Asia/Shanghai)
  - `bm25_factor` - BM25 sigmoid normalization factor (default: 0.5)
  - `webpage_sites` - Site-specific CSS selectors for WebpageProvider

**Secrets Location:**
- No secret storage service used
- GitHub token via environment variable only

## File Storage

**Local File Storage:**
- SQLite database: `~/.local/share/feedship/feedship.db`
- ChromaDB vectors: `~/.local/share/feedship/chroma/`
- Platformdirs ensures cross-platform compatibility

## Node.js Scripts

**Feed Extraction:**
- `bin/extract.mjs` - Article extraction via Node.js
- `bin/extract_defuddle.mjs` - Defuddle extraction variant
- Used for advanced content extraction beyond trafilatura

## Caching Strategy

**URL Response Cache:**
- Type: TTLCache (cachetools)
- Size: 1000 URLs
- TTL: 300 seconds (5 minutes)
- Location: `src/utils/scraping_utils.py`

**Embedding Model Cache:**
- HuggingFace offline mode enabled
- Models cached locally after first download

---

*Integration audit: 2026-03-31*
