# CLI Reference

## Commands

| Command | Description |
|---------|-------------|
| `feed add <url>` | Subscribe to a feed (auto-detects RSS/GitHub) |
| `feed list` | List all subscribed feeds |
| `feed remove <id>` | Unsubscribe from a feed |
| `fetch --all` | Fetch new articles from all feeds |
| `fetch <id> [<id>...]` | Fetch from specific feeds |
| `discover <url>` | Discover feeds on a website (without subscribing) |
| `article list` | List recent articles |
| `article view <id>` | View full article content |
| `article open <id>` | Open article URL in browser |
| `article related <id>` | Find semantically related articles |
| `search <query>` | Keyword search (FTS5) |
| `search <query> --semantic` | Semantic search (ChromaDB) |
| `search <query> --rerank` | Search with Cross-Encoder reranking |

## feed

### feed add

```
feed add <url> [--discover] [--automatic]
```

Subscribe to a feed. Auto-detects RSS, Atom, or GitHub releases.

### feed list

```
feed list
```

List all subscribed feeds with ID, name, URL, and provider type.

### feed remove

```
feed remove <id>
```

Unsubscribe and remove a feed and its articles.

## fetch

### fetch --all

```
fetch --all [--concurrency 10]
```

Fetch all subscribed feeds concurrently. Default concurrency: 10 (max 100).

### fetch (specific)

```
fetch <feed_id> [<feed_id>...]
```

Fetch from specific feeds by ID.

## discover

### discover

```
discover <url> [--discover-depth 1]
```

Discover RSS/Atom/RDF feeds on a website without subscribing. Crawls links up to specified depth.

## article

### article list

```
article list [--limit 20] [--feed-id <id>] [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--on YYYY-MM-DD]
```

List recent articles. Supports date filtering.

### article view

```
article view <id>
```

Display full article content (extracted via Readability).

### article open

```
article open <id>
```

Open article URL in default browser.

### article related

```
article related <id> [--limit 5]
```

Find semantically related articles using ChromaDB embeddings.

## search

### Keyword search (FTS5)

```
search <query> [--limit 20] [--feed-id <id>] [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--on YYYY-MM-DD]
```

Full-text search using SQLite FTS5. Results ranked by BM25 score.

### Semantic search (ChromaDB)

```
search <query> --semantic [--limit 20] [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--on YYYY-MM-DD]
```

Vector similarity search using sentence-transformers embeddings.

### With Cross-Encoder reranking

```
search <query> --semantic --rerank
search <query> --rerank
```

Applies Cross-Encoder reranking (BAAI/bge-reranker-base) before final scoring.

### Scoring

Search results use unified scoring via `combine_scores()`:

- **Semantic path**: `alpha×ce_score + beta×freshness + gamma×vec_sim` (gamma=0.2, delta=0.0)
- **FTS5 path**: `alpha×ce_score + beta×freshness + delta×bm25_score` (gamma=0.0, delta=0.2)
- alpha=0.3, beta=0.3 (always applied)
- Cross-Encoder reranking fills `ce_score` when `--rerank` is used
