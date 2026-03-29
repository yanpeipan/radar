# Phase 41: ArticleListItem & Semantic Search Core - Research

**Researched:** 2026-03-28
**Domain:** Python dataclass extension, ChromaDB semantic search, timestamp handling
**Confidence:** HIGH

## Summary

Phase 41 extends `ArticleListItem` with 6 scoring fields and fixes a P0 crash in `search_articles_semantic` when `pub_date` is an INTEGER unix timestamp. The phase also removes a hardcoded weighted scoring formula, returning raw cosine similarity instead. All decisions are locked in CONTEXT.md -- no alternatives need research.

**Primary recommendation:** Add 6 fields to `ArticleListItem` dataclass; replace `datetime.fromisoformat()` call at vector.py:363 with `_pub_date_to_timestamp()`; remove lines 376-377 hardcoded formula.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01 through D-12** are fully locked -- implementation must follow exactly:

- **D-01:** Add 6 fields to `ArticleListItem`: `vec_sim: float = 0.0`, `bm25_score: float = 0.0`, `freshness: float = 0.0`, `source_weight: float = 0.3`, `ce_score: float = 0.0`, `final_score: float = 0.0`
- **D-02:** Keep `score` field for backward compatibility; `final_score` becomes canonical sort field
- **D-03:** All new fields default to `0.0` except `source_weight` which defaults to `0.3`
- **D-04:** `search_articles_semantic` returns raw `cos_sim` from ChromaDB directly as `vec_sim`
- **D-05:** Remove hardcoded weighted formula at lines 376-377
- **D-06:** ChromaDB returns cosine distance; convert to similarity: `cos_sim = 1 - distance / 2`
- **D-07:** Freshness and source_weight signals removed from storage layer
- **D-08:** Fix line 363 crash: `datetime.fromisoformat(pub_date.replace(...))` fails on INTEGER
- **D-09:** Use `_pub_date_to_timestamp(pub_date)` for ALL timestamp conversions
- **D-10:** After getting unix timestamp, compute `days_ago = (now - pub_dt).days` where `pub_dt = datetime.fromtimestamp(pub_date_ts, tz=timezone.utc)`
- **D-11:** `_pub_date_to_timestamp` handles ISO strings, RFC-2822, unix integers, unix strings
- **D-12:** Freshness computation at lines 365-377 is for ChromaDB metadata filtering, NOT ArticleListItem.freshness

### Deferred Ideas (OUT OF SCOPE)

None -- discussion stayed within Phase 41 scope.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEARCH-00 | Fix `search_articles_semantic` line 363 crash when pub_date is INTEGER unix timestamp | `_pub_date_to_timestamp()` utility at vector.py:30-61 already handles all formats; replace inline `datetime.fromisoformat()` call |
| SEARCH-01 | `ArticleListItem` extended with 6 fields: vec_sim, bm25_score, freshness, source_weight, ce_score, final_score | Dataclass at articles.py:20; add fields with defaults per D-01/D-02/D-03 |
| SEARCH-02 | `search_articles_semantic` returns raw cos_sim without weighted combination | Remove lines 376-377 hardcoded formula; `vec_sim` field carries raw ChromaDB cosine similarity |

## Standard Stack

No new dependencies required. All required functionality uses existing libraries.

| Library | Version | Purpose |
|---------|---------|---------|
| Python dataclasses | built-in | `ArticleListItem` dataclass extension |
| chromadb | existing | ChromaDB client; cosine distance via `hnsw:space=cosine` |
| datetime | built-in | Timestamp conversion for freshness computation |
| email.utils | built-in | RFC-2822 date parsing via `parsedate_to_datetime` |

## Architecture Patterns

### Dataclass Field Extension Pattern

