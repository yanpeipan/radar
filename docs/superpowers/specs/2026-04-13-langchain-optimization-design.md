# LangChain Optimization & Report Module Refactor

## Status
- Author: yanpeipan
- Date: 2026-04-13
- Approved: Yes (in-session user approval)

---

## 1. Overview

**Goal:** Refactor the report generation pipeline to use standard LangChain LCEL patterns, eliminate event loop leaks, fix performance/memory issues, and improve code structure.

**Scope:**
- Report module (`src/application/report/`)
- Storage layer (`src/storage/sqlite/`)
- LLM chain interfaces (`src/llm/chains.py`)

**Target Outcomes:**
- Memory: Reduce peak memory by streaming articles instead of loading all 3333 into memory
- Performance: Fix O(n) freshness computation, dedup memory bloat, write lock duplication
- Code: Replace custom Runnable classes with standard LCEL patterns
- LangChain: Use GeneratorRunnable for streaming pipeline

---

## 2. Architecture

### 2.1 Current State Problems

| Issue | Location | Severity |
|-------|----------|----------|
| Custom Runnable classes don't compose via `\|` | `classify.py`, `tldr.py`, `models.py` | 🔴 Critical |
| `new_event_loop()` leaks per invoke | All chain classes | 🔴 Critical |
| `list_articles` computes freshness for all rows | `articles.py:456` | 🔴 Critical |
| Duplicate `_db_write_lock` | `conn.py` + `articles.py` | 🔴 Critical |
| 3x article list during dedup | `dedup.py` | 🟡 Medium |
| SignalFilter re-implements dedup | `filter.py` | 🟡 Medium |
| Misleading "tz is ignored" docstring | `utils.py:65` | 🟢 Low |

### 2.2 Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Report Generation Pipeline                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐          │
│  │ articles │───▶│  Dedup   │───▶│ SignalFilter │          │
│  │ (stream) │    │ (stream) │    │   (stream)   │          │
│  └──────────┘    └──────────┘    └──────────────┘          │
│                                             │                │
│                                             ▼                │
│  ┌──────────────┐    ┌──────────────────────────────┐      │
│  │ BatchClassify │───▶│ BuildReportData (streaming) │      │
│  │  (LCEL map)  │    │      (GeneratorRunnable)     │      │
│  └──────────────┘    └──────────────────────────────┘      │
│                                             │                │
│                                             ▼                │
│  ┌──────────────┐    ┌──────────────────────────────┐      │
│  │  TLDRChain   │───▶│   ReportTemplate.render     │      │
│  │ (LCEL map)   │    │      (async generator)      │      │
│  └──────────────┘    └──────────────────────────────┘      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Key Changes

#### A. Streaming Pipeline (GeneratorRunnable)

Replace `_entity_report_async` with a streaming pattern:

```python
from langchain_core.runnables import RunnableGenerator

async def article_generator(since, until, limit):
    """Yield articles in batches to avoid loading all into memory."""
    for batch in chunked(list_articles(...), batch_size=100):
        yield batch

# Stream through dedup → filter → classify → build
pipeline = (
    RunnableGenerator(article_generator)
    | DedupRunnable()           # streaming dedup
    | SignalFilterRunnable()    # streaming filter
    | BatchClassifyRunnable()   # LCEL map with semaphore
    | BuildReportDataRunnable() # streaming build
    | TLDRRunnable()           # LCEL map
)
```

#### B. Fix Event Loop Leaks

Replace `new_event_loop()` pattern with `asyncio.run()`:

```python
# BEFORE (leaks event loops)
def invoke(self, input, config=None):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(self.ainvoke(input, config))
    finally:
        loop.close()

# AFTER (uses running loop or creates single loop)
def invoke(self, input, config=None):
    try:
        loop = asyncio.get_running_loop()
        return loop.run_until_complete(self.ainvoke(input, config))
    except RuntimeError:
        return asyncio.run(self.ainvoke(input, config))
```

#### C. Fix list_articles Freshness Computation

```python
# BEFORE: always computes freshness
return [_compute_article_item(row) for row in rows]

# AFTER: only compute when needed
def _compute_article_item(row, compute_freshness=False):
    freshness = 0.0
    if compute_freshness:
        pub_ts = _published_at_to_timestamp(row["published_at"])
        if pub_ts:
            days_ago = (datetime.now(timezone.utc) - datetime.fromtimestamp(pub_ts, tz=timezone.utc)).days
            freshness = math.exp(-days_ago / 7)
    return ArticleListItem(..., freshness=freshness, ...)
```

#### D. Single Source of Truth for Write Lock

Move `_db_write_lock` to `conn.py` only:

```python
# conn.py
_db_write_lock: asyncio.Lock | None = None

def _get_db_write_lock() -> asyncio.Lock:
    global _db_write_lock
    if _db_write_lock is None:
        _db_write_lock = asyncio.Lock()
    return _db_write_lock

# articles.py - import from conn instead of redefining
from src.storage.sqlite.conn import _get_db_write_lock
```

#### E. Streaming Dedup (Memory Optimization)

```python
async def _level1_exact_dedup_streaming(articles):
    """Streaming exact dedup - yields articles as they pass dedup check."""
    seen: set[str] = set()
    for article in articles:
        ch = article.content_hash
        if ch is None or ch not in seen:
            seen.add(ch or id(article))
            yield article
```

