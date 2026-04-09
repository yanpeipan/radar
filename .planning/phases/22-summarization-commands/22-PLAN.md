# Phase 22: Summarization Commands — Plan

**Phase:** 22
**Goal:** Users can summarize articles individually or in batch, with quality scoring and keyword extraction
**Depends on:** Phase 20, Phase 21

## Task 1: Application Layer — Summarization Logic

**File:** `src/application/summarize.py` (new)

Create `process_article_llm(article_id, force=False)` that:
1. Fetches article with `get_article_with_llm(article_id)`
2. Computes `content_hash` to check if content changed (skip if same and not force)
3. Runs `summarize_text(content, title)` → `summary`
4. Runs `score_quality(content, title)` → `quality_score`
5. Runs `extract_keywords(content)` → `keywords`
6. Calls `update_article_llm()` to persist to SQLite
7. Calls `upsert_article_summary()` and `upsert_article_keywords()` for ChromaDB
8. Returns dict with `summary`, `quality_score`, `keywords`, `tokens_used`, `model_used`

## Task 2: CLI Command — Summarize

**File:** `src/cli/summarize.py` (new)

```python
@cli.command("summarize")
@click.option("--url", help="Summarize article at URL directly")
@click.option("--id", help="Summarize article by ID")
@click.option("--group", help="Summarize all articles in group")
@click.option("--feed-id", help="Summarize all articles in feed")
@click.option("--all", "all_", is_flag=True, help="Summarize ALL unsummarized articles")
@click.option("--force", is_flag=True, help="Force re-summarize even if already done")
@click.option("--dry-run", is_flag=True, help="Preview articles to process without LLM call")
@click.option("--json", "json_output", is_flag=True, help="JSON output")
@click.option("--limit", default=50, help="Max articles to process in batch mode")
@click.pass_context
def summarize(...)
```

- At least one of `--url`, `--id`, `--group`, `--feed-id`, `--all` required
- `--url` mode: fetch → extract text with trafilatura → process directly (no DB)
- `--id` mode: get from DB, call `process_article_llm()`
- `--group/--feed-id/--all` modes: use `list_articles_for_llm()` batch processing
- Rich progress bar with `Progress()` showing article title, status
- `--dry-run` shows count and list without calling LLM
- JSON output: per-article {id, title, summary, quality_score, keywords}

## Task 3: CLI Command — Article List with Quality

**File:** `src/cli/article.py` (modify `article_list`)

Add:
- `--sort quality` — sort by quality_score DESC
- `--min-quality FLOAT` — filter articles with quality_score >= FLOAT

Update `list_articles` in `src/application/articles.py` to support `sort_by` and `min_quality` params.

## Task 4: Module Registration

**File:** `src/cli/__init__.py`

Add `summarize` to the import list.

## Verify

```bash
uv run feedship summarize --help
uv run feedship summarize --all --dry-run
uv run python -c "from src.application.summarize import process_article_llm; print('ok')"
```