```python
# Current (articles.py:20)
@dataclass
class ArticleListItem:
    id: str
    feed_id: str
    # ... existing fields ...
    score: float = 1.0

# Target -- add 6 new fields before score (or after, with defaults)
@dataclass
class ArticleListItem:
    id: str
    feed_id: str
    feed_name: str
    title: Optional[str]
    link: Optional[str]
    guid: str
    pub_date: Optional[str]
    description: Optional[str]
    # NEW fields
    vec_sim: float = 0.0
    bm25_score: float = 0.0
    freshness: float = 0.0
    source_weight: float = 0.3
    ce_score: float = 0.0
    final_score: float = 0.0
    # Backward compat
    score: float = 1.0
```

### Cosine Distance to Similarity Conversion

ChromaDB with `hnsw:space=cosine` returns **cosine distance** (0-2 range where 0 = identical). Convert to similarity:

```python
# vector.py:356 (current)
cos_sim = max(0.0, 1.0 - distance / 2.0) if distance is not None else 0.5
```

This formula is correct and should be retained, but the result should be assigned to `vec_sim` field, NOT to a combined `score`.

### pub_date Timestamp Conversion

The existing utility handles all formats:

```python
# vector.py:30-61
def _pub_date_to_timestamp(pub_date: str | None) -> int | None:
    # Handles: RFC 2822, ISO format (with/without Z), unix integers, unix strings
    # Returns: unix timestamp (int) or None
```

**The P0 crash (line 363):** `datetime.fromisoformat(pub_date.replace("Z", "+00:00"))` is called on `pub_date` from SQLite, which may be an **INTEGER unix timestamp** (not a string). `datetime.fromisoformat()` only accepts strings.

**Fix approach:** After fetching article from SQLite, convert `pub_date` to timestamp using `_pub_date_to_timestamp()`. Then compute `days_ago` using `datetime.fromtimestamp(pub_date_ts, tz=timezone.utc)` -- which accepts an integer.

### Hardcoded Formula Removal

**Current (lines 376-377):**
```python
score = 0.5 * cos_sim + 0.2 * freshness + 0.3 * source_weight
```

**Target:** Remove this formula. `vec_sim` field carries raw cos_sim. `freshness`, `source_weight`, and `final_score` are computed at application layer by `combine_scores()` (Phase 43).

### ChromaDB Metadata Filtering

The freshness computation at lines 365-377 in vector.py serves **ChromaDB's metadata filter** (where clause, lines 283-297) which requires integer unix timestamps for `$gte/$lte` comparisons. This is separate from the `ArticleListItem.freshness` field.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Timestamp parsing | Inline if/except for each format | `_pub_date_to_timestamp()` | Handles RFC-2822, ISO, unix int, unix string -- already exists |
| Cosine distance conversion | Custom formula | `1 - distance / 2` | Standard formula for hnsw:space=cosine; already correct |
| Combined scoring | Hardcoded weighted sum | `combine_scores()` in Phase 43 | Separation of concerns; storage returns raw signals |

## Common Pitfalls

### Pitfall 1: Confusing metadata filter freshness with ArticleListItem.freshness
**What goes wrong:** Developer might try to fill `ArticleListItem.freshness` in the storage layer during ChromaDB query.
**Why it happens:** Lines 365-377 compute a freshness-like value for ChromaDB filtering. Phase 41 only fixes the P0 crash; it does NOT populate `ArticleListItem.freshness`.
**How to avoid:** `ArticleListItem.freshness` is populated by `combine_scores()` in Phase 43. Phase 41 only fixes the crash and removes the hardcoded formula.

### Pitfall 2: Using wrong ArticleListItem.score vs final_score
**What goes wrong:** Code sorts by `score` when it should sort by `final_score`.
**Why it happens:** Both fields exist; `score` is for backward compatibility.
**How to avoid:** Phase 41 does not change sorting behavior -- Phase 43 `combine_scores()` populates `final_score`. Phase 44 CLI integration will use `final_score` for sorting.

### Pitfall 3: Forgetting that pub_date in SQLite is INTEGER unix timestamp
**What goes wrong:** `datetime.fromisoformat()` fails on integer.
**Why it happens:** pub_date was migrated to INTEGER storage in prior phase.
**How to avoid:** Always use `_pub_date_to_timestamp()` when converting pub_date from SQLite.

