# Optional Dependencies

Feedship supports optional dependency groups for enhanced functionality.

## Installation

```bash
# Core installation
pip install feedship

# ML/AI features
pip install feedship[ml]

# Browser automation features
pip install feedship[cloudflare]

# All features
pip install feedship[ml,cloudflare]
```

---

## ML Extra (`[ml]`)

Provides semantic search and related article functionality.

### Included Packages

| Package | Version | Purpose |
|---------|---------|---------|
| chromadb | >=0.4.0 | Vector database for embeddings |
| sentence-transformers | >=3.0.0 | Sentence embedding models |
| torch | >=2.0.0 | PyTorch (Python < 3.13) |
| safetensors | >=0.4.3 | Safe tensor serialization |
| transformers | >=4.40.0 | HuggingFace transformers |

### Features Enabled

- **`feedship search --semantic`**: Vector similarity search using sentence-transformers
- **`feedship article related`**: Find semantically related articles
- Automatic article embedding and storage
- Cross-Encoder reranking with `--rerank` flag

### Requirements

- Python < 3.13 (torch compatibility)
- ~2GB disk space for models
- GPU recommended for faster embeddings (optional)

### Example

```bash
# Install ML dependencies
pip install feedship[ml]

# Use semantic search
feedship search "machine learning frameworks" --semantic

# Find related articles
feedship article related abc12345 --limit 10

# Semantic with reranking
feedship search "Python best practices" --semantic --rerank
```

---

## Cloudflare Extra (`[cloudflare]`)

Provides enhanced web scraping with browser automation.

### Included Packages

| Package | Version | Purpose |
|---------|---------|---------|
| scrapling | >=0.4.0 | CSS-selector HTML parsing (already in base) |
| playwright | >=1.49.0 | Browser automation |
| curl-cffi | >=0.14.0 | Fast HTTP with Cloudflare bypass |
| socksio | >=1.0.0 | SOCKS protocol support |
| browserforge | >=1.2.0 | Browser fingerprint management |

### Features Enabled

- **`feedship feed add`**: Enhanced feed discovery with JavaScript rendering
- **`feedship discover`**: Deep crawling with browser rendering
- Cloudflare-aware fetching
- Better handling of JavaScript-heavy sites

### Requirements

- Playwright browsers installed: `playwright install`
- ~500MB disk space for browsers

### Example

```bash
# Install Cloudflare dependencies
pip install feedship[cloudflare]

# Install Chromium browser
playwright install chromium

# Discover feeds on JavaScript-heavy sites
feedship discover https://example-javascript-site.com --discover-depth 2
```

---

## Dependency Hierarchy

```
feedship (base)
├── feedparser     # RSS/Atom parsing
├── httpx          # HTTP client
├── click          # CLI framework
├── beautifulsoup4 # HTML parsing
├── rich           # Terminal UI
├── PyGithub       # GitHub API
├── dynaconf       # Configuration
├── trafilatura     # Article extraction
├── robotexclusionrulesparser  # robots.txt
├── platformdirs   # Platform directories
├── numpy          # Array operations
├── scikit-learn   # BM25 ranking
├── pyyaml         # YAML config
├── uvloop         # Async event loop
├── nanoid         # ID generation
├── scrapling      # CSS HTML parsing
└── msgspec        # Fast serialization
    │
    ├── [ml]
    │   ├── chromadb
    │   ├── sentence-transformers
    │   ├── torch
    │   ├── safetensors
    │   └── transformers
    │
    └── [cloudflare]
        ├── playwright
        ├── curl-cffi
        ├── socksio
        └── browserforge
```

---

## Troubleshooting

### ML Features Unavailable

```bash
# Error: "Search unavailable: No module named 'chromadb'"
# Solution:
pip install feedship[ml]
```

### Semantic Search Slow

- First run downloads ~500MB of transformer models
- Use GPU for 10x faster embeddings
- Consider using `--limit` to reduce search scope

### Playwright Browser Issues

```bash
# Install browsers
playwright install

# Or install specific browser
playwright install chromium
```
