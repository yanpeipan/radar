# Phase 42: Storage Scoring Fixes - Context
**Gathered:** 2026-03-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 42 delivers two storage-layer fixes: (1) BM25 sigmoid normalization in `search_articles`, and (2) freshness field population in `list_articles`. Both are prerequisites for Phase 43 scoring infrastructure.

**Delivers:**
- `search_articles` uses sigmoid normalization for BM25: `1 / (1 + exp(bm25_raw * factor))`
- `list_articles` populates `freshness` via Newton's cooling law
- Missing scoring fields set to 0.0 in `list_articles`
- `bm25_factor` added to config.py

**Depends on:** Phase 41 (complete)
**Requirements:** SEARCH-03, SEARCH-04
**Success Criteria (from ROADMAP.md):**
1. list_articles populates freshness score (0-1, time decay from publication date)
2. Articles without vec_sim/bm25_score/ce_score have those fields set to 0.0
3. search_articles BM25 score uses sigmoid normalization: sigmoid_norm(bm25_raw, factor)
4. BM25 sigmoid factor is configurable via config.py (default 0.5)
</domain>

<decisions>
## Implementation Decisions

### BM25 Sigmoid Normalization (SEARCH-03)
- **D-13:** `search_articles` in `storage/sqlite/impl.py` uses sigmoid normalization: `sigmoid_norm(bm25_raw, factor) = 1 / (1 + exp(bm25_raw * factor))`
- **D-14:** `bm25_score` field on ArticleListItem populated by `search_articles` with 0-1 range
- **D-17:** BM25 factor comes from `config.py` (key: `bm25_factor`, default `0.5`)
- **D-18:** Replace current WRONG `abs()` approach: `score = 1 / (1 + abs(row["bm25_score"]))` → correct sigmoid

### Freshness Field Population (SEARCH-04)
- **D-15:** `list_articles` in `storage/sqlite/impl.py` populates `freshness` using Newton's cooling law: `exp(-days_ago / half_life_days)` with `half_life_days = 7`
- **D-16:** `vec_sim`, `bm25_score`, `ce_score` set to 0.0 when not applicable (list_articles has no semantic data)
- **D-19:** days_ago computed from pub_date via `_pub_date_to_timestamp()` → `datetime.fromtimestamp(pub_ts, tz=timezone.utc)` → `(now - pub_dt).days`
- **D-20:** `pub_date` in storage is INTEGER unix timestamp — use `_pub_date_to_timestamp()` consistently
- **D-21:** Freshness formula: `exp(-days_ago / 7)` — value 0-1, recent articles score near 1.0
- **D-22:** `source_weight` remains 0.3 default (per ArticleListItem field default; feed.weight not yet queried)
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v2.0 Architecture
- `docs/Search.md` — Complete technical design for Route A
  - §Sigmoid normalization: `1 / (1 + exp(bm25_raw * factor))`
  - §Newton's cooling law: `exp(-days_ago / half_life_days)` with half_life=7
  - §list_articles returns ArticleListItem with freshness field populated

### Requirements
- `.planning/REQUIREMENTS.md` — SEARCH-03, SEARCH-04 requirements for Phase 42

### State
- `.planning/STATE.md` §Accumulated Context — v2.0 decisions (Route A, ArticleListItem fields, Cross-Encoder lazy import, Newton's cooling law)
- `.planning/ROADMAP.md` §Phase 42 — success criteria and phase goal

### Codebase Scout Results
- `src/storage/sqlite/impl.py` §search_articles (line 660+) — current BM25 normalization is WRONG (uses `abs()`)
- `src/storage/sqlite/impl.py` §list_articles (line 478+) — returns ArticleListItem with no scoring fields
- `src/config.py` — bm25_factor not yet defined
- `src/storage/vector.py` §_pub_date_to_timestamp (lines 30-61) — timestamp conversion utility
</canonical_refs>

<beneft>
## Existing Code Insights

### Reusable Assets
- `_pub_date_to_timestamp()` in `vector.py:30-61`: handles ISO strings, RFC-2822, unix integers, unix strings
- `ArticleListItem` dataclass in `articles.py:20`: already has vec_sim, bm25_score, freshness, source_weight, ce_score, final_score fields (Phase 41)

### Established Patterns
- `datetime.fromtimestamp(pub_ts, tz=timezone.utc)` for timestamp → datetime conversion
- `exp(-days_ago / 7)` for freshness (half_life_days=7, Newton's cooling law)
- sigmoid normalization: `1 / (1 + exp(x * factor))`

### Integration Points
- Phase 43: `combine_scores` in `application/combine.py` will use all signal fields populated by Phase 42
- Phase 43: `rerank` in `application/rerank.py` will populate `ce_score` after Phase 42 scoring is ready
</benaft>

<specifics>
## Specific Ideas

**Code locations (confirmed during scout):**
- search_articles: `src/storage/sqlite/impl.py:660+`
- list_articles: `src/storage/sqlite/impl.py:478+`
- _pub_date_to_timestamp: `src/storage/vector.py:30-61`
- config.py: `src/config.py`

**BM25 sigmoid fix (D-18):**
Current WRONG code at impl.py:759:
```python
score=1 / (1 + abs(row["bm25_score"]))
```
Replace with:
```python
from src.config import bm25_factor
score=1 / (1 + math.exp(row["bm25_score"] * bm25_factor))
```
Need to `import math` if not already present.

**Freshness computation (D-21):**
```python
pub_ts = _pub_date_to_timestamp(r.get("pub_date"))
freshness = 0.0
if pub_ts:
    pub_dt = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
    days_ago = (datetime.now(timezone.utc) - pub_dt).days
    freshness = math.exp(-days_ago / 7)
```
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 42 scope.

</deferred>

---
*Phase: 42-storage-scoring-fixes*
*Context gathered: 2026-03-28*
