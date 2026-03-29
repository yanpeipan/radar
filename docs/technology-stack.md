# Technology Stack

## Core Dependencies

| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| **feedparser** | 6.0.x | Universal feed parser (RSS 0.9x-2.0, Atom, CDF) | Active |
| **scrapling** | 0.4.x | CSS-selector HTML parsing, HTTP fetching, browser automation | Active |
| **click** | 8.1.x | CLI framework | Active |
| **rich** | 13.x | Terminal output formatting | Active |
| **PyGithub** | 2.0.x | GitHub API client | Active |
| **dynaconf** | 3.2.x | Configuration management (YAML) | Active |
| **trafilatura** | 1.0.x+ | Web content extraction | Active |
| **robotexclusionrulesparser** | 1.7.x | robots.txt parsing | Active |
| **platformdirs** | 4.9.x | Platform directories | Active |
| **uvloop** | 0.22.x | High-performance async event loop | Active |
| **nanoid** | 2.0.x | URL-safe unique ID generation | Active |
| **msgspec** | 0.20.x | Fast serialization (required by scrapling) | Active |

## Data Storage & ML

| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| **sqlite3** | (built-in) | Primary database (articles, feeds, metadata) | Active |
| **chromadb** | 0.4.x+ | Vector store for semantic search (embeddings) | Active |
| **sentence-transformers** | 3.0.x | Text embeddings (all-MiniLM-L6-v2, 384-dim) | Optional (ml) |
| **scikit-learn** | 1.7.x | BM25 scoring, normalization | Active |
| **numpy** | 1.26.x | Array operations | Active |

## Optional Dependencies

### Cloudflare / Browser Automation
| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| **playwright** | 1.49.x | Browser automation (JS-rendered pages) | Optional |
| **curl-cffi** | 0.14.x | HTTP client with TLS impersonation | Optional |
| **socksio** | 1.0.x | SOCKS proxy support | Optional |
| **browserforge** | 1.2.x | Browser fingerprint | Optional |

### Testing
| Technology | Version | Purpose |
|------------|---------|---------|
| **pytest** | 9.0.x | Test framework |
| **pytest-asyncio** | 1.0.x | Async test support |
| **pytest-cov** | 7.0.x | Coverage reporting |
| **pytest-mock** | 3.15.x | Mocking |
| **pytest-httpx** | 0.36.x | HTTP mocking |

### Cross-Encoder Reranking
| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| **transformers** | 4.40.x | BAAI/bge-reranker-base model | Optional (ml) |
| **torch** | 2.0.x | PyTorch (required by transformers) | Optional (ml) |
| **safetensors** | 0.4.x | Safe model loading | Optional (ml) |

## Deprecated / Replaced

| Technology | Status | Replacement |
|------------|--------|-------------|
| **httpx** | Removed | scrapling.Fetcher |

## Architecture Notes

- **Async**: uvloop for event loop, asyncio for concurrency
- **HTML Parsing**: scrapling (CSS selectors) replaces BeautifulSoup + lxml for provider/discovery
- **HTTP Client**: scrapling.Fetcher (sync) wrapped with asyncio.to_thread, or AsyncFetcher (native async)
- **Semantic Search**: ChromaDB + sentence-transformers (all-MiniLM-L6-v2)
- **Config**: dynaconf reads from config.yaml (no hardcoded values)