---

## 3. Component Changes

### 3.1 Report Module

| File | Change |
|------|--------|
| `generator.py` | Replace `_entity_report_async` with streaming GeneratorRunnable pipeline |
| `classify.py` | Replace `BatchClassifyChain` with LCEL `RunnableLambda` + `.map()` |
| `tldr.py` | Replace `TLDRChain` with LCEL `RunnableLambda` + `.map()` with semaphore |
| `models.py` | Replace `BuildReportDataChain` with `RunnableLambda` or `RunnableGenerator` |
| `filter.py` | Remove dedup logic (now in dedup.py), keep only signal filter rules |

### 3.2 Storage Layer

| File | Change |
|------|--------|
| `articles.py` | Remove duplicate `_db_write_lock`, import from `conn.py` |
| `conn.py` | Single source of truth for `_db_write_lock` |
| `utils.py` | Fix docstring: `_date_to_str` does use `tz` parameter |

### 3.3 Dedup Module

| File | Change |
|------|--------|
| `dedup.py` | Add streaming variants: `_level1_exact_dedup_streaming()`, `_level2_minhash_streaming()` |

---

## 4. LCEL Migration Details

### 4.1 Custom Runnable → Standard LCEL

**Before:**
```python
class BatchClassifyChain(Runnable):
    def __init__(self, tag_list, target_lang, ...):
        ...

    async def ainvoke(self, input, config=None):
        # batch processing
        ...
        return input
```

**After:**
```python
from langchain_core.runnables import RunnableLambda

def make_classify_runnable(tag_list, target_lang):
    async def classify_fn(articles):
        # batching logic
        ...
        return enriched_articles
    return RunnableLambda(classify_fn)
```

### 4.2 Streaming with GeneratorRunnable

`RunnableGenerator` accepts a **sync generator function** (not async). For async streaming, use `astream()` method on the pipeline instead.

```python
from langchain_core.runnables import RunnableGenerator

def article_gen(since, until, limit):
    """Sync generator - yields articles in chunks."""
    articles = list_articles(limit=limit, since=since, until=until)
    for article in articles:
        yield article

# For async streaming, wrap in async generator and use .astream():
async def article_gen_async(since, until, limit):
    articles = list_articles(limit=limit, since=since, until=until)
    for article in articles:
        yield article

# Pipeline using async astream()
pipeline = (
    RunnableLambda(article_gen_async)
    | DedupRunnable()
    | SignalFilterRunnable()
    | BatchClassifyRunnable()
    | BuildReportDataRunnable()
    | TLDRRunnable()
)

# Usage: async for chunk in pipeline.astream({"since": since, "until": until, "limit": limit}):
```

**Key distinction:**
- `RunnableGenerator(fn)` — fn is sync generator, use `.invoke()` or `.stream()`
- For async generators, use `RunnableLambda(async_gen_fn)` and `.astream()`

---

## 5. Performance Optimizations

### 5.1 Write Lock Consolidation

- **Before:** Two separate `_db_write_lock` instances in `conn.py` and `articles.py`
- **After:** Single lock in `conn.py`, imported by `articles.py`
- **Impact:** Prevents potential race conditions in async write paths

### 5.2 Freshness Computation

- **Before:** Computed for every row in every query
- **After:** Only computed when `sort_by == "quality"` or `compute_freshness=True`
- **Impact:** ~50% CPU reduction on `list_articles` calls

### 5.3 Dedup Memory

- **Before:** Holds `step1`, `step2`, `step3` simultaneously
- **After:** Streaming dedup with generator, single copy at a time
- **Impact:** 3x reduction in peak memory during dedup

---

## 6. Error Handling

| Component | Strategy |
|-----------|----------|
| LCEL chain | Use `.with_retry()` for LLM calls |
| Dedup | Log and skip individual failures, don't fail entire pipeline |
| DB writes | Lock serialization prevents "database locked" |
| LLM batch | Semaphore limits concurrency, exceptions logged and skipped |

---

## 7. Testing Strategy

- Unit tests for each LCEL runnable step
- Integration test for full streaming pipeline
- Memory profiling: verify peak memory < 100MB for 3333 articles
- Performance benchmark: compare before/after list_articles latency

---

## 8. Migration Path

1. **Phase 1:** Fix critical bugs (event loops, write lock) — no behavioral change
2. **Phase 2:** Migrate custom Runnables to standard LCEL — backward compatible
3. **Phase 3:** Implement streaming pipeline — memory optimization
4. **Phase 4:** Polish and dedup deduplication — remove redundant work

---

## 9. Files to Change

```
src/application/report/generator.py    # Streaming pipeline
src/application/report/classify.py    # LCEL migration
src/application/report/tldr.py       # LCEL migration
src/application/report/models.py      # BuildReportDataChain → LCEL
src/application/report/filter.py      # Remove dedup, keep signal filter
src/application/dedup.py             # Add streaming variants
src/storage/sqlite/articles.py       # Remove duplicate lock, fix freshness
src/storage/sqlite/conn.py            # Single source of truth for lock
src/storage/sqlite/utils.py           # Fix docstring
src/llm/chains.py                    # Expose runnable factories
```
