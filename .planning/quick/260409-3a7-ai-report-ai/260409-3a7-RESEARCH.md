# Quick Task 260409-3a7: AI Architect Evaluation + Fix Top 3 Issues + AI News Analyst Quality

**Researched:** 2026-04-09
**Domain:** report.py architecture — v2 clustering pipeline, DB writes in async context, translation pattern
**Confidence:** MEDIUM-HIGH (code inspection + prior S6089 findings)

## Summary

The v2 report pipeline (`_cluster_articles_v2_async`) has 4 remaining critical issues from S6089 after the per-cluster LLM classification fix in 260409-20c. The top 3 most serious are: **(3) sync DB writes inside asyncio.gather**, **(5) event loop leak in `_translate_title_sync`**, and **(4) O(n) LLM calls for line-by-line translation**. Issue #1 (double deduplication) is lower priority since v2 only deduplicates once.

**Primary recommendation:** Fix the DB write pattern by extracting all `update_article_llm` calls out of `asyncio.gather` and batching them post-gather. Fix the event loop leak by making translation use an async chain. Fix the line-by-line translation by batching lines.

---

## Issue Priority Assessment

| # | Issue | Severity | Fix Complexity | Rationale |
|---|-------|----------|----------------|-----------|
| 3 | `update_article_llm` sync DB write inside `asyncio.gather` | **HIGH** | Medium | Data loss risk, "database is locked" SQLite errors under concurrency |
| 5 | Event loop leak in `_translate_title_sync` | **HIGH** | Low-Medium | `asyncio.new_event_loop()` + `loop.close()` in sync function, called from Jinja2 filter |
| 4 | O(n) LLM calls for line-by-line translation | **HIGH** | Medium | 1000 lines = 1000 LLM calls; should batch |
| 1 | deduplicate_articles called twice | **MEDIUM** | Low | v2 pipeline only calls it once (line 816); v1 has no dedup — actual data loss risk is unclear |

---

## Issue #3: Sync DB Writes Inside asyncio.gather (CRITICAL)

**Files affected:** `src/application/report.py` lines 680, 773

**What goes wrong:**
```python
# Line 709-713 in _cluster_articles_async (v1):
classified = await asyncio.gather(
    *[bounded_process(a) for a in articles],  # up to 10 concurrent
    return_exceptions=True,
)
# Inside bounded_process -> process_one -> update_article_llm (sync SQLite write)
```

Each `update_article_llm` call at line 680 opens its own DB connection via `with get_db() as conn`. With a semaphore of 10 and 200 articles, up to 10 concurrent writes can fire simultaneously. SQLite will throw "database is locked" or write can silently fail under contention.

**How to fix:**
1. **Post-gather batch:** Collect all pending writes during gather, then do them sequentially or in batches after `asyncio.gather` completes.
2. Or: use `asyncio.to_thread()` to run sync DB writes on a thread pool, avoiding blocking the async event loop.
3. Or: use ` connexion` to defer writes to a background queue.

**Pattern to use:**
```python
# Instead of write inside gather, collect pending writes:
pending_writes: list[tuple[str, str, float]] = []

async def bounded_process(a):
    async with semaphore:
        result = await process_one(a)
        if result.should_write:
            pending_writes.append(result.write_params)  # non-blocking collection
        return result

# After gather completes:
for params in pending_writes:
    update_article_llm(*params)
```

---

## Issue #5: Event Loop Leak in `_translate_title_sync`

**File:** `src/application/report.py` lines 436-463

**What goes wrong:**
```python
def _translate_title_sync(title: str, target_lang: str) -> str:
    def _run():
        loop = asyncio.new_event_loop()   # new loop each call
        try:
            return asyncio.run(_translate())  # runs ainvoke in new loop
        finally:
            loop.close()  # close in same thread — ok here but pattern is fragile
```
`asyncio.run()` creates AND CLOSES the event loop internally. Then `_run()` creates ANOTHER new loop with `asyncio.new_event_loop()`. This is redundant but not technically a "leak" — `loop.close()` is called.

**However:** This function is called from a **Jinja2 filter** (`env.filters["format_title"]` at lines 929, 981) which runs during **synchronous template rendering**. If the template iterates over 100 articles, this creates 100 separate event loops sequentially. The `loop.close()` in the same thread is fine, but the pattern is fragile and creates unnecessary overhead.

**How to fix:**
1. Make `_translate_title_sync` use `asyncio.get_event_loop()` (retrieve existing loop) instead of creating a new one.
2. Or better: pre-translate all titles before template rendering (async batch), not lazily during template render.
3. Or: use a single shared event loop for all translations.

**Recommended approach:** Pre-translate titles in the async pipeline before template rendering:
```python
async def _translate_titles_batch(titles: list[str], target_lang: str) -> dict[str, str]:
    chain = get_translate_chain()
    results = await asyncio.gather(*[chain.ainvoke({"text": t, "target_lang": target_lang}) for t in titles])
    return dict(zip(titles, results))
```

