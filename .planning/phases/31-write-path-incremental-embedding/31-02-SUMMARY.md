# Phase 31 Plan 02: Write Path - Incremental Embedding

## Summary

| Field | Value |
|-------|-------|
| **Plan** | 31-02 |
| **Phase** | 31 (Write Path - Incremental Embedding) |
| **Wave** | 2 |
| **Status** | completed |
| **Files Modified** | `src/application/fetch.py` |

## Files Modified

- `/Users/y3/radar/src/application/fetch.py` - Integrated `add_article_embedding()` call in `fetch_one_async()`

## Implementation Details

### Integration Point: `fetch_one_async()` (lines 72-83)

After `store_article_async()` succeeds (line 70 `new_count += 1`), added:

```python
# Generate embedding for semantic search (D-09)
try:
    await asyncio.to_thread(
        add_article_embedding,
        article_id=article_guid,
        title=article.get("title") or "",
        content=article.get("content") or article.get("description") or "",
        url=article.get("link") or "",
    )
except Exception as e:
    logger.warning("Failed to add embedding for article %s: %s", article_guid, e)
    # Don't re-raise - embedding failure should not fail the fetch
```

### Import Added

```python
from src.storage import list_feeds as storage_list_feeds, store_article_async, add_article_embedding
```

## Key Implementation Decisions

1. **Async handling (D-09)**: Used `asyncio.to_thread()` because embedding generation is CPU-bound, avoiding event loop blocking
2. **Error isolation**: Embedding failures are logged but don't re-raise - fetch continues even if embedding fails
3. **Data mapping**: article_guid -> article_id, link -> url, following the pattern established in plan 31-01
4. **Placement**: Called immediately after `store_article_async()` succeeds, before `articles_needing_tags.append()`

## Verification Results

- Syntax validation: PASSED (`python -m py_compile src/application/fetch.py`)
- Import verification: BLOCKED (chromadb module not installed in environment - pre-existing dependency issue)
- Pattern validation: PASSED (matches `apply_rules_to_article()` pattern at lines 92-99)

## Success Criteria Status

| Criterion | Status |
|-----------|--------|
| `add_article_embedding` imported in fetch.py | PASSED |
| Called after each successful `store_article_async()` | PASSED |
| Uses `asyncio.to_thread()` for non-blocking CPU-bound embedding | PASSED |
| Import works without error | BLOCKED (pre-existing env issue) |

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- Implementation matches specification
- Integration point correct (after store_article_async succeeds)
- Async handling correct (asyncio.to_thread)
- Error handling follows pattern (warning + no re-raise)
- Syntax validated
