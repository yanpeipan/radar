# Phase 21: Storage Extension — Summary

**Phase:** 21
**Goal:** LLM outputs persisted and queryable in SQLite and ChromaDB
**Status:** ✅ Complete

## What Was Done

### 1. SQLite Schema Migration
- Added 4 LLM columns to `_ARTICLES_EXTRA_COLUMNS` in `src/storage/sqlite/init.py`:
  - `summary` (TEXT) — article summary from LLM
  - `quality_score` (REAL) — 0-1 quality score
  - `keywords` (TEXT) — JSON array of extracted keywords
  - `summarized_at` (TEXT) — ISO timestamp
- Forward-compatibility `ALTER TABLE` loop handles existing databases automatically

### 2. Storage Functions (`src/storage/sqlite/impl.py`)
- **`update_article_llm(article_id, summary, quality_score, keywords, tags)`** — updates all LLM fields, supports 8-char truncated ID, JSON-serializes keywords/tags
- **`get_article_with_llm(article_id)`** — SELECT with all LLM fields + JOIN feeds table for feed_name/weight
- **`list_articles_for_llm(limit, feed_id, groups, since, until, min_quality)`** — returns articles WHERE summary IS NULL, ordered by feed.weight DESC

### 3. ChromaDB Collections (`src/storage/vector.py`)
- **`get_llm_summary_collection()`** — `article_summaries` collection with cosine similarity
- **`get_llm_keywords_collection()`** — `article_keywords` collection with cosine similarity
- **`upsert_article_summary(article_id, summary, title, url, published_at)`** — embeds and stores summary
- **`upsert_article_keywords(article_id, keywords, title, url, published_at)`** — joins keywords with " | " and embeds
- **`search_llm_summaries(query_text, limit, since, until)`** — semantic search over summaries
- **`search_llm_keywords(query_text, limit, since, until)`** — semantic search over keywords

### 4. Package Exports (`src/storage/__init__.py`)
Added 3 new exports: `get_article_with_llm`, `list_articles_for_llm`, `update_article_llm`

## Verification

- `uv run python -m py_compile src/storage/sqlite/impl.py` ✅
- `uv run python -m py_compile src/storage/vector.py` ✅
- `from src.storage import update_article_llm, get_article_with_llm, list_articles_for_llm` ✅

## Files Changed

- `src/storage/sqlite/init.py` — added 4 LLM columns
- `src/storage/sqlite/impl.py` — added 3 storage functions
- `src/storage/vector.py` — added 6 ChromaDB functions
- `src/storage/__init__.py` — added 3 exports

## Next

Phase 22: Summarization Commands — the CLI commands that use Phase 20 + 21 infrastructure