---

## Issue #4: Line-by-Line O(n) LLM Translation

**File:** `src/application/report.py` lines 1016-1022

**What goes wrong:**
```python
async def _translate_report_async(report_text: str, target_lang: str) -> str:
    lines = report_text.splitlines()
    for line in lines:  # O(n) LLM calls
        result = await chain.ainvoke({"text": line, "target_lang": target_lang})
        translated_lines.append(result)
```
A 200-line report = 200 LLM calls. A 1000-line report = 1000 LLM calls.

**How to fix:**
1. Batch lines: group 5-10 lines into one prompt with instructions to translate each line individually.
2. Use a single prompt with all lines listed, ask LLM to return translations in numbered format.
3. Parallel batch: use `asyncio.gather` with semaphore on batches (not individual lines).

**Recommended pattern:**
```python
async def _translate_report_async(report_text: str, target_lang: str) -> str:
    chain = get_translate_chain()
    lines = report_text.splitlines()

    # Batch lines: 10 lines per LLM call
    batch_size = 10
    batches = [lines[i:i+batch_size] for i in range(0, len(lines), batch_size)]

    translated_texts = []
    for batch in batches:
        # Skip article link lines
        non_link_lines = [(j, line) for j, line in enumerate(batch) if "]((" not in line and "](http" not in line]
        link_lines = {j: line for j, line in enumerate(batch) if "]((" in line or "](http" in line}

        if non_link_lines:
            prompt = "\n".join([f"{j+1}. {line}" for j, line in non_link_lines])
            result = await chain.ainvoke({
                "text": f"Translate the following lines:\n{prompt}",
                "target_lang": target_lang
            })
            # Parse result back to lines...

    return "\n".join(translated_texts)
```

---

## Issue #1: Double Dedup — Lower Priority

**Analysis:** The v2 pipeline at line 816 only calls `deduplicate_articles` once. The v1 pipeline (`_cluster_articles_async`) does NOT call `deduplicate_articles` at all. So there is no "called twice" within v2.

The actual data loss risk in v1 is **lack of deduplication** (not double deduplication). The issue description may be referring to:
- v1: no dedup (articles with duplicate content appear in report)
- v2: deduplicates (some legitimate articles may be incorrectly removed if dedup thresholds are too aggressive)

**Status:** MEDIUM severity concern for v1 (no dedup). v2 appears safe with single dedup call.

---

## Don't Hand-Roll

| Problem | Use Instead | Notes |
|---------|-------------|-------|
| Event loop management in sync wrapper | `asyncio.get_event_loop()` or pre-batch async | Current pattern creates redundant loops |
| Per-line LLM translation | Batch translation (5-10 lines per call) | Current O(n) calls = 200-1000 LLM calls per report |
| Concurrent SQLite writes | Post-gather sequential writes | SQLite locks under concurrent write connections |

---

## Integration Points

1. **Jinja2 template rendering** (lines 920-945, 963-982) — calls `_format_article_title` which calls `_translate_title_sync`. Fix: pre-translate before render.
2. **`asyncio.gather`** at lines 710, 805 — gather points where sync DB writes occur. Fix: defer writes post-gather.
3. **`_translate_report_async`** at lines 1016-1022 — line-by-line translation loop. Fix: batch.

---

## Code References

- `update_article_llm`: `src/storage/sqlite/impl.py:952` — sync SQLite write, opens own connection
- `_translate_title_sync`: `src/application/report.py:436` — creates new event loop per call
- `_translate_report_async`: `src/application/report.py:1007` — O(n) line-by-line invoke
- `deduplicate_articles`: `src/application/dedup.py:207` — three-level dedup (exact hash, MinHash LSH, embedding cosine)
- `asyncio.gather` in v2: `src/application/report.py:805` — gather point for bounded_process

---

## Assumptions Log

| # | Claim | Confidence | Risk if Wrong |
|---|-------|------------|---------------|
| A1 | `update_article_llm` opens independent SQLite connection each call | HIGH (code inspection) | Low — confirmed at impl.py:975 |
| A2 | `loop.close()` is called in `_translate_title_sync` | HIGH (code inspection) | Low — confirmed at line 456 |
| A3 | No double deduplication within v2 pipeline | HIGH (code inspection) | Low — only one call at line 816 |
| A4 | Line-by-line translation is O(n) LLM calls | HIGH (code inspection) | Low — confirmed at lines 1016-1022 |

---

## Open Questions

1. **Issue #1 actual meaning:** The S6089 description "deduplicate_articles called twice causing data loss risk" — is this about v1 vs v2 inconsistency (v1 has no dedup), or is there a hidden second call somewhere? Recommend checking if `list_articles_for_llm` or the fetch pipeline already dedupes upstream.

2. **SQLite concurrency limit:** What is the actual SQLite `timeout` setting in `get_db()`? If it's 0 (fail immediately on lock), concurrent writes will fail fast. If it's 5s, writes will queue but could timeout.
