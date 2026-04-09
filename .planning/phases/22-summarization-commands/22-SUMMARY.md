# Phase 22: Summarization Commands — Summary

**Phase:** 22
**Goal:** Users can summarize articles individually or in batch, with quality scoring and keyword extraction
**Status:** ✅ Complete

## What Was Done

### 1. Application Layer (`src/application/summarize.py` — NEW)
- `process_article_llm(article_id, force=False)` — runs summarize_text + score_quality + extract_keywords in parallel, persists to SQLite + ChromaDB
- `process_article_llm_batch(article_ids, force=False)` — batch version with asyncio.Semaphore(5) concurrency

### 2. CLI Command (`src/cli/summarize.py` — NEW)
- `feedship summarize --url <url>` — fetch directly, no DB
- `feedship summarize --id <article_id>` — single article from DB
- `feedship summarize --group <name>` — batch by group
- `feedship summarize --feed-id <id>` — batch by feed
- `feedship summarize --all` — all unsummarized articles
- `--force` flag to re-summarize
- `--dry-run` preview without LLM calls
- `--json` machine-readable output
- `--limit N` for batch size control
- Rich Progress bar with per-article status output

### 3. Article List Enhancement (`src/cli/article.py`)
- Added `--sort quality` — sorts by quality_score DESC
- Added `--min-quality FLOAT` — filters by quality_score >= value
- JSON output includes quality_score field

### 4. Storage Layer (`src/storage/sqlite/impl.py`)
- `list_articles()` now supports `sort_by` and `min_quality` parameters
- Added `quality_score` to SELECT and ArticleListItem dataclass
- WHERE clause adds `quality_score >= ?` when min_quality is set
- ORDER BY switches to `quality_score DESC, published_at DESC` when sort_by="quality"

### 5. JSON Serialization (`src/cli/ui.py`)
- `_serialize_article()` now includes `quality_score` in output

### 6. Module Registration (`src/cli/__init__.py`)
- Added `summarize` to the import list

## Files Changed

- `src/application/summarize.py` — NEW
- `src/cli/summarize.py` — NEW
- `src/cli/article.py` — added --sort/--min-quality
- `src/application/articles.py` — added sort_by/min_quality params + quality_score field
- `src/storage/sqlite/impl.py` — added sort_by/min_quality support
- `src/cli/ui.py` — added quality_score to serialization
- `src/cli/__init__.py` — registered summarize command

## Verification

- `uv run feedship summarize --help` ✅
- `uv run feedship article list --help | grep sort` ✅
- `uv run python -m py_compile` on all modified files ✅

## Next

Phase 23: Report Generation — topic clustering and the `feedship report` command
