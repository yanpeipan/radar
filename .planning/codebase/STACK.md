# Technology Stack

**Analysis Date:** 2026-03-31

## Languages

**Primary:**
- Python 3.10+ - All application code, CLI, storage, providers

**Secondary:**
- JavaScript/TypeScript - Node.js scripts in `bin/` directory for feed extraction

## Runtime

**Environment:**
- Python >=3.10 (required)

**Package Manager:**
- pip (via pyproject.toml)
- Lockfile: Not committed (pip freeze not used)

## Frameworks

**Core:**
- Click 8.1.x - CLI framework with command groups
- Rich 13.x - Terminal output formatting and tables

**Data Processing:**
- feedparser 6.0.x - RSS/Atom/CDF feed parsing
- trafilatura 1.0.x+ - Web content extraction (article text mining)
- BeautifulSoup4 4.12.x - HTML parsing (legacy, being replaced by scrapling)
- lxml 6.0.x - XML/HTML processing

**HTTP & Scraping:**
- scrapling 0.4.x - CSS-selector HTML parsing, HTTP fetching, browser automation
- msgspec 0.20.x - Fast serialization (required by scrapling browser engine)

**Storage:**
- sqlite3 (built-in) - Primary database for articles and feeds
- chromadb 0.4.x+ - Vector store for semantic search (optional ml extra)
- scikit-learn 1.7.x - BM25 scoring and normalization

**ML/AI (optional ml extra):**
- sentence-transformers 3.0.x - Text embeddings (all-MiniLM-L6-v2, 384-dim)
- transformers 4.40.x - HuggingFace models (BAAI/bge-reranker-base)
- torch 2.0.x - PyTorch (optional, Python < 3.13)
- safetensors 0.4.x - Safe model loading

**Cloudflare/Browser (optional cloudflare extra):**
- playwright 1.49.x - Browser automation (JS-rendered pages)
- curl-cffi 0.14.x - HTTP client with TLS impersonation
- socksio 1.0.x - SOCKS proxy support
- browserforge 1.2.x - Browser fingerprint management

**Configuration:**
- dynaconf 3.2.x - Configuration management (YAML)
- PyYAML 6.0.x - YAML parsing

**Utilities:**
- platformdirs 4.9.x - Cross-platform user data directories
- nanoid 2.0.x - URL-safe unique ID generation
- cachetools 5.3.x - TTL caches for rate limiting
- robotexclusionrulesparser 1.7.x - robots.txt parsing
- uvloop 0.22.x - High-performance async event loop
- PyGithub 2.0.x - GitHub API client

## Testing

**Framework:**
- pytest 9.0.x - Test runner with asyncio support
- pytest-asyncio 1.0.x - Async test support
- pytest-cov 7.0.x - Coverage reporting
- pytest-mock 3.15.x - Mocking
- pytest-httpx 0.36.x - HTTP mocking
- pytest-xdist 3.8.x - Parallel test execution
- pytest-click 1.1.x - Click CLI testing

**Code Quality:**
- ruff 0.6.x - Linting (E, W, F, I, UP, B, C4, SIM) and formatting
- pre-commit 3.0.x - Pre-commit hooks

## Configuration Files

**Project Config:**
- `pyproject.toml` - Dependencies, pytest config, ruff settings
- `config.yaml` - Application settings (timezone, BM25 factor, site configs)
- `.pre-commit-config.yaml` - Pre-commit hooks (trailing-whitespace, end-of-file-fixer, ruff)

**Entry Points:**
- `src.cli:cli` - Main CLI command group

## Architecture Notes

**Async:** uvloop for event loop, asyncio for concurrency
**HTML Parsing:** scrapling (CSS selectors) replaces BeautifulSoup + lxml for provider/discovery
**HTTP Client:** scrapling.Fetcher (sync) wrapped with asyncio.to_thread, or AsyncFetcher (native async)
**Semantic Search:** ChromaDB + sentence-transformers (all-MiniLM-L6-v2)
**Config:** dynaconf reads from config.yaml (env prefix: RADAR)

---

*Stack analysis: 2026-03-31*
