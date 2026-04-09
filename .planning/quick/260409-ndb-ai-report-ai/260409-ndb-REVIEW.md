---
phase: quick
reviewed: 2026-04-09T00:00:00Z
depth: quick
files_reviewed: 2
files_reviewed_list:
  - src/application/report.py
  - src/llm/core.py
findings:
  critical: 2
  warning: 2
  info: 2
  total: 6
status: issues_found
---

# Phase Quick: Code Review Report

**Reviewed:** 2026-04-09
**Depth:** quick
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Two critical issues found related to LLM failure handling and MiniMax `choices: None` error. The report pipeline has good concurrency controls (semaphore-based) but is undermined by overly restrictive `Semaphore(1)` limits and sequential LLM calls in loops.

---

## Critical Issues

### CR-01: Unguarded access to `response["choices"][0]` — MiniMax `choices: None` crash

**File:** `src/llm/core.py:308`
**Issue:** Direct array access on `response["choices"]` without null check. When MiniMax overloads, it returns `{"choices": null}` which causes `TypeError: 'NoneType' object is not subscriptable` at `response["choices"][0]`.

```python
# Line 304-308
response = await asyncio.wait_for(
    acompletion(**kwargs),
    timeout=self.config.timeout_seconds,
)
return response["choices"][0]["message"]["content"]  # CRASH if choices is None
```

**Fix:** Add validation before access:
```python
response = await asyncio.wait_for(...)
if not response.get("choices") or not response["choices"]:
    raise LLMError(f"Provider {provider} returned empty choices: {response}")
return response["choices"][0]["message"]["content"]
```

---

### CR-02: Key LLM functions lack retry mechanism — unlike `generate_cluster_summary`

**File:** `src/application/report.py:529-550`, `553-592`
**Issue:** `classify_article_layer` and `classify_cluster_layer` have NO retry logic. Compare with `generate_cluster_summary` (lines 617-652) which has proper exponential backoff retry (2s, 4s, 8s). When MiniMax overloads and returns `choices: None`, these functions catch the generic exception and silently return "AI应用" fallback — masking real errors.

- Line 548-550: `classify_article_layer` catches Exception and returns default
- Line 590-592: `classify_cluster_layer` catches Exception and returns default

**Fix:** Add retry with exponential backoff (same pattern as `generate_cluster_summary`):
```python
delays = [2, 4, 8]
for attempt, delay in enumerate(delays):
    try:
        chain = get_classify_chain()
        result = await chain.ainvoke(...)
        # ... validation ...
        return cat
    except Exception as e:
        if attempt < len(delays) - 1:
            logger.warning("Classify attempt %d failed: %s. Retrying...", attempt + 1, e)
            await asyncio.sleep(delay)
        else:
            raise
```

---

## Warnings

### WR-01: `Semaphore(1)` overrides `max_concurrency=5` — async pipeline serialized

**File:** `src/application/report.py:745`, `842`, `494`
**Issue:** `max_concurrency` is configured as 5 in `LLMConfig.from_settings()` (line 104), but the report pipeline uses hardcoded `asyncio.Semaphore(1)` which forces sequential execution. This defeats the purpose of the concurrency control.

- Line 745: `_cluster_articles_async` — `semaphore = asyncio.Semaphore(1)`
- Line 842: `_cluster_articles_v2_async` — `semaphore = asyncio.Semaphore(1)`
- Line 494: `_translate_titles_batch_async` — `semaphore = asyncio.Semaphore(1)` (comment says "max 2 concurrent")

```python
# Line 745-749
semaphore = asyncio.Semaphore(1)  # Overrides config.max_concurrency=5

async def bounded_process(a: dict) -> tuple[str, dict]:
    async with semaphore:  # Only 1 at a time
        return await process_one(a)
```

**Fix:** Use `config.max_concurrency` instead of hardcoded 1:
```python
from src.application.config import _get_settings
settings = _get_settings()
llm_config = LLMConfig.from_settings()
semaphore = asyncio.Semaphore(llm_config.max_concurrency)
```

---

### WR-02: Sequential LLM calls in loops — O(n) awaits instead of batching

**File:** `src/application/report.py:870-871`
**Issue:** `classify_cluster_layer` is called sequentially inside a loop, making N LLM calls for N topics. No parallelization.

```python
# Line 870-871
for topic in all_topics:
    topic["layer"] = await classify_cluster_layer(topic["sources"], target_lang)
```

**Fix:** Batch all cluster texts into a single LLM call or use `asyncio.gather` for parallel execution:
```python
async def classify_one(topic: dict) -> tuple[int, str]:
    layer = await classify_cluster_layer(topic["sources"], target_lang)
    return (all_topics.index(topic), layer)

layers = await asyncio.gather(*[classify_one(t) for t in all_topics])
for idx, layer in layers:
    all_topics[idx]["layer"] = layer
```

---

## Info

### IN-01: `batch_complete` silently returns exceptions in result list

**File:** `src/llm/core.py:330`
**Issue:** `return_exceptions=True` means failed prompts return an Exception object instead of raising. Caller cannot distinguish success from failure without checking `isinstance(result, Exception)`.

```python
return await asyncio.gather(*tasks, return_exceptions=True)  # type: ignore[return-value]
```

**Fix:** Document this behavior clearly or filter out exceptions with a warning log.

---

### IN-02: `_translate_title_sync` blocks event loop on cache miss

**File:** `src/application/report.py:475-477`
**Issue:** On cache miss, `_translate_title_sync` calls `loop.run_until_complete()` which blocks the running event loop. If called from within an async context (e.g., a template filter during render), this can deadlock.

```python
loop = asyncio.get_event_loop()
translated = loop.run_until_complete(
    get_translate_chain().ainvoke({"text": title, "target_lang": target_lang})
)
```

**Fix:** Raise an error on cache miss instead of blocking, forcing callers to use the async pre-translation path:
```python
raise RuntimeError(
    f"Title translation cache miss for '{title[:50]}'. "
    "Use _translate_titles_batch_async() before rendering."
)
```

---

_Reviewed: 2026-04-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick_
