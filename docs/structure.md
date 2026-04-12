# Application Structure

## Directory Layout

```
src/
├── cli/               # CLI commands (click)
│   └── report.py      # Report generation command
├── application/       # Business logic (fetch, feed, articles, search)
│   ├── feed.py        # Feed CRUD
│   ├── fetch.py       # Fetch orchestration
│   ├── articles.py    # Article CRUD
│   ├── report/        # Report generation (models, generator, template, classify, filter, tldr)
├── providers/          # Plugin providers (RSS, GitHub, Default)
├── storage/            # Data access (SQLite, ChromaDB)
├── discovery/          # Feed discovery (BFS crawler, parser)
├── utils/              # Utilities
└── models.py           # Dataclasses (Feed, Article, Tag)
```

## Source Files

| File | Responsibility |
|------|----------------|
| `cli/__init__.py` | cli() entry point |
| `cli/__main__.py` | CLI bootstrap |
| `cli/feed.py` | feed add/list/remove |
| `cli/article.py` | article list/view/open/related, search |
| `cli/discover.py` | discover command |
| `application/feed.py` | add_feed, list_feeds, remove_feed |
| `application/fetch.py` | fetch orchestration (uvloop at boundaries) |
| `application/articles.py` | Article CRUD, ArticleListItem dataclass |
| `application/search.py` | (merged into article.py) |
| `application/rerank.py` | Cross-Encoder reranking (BAAI/bge-reranker-base) |
| `application/combine.py` | combine_scores() unified ranking |
| `application/config.py` | Configuration (bm25_factor, etc.) |
| `application/discover.py` | Discovery orchestration |
| `cli/report.py` | report command (--since, --until, --language, --template, --output) |
| `application/report/models.py` | ReportArticle, ReportCluster, ReportData dataclasses |
| `application/report/generator.py` | cluster_articles_for_report(), _entity_report_async() |
| `application/report/template.py` | ReportTemplate, HeadingNode, parse_markdown_headings() |
| `application/report/classify.py` | BatchClassifyChain (LCEL chain for LLM classification) |
| `application/report/filter.py` | SignalFilter (rules-based article filtering) |
| `application/report/tldr.py` | TLDRChain (LCEL chain for TLDR generation) |
| `providers/__init__.py` | Provider registry |
| `providers/base.py` | ContentProvider protocol |
| `providers/rss_provider.py` | RSS/Atom (priority 50) |
| `providers/default_provider.py` | Default fallback |
| `providers/github_release_provider.py` | GitHub releases (priority 200) |
| `storage/sqlite/impl.py` | SQLite data access |
| `storage/vector.py` | ChromaDB semantic search |
| `discovery/` | Auto-discovery (BFS crawler, HTML parser) |
| `models.py` | Dataclasses (Feed, Article, Tag) |

## Structural Rules

1. **DB via context manager**: `with get_db() as conn:` not bare `get_connection()`
2. **No circular imports**: shared logic in base.py
3. **CLI is thin**: business logic in application/
4. **parse_feed() ≠ crawl()**: metadata separate from content
5. **Single DAL**: storage/ owns all SQL
6. **uvloop at boundaries**: `uvloop.run()` only at CLI entry points, `asyncio.to_thread()` for blocking I/O
