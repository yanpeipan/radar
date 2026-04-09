# Phase 21: Storage Extension — Plan

**Phase:** 21
**Goal:** LLM outputs persisted and queryable in SQLite and ChromaDB
**Depends on:** Phase 20
**Requirements:** STOR-01, STOR-02, STOR-03

## Task 1: SQLite Schema Migration

**File:** `src/storage/sqlite/init.py`

1. Add to `_ARTICLES_EXTRA_COLUMNS`:
   ```python
   _ARTICLES_EXTRA_COLUMNS = {
       "author": "TEXT",
       "tags": "TEXT",
       "category": "TEXT",
       "meta": "TEXT",
       # NEW:
       "summary": "TEXT",
       "quality_score": "REAL",
       "keywords": "TEXT",       # JSON array
       "summarized_at": "TEXT",  # ISO timestamp
   }
   ```
2. The forward-compatibility `ALTER TABLE` loop (lines ~76-84) handles existing DBs automatically

## Task 2: Storage Functions

**File:** `src/storage/sqlite/impl.py` (new functions)

1. **`update_article_llm(article_id, summary, quality_score, keywords, tags)`**
   - Updates summary, quality_score, keywords (JSON), tags (JSON), summarized_at fields
   - Accepts 8-char truncated ID (like existing `update_article_content`)
   - Returns `{"success": bool, "error": str | None}`

2. **`get_article_with_llm(article_id)`**
   - SELECT with all LLM fields (summary, quality_score, keywords, tags, summarized_at)
   - JOIN with feeds to get feed_name, weight
   - Returns `ArticleWithLLM` dataclass

3. **`list_articles_for_llm(limit, feed_id, group, since, until, min_quality)`**
   - Returns articles lacking LLM data (summary IS NULL) or force=True
   - Used by summarize batch processing
   - Filters: feed_id, group, date range, min_quality threshold

4. **`list_articles_for_llm_by_group(group, ...)`**
   - Returns articles grouped by category for report clustering

## Task 3: ChromaDB Collections

**File:** `src/storage/vector.py` (extend)

1. **`init_llm_collections()`** — initialize `article_summaries` and `article_keywords` collections
2. **`upsert_article_summary(article_id, summary_text, embedding)`** — store summary + embedding
3. **`upsert_article_keywords(article_id, keywords, embeddings)`** — store keywords + embeddings
4. **`search_summaries(query_embedding, top_k)`** — semantic search over summaries
5. **`search_keywords(query_embedding, top_k)`** — semantic search over keywords

## Task 4: Export from storage package

**File:** `src/storage/__init__.py`

Export new functions.

## Verify

- Run: `uv run pytest tests/ -v -k "llm or storage" --tb=short`
- Manual: `uv run feedship article list --json | python -c "import json,sys; d=json.load(sys.stdin); print([k for k in d.keys()])"`