## Code Examples

### Fix for P0 Crash (line 363)

```python
# BEFORE (crashes on INTEGER pub_date):
pub_date = article_info.get("pub_date")
freshness = 0.0
if pub_date:
    try:
        pub_dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))  # FAILS
        ...

# AFTER (uses _pub_date_to_timestamp):
pub_date = article_info.get("pub_date")
pub_ts = _pub_date_to_timestamp(pub_date)  # Returns int or None
freshness = 0.0
if pub_ts:
    pub_dt = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
    days_ago = (datetime.now(timezone.utc) - pub_dt).days
    freshness = max(0.0, 1.0 - days_ago / 30)
```

### ArticleListItem Extension

```python
# src/application/articles.py:19-42
@dataclass
class ArticleListItem:
    id: str
    feed_id: str
    feed_name: str
    title: Optional[str]
    link: Optional[str]
    guid: str
    pub_date: Optional[str]
    description: Optional[str]
    # v2.0 scoring fields
    vec_sim: float = 0.0
    bm25_score: float = 0.0
    freshness: float = 0.0
    source_weight: float = 0.3
    ce_score: float = 0.0
    final_score: float = 0.0
    # Backward compatibility
    score: float = 1.0
```

### Return Raw cos_sim in search_articles_semantic

```python
# In vector.py search_articles_semantic(), around lines 396-408:
# BEFORE:
result_items.append(ArticleListItem(
    ...
    score=r.get("score", 1.0),  # Was combined score
))

# AFTER:
cos_sim = max(0.0, 1.0 - distance / 2.0) if distance is not None else 0.5
result_items.append(ArticleListItem(
    id=r["sqlite_id"] or r["article_id"] or "",
    feed_id=r["feed_id"] or "",
    feed_name=r["feed_name"] or "",
    title=r.get("title"),
    link=r.get("url"),
    guid=r["sqlite_id"] or r["article_id"] or "",
    pub_date=r.get("pub_date"),
    description=None,
    vec_sim=cos_sim,  # Raw cosine similarity
    # Other fields default to 0.0 or 0.3 per D-01/D-03
))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single `score` field | 6-field signal decomposition | Phase 41 (this phase) | Enables Route A scoring architecture |
| Hardcoded `0.5*cos+0.2*fresh+0.3*weight` | Raw cos_sim returned | Phase 41 (this phase) | combine_scores in Phase 43 handles combination |
| `datetime.fromisoformat()` on INTEGER | `_pub_date_to_timestamp()` for all | Phase 41 (this phase) | Fixes P0 crash on unix timestamp pub_date |

**Deprecated/outdated:**
- Hardcoded weighted scoring formula (lines 376-377) -- removed in Phase 41
- Combined `score` as primary sort -- `final_score` becomes primary in Phase 44

## Open Questions

None -- all implementation decisions are locked in CONTEXT.md.

## Environment Availability

Step 2.6: SKIPPED (no external dependencies -- code/config-only changes)

## Sources

### Primary (HIGH confidence)
- `src/application/articles.py` -- ArticleListItem dataclass definition (line 20)
- `src/storage/vector.py` -- search_articles_semantic (line 265+), _pub_date_to_timestamp (line 30-61)
- `.planning/REQUIREMENTS.md` -- SEARCH-00, SEARCH-01, SEARCH-02 requirements
- `.planning/ROADMAP.md` -- Phase 41 success criteria
- `docs/Search.md` -- v2.0 architecture specification (Route A)

### Secondary (MEDIUM confidence)
- `.planning/STATE.md` -- v2.0 accumulated context

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, existing codebase patterns
- Architecture: HIGH -- all decisions locked in CONTEXT.md
- Pitfalls: HIGH -- known crash scenario documented with fix approach

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (30 days -- stable phase with locked decisions)
