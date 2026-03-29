# Phase 41: ArticleListItem & Semantic Search Core - Context

**Gathered:** 2026-03-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 41 delivers the core ArticleListItem dataclass with extended scoring fields and fixes the P0 crash in `search_articles_semantic`. This is the foundation for all subsequent v2.0 scoring work (Phases 42-44).

**Delivers:**
- `ArticleListItem` extended with 6 new fields: `vec_sim`, `bm25_score`, `freshness`, `source_weight`, `ce_score`, `final_score`
- `search_articles_semantic` returns raw `cos_sim` (no weighted combination)
- `search_articles_semantic` no longer crashes when `pub_date` is INTEGER unix timestamp
- `score` field retained for backward compatibility; `final_score` becomes the canonical sort field

**Depends on:** Phase 40 (complete)
**Requirements:** SEARCH-00, SEARCH-01, SEARCH-02
**Success Criteria (from ROADMAP.md):**
1. ArticleListItem has vec_sim, bm25_score, freshness, source_weight, ce_score, final_score fields
2. search_articles_semantic returns ArticleListItem with vec_sim set to raw cosine similarity from ChromaDB
3. search_articles_semantic no longer crashes when pub_date is INTEGER unix timestamp
4. search_articles_semantic score is NOT a weighted combination (returns raw cos_sim directly)

</domain>

<decisions>
## Implementation Decisions

### ArticleListItem Field Extension (SEARCH-01)
- **D-01:** Add 6 fields to `ArticleListItem` dataclass in `src/application/articles.py`:
  - `vec_sim: float = 0.0` — ChromaDB cosine similarity (0-1)
  - `bm25_score: float = 0.0` — FTS5 BM25 normalized score (0-1)
  - `freshness: float = 0.0` — Time decay score (0-1, Newton's cooling law, filled by combine_scores)
  - `source_weight: float = 0.3` — Feed source weight (from feed.weight)
  - `ce_score: float = 0.0` — Cross-Encoder score (0-1, filled after rerank)
  - `final_score: float = 0.0` — Combined score from combine_scores
- **D-02:** Keep existing `score` field for backward compatibility; `final_score` becomes canonical sort field
- **D-03:** Fields default to `0.0` except `source_weight` which defaults to `0.3` (per existing feed.weight default)

### Raw Cosine Similarity Return (SEARCH-02)
- **D-04:** `search_articles_semantic` returns raw `cos_sim` from ChromaDB directly as `vec_sim`
- **D-05:** Remove hardcoded weighted formula at lines 376-377: `score = 0.5 * cos_sim + 0.2 * freshness + 0.3 * source_weight`
- **D-06:** ChromaDB returns cosine distance; convert to similarity: `cos_sim = 1 - distance / 2` (hnsw:space=cosine)
- **D-07:** Freshness and source_weight signals removed from storage layer — these are computed at application layer by `combine_scores`

### pub_date Crash Fix (SEARCH-00)
- **D-08:** Fix line 363 crash: `datetime.fromisoformat(pub_date.replace("Z", "+00:00"))` fails when pub_date is INTEGER
- **D-09:** Use `_pub_date_to_timestamp(pub_date)` for ALL timestamp conversions (already exists at lines 30-61 in vector.py)
- **D-10:** After getting unix timestamp, compute days_ago: `days_ago = (now - pub_dt).days` where `pub_dt = datetime.fromtimestamp(pub_date_ts, tz=timezone.utc)`

### Timestamp Conversion (related)
- **D-11:** `_pub_date_to_timestamp` function already handles: ISO strings (with/without Z suffix), RFC-2822 strings, unix timestamp integers, unix timestamp strings — use it consistently
- **D-12:** The freshness computation at lines 365-377 is for ChromaDB metadata filtering (where/integer comparison), NOT for the ArticleListItem.freshness field (that gets computed in combine_scores)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v2.0 Architecture
- `docs/Search.md` — Complete technical design for Route A unified search ranking
  - §Target: ArticleListItem with 6 signal fields
  - §Sigmoid normalization: `1 / (1 + exp(bm25_raw * factor))`
  - §Newton's cooling law: `exp(-days_ago / half_life_days)` with half_life=7
  - §combine_scores weights: alpha=0.3, beta=0.3, gamma=0.2, delta=0.2
  - §Search type weight matrix: semantic (gamma=0.2, delta=0.0), keyword (gamma=0.0, delta=0.2)

### Requirements
- `.planning/REQUIREMENTS.md` — SEARCH-00, SEARCH-01, SEARCH-02 requirements for Phase 41

### State
- `.planning/STATE.md` §Accumulated Context — v2.0 decisions (Route A, ArticleListItem fields, Cross-Encoder lazy import, Newton's cooling law)
- `.planning/ROADMAP.md` §Phase 41 — success criteria and phase goal

### Codebase Scout Results
- `src/application/articles.py` §ArticleListItem (line 20) — existing dataclass definition
- `src/storage/vector.py` §_pub_date_to_timestamp (lines 30-61) — timestamp conversion utility
- `src/storage/vector.py` §search_articles_semantic (line 265+) — semantic search implementation
  - P0 crash at line 363: `datetime.fromisoformat(pub_date.replace(...))` on INTEGER
  - Hardcoded formula at lines 376-377: `0.5 * cos + 0.2 * fresh + 0.3 * weight`
- `src/storage/sqlite/impl.py` §list_articles — freshness field needed here (Phase 42)

### Config
- `src/config.py` — bm25_factor default 0.5 (used for sigmoid normalization)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_pub_date_to_timestamp()` in `vector.py:30-61`: Already handles ISO strings, RFC-2822, unix integers, unix strings — use this instead of inline datetime.fromisoformat
- `ArticleListItem` dataclass in `articles.py:20`: Extend here with 6 new fields

### Established Patterns
- Dataclass with Optional fields and defaults: follows existing ArticleListItem pattern
- Unix timestamp storage (INTEGER): pub_date stored as INTEGER unix timestamp per prior migration
- Lazy import pattern: used for Cross-Encoder in Phase 43

### Integration Points
- Phase 42: `list_articles` in `storage/sqlite/impl.py` needs to populate `freshness` field
- Phase 42: `search_articles` in `storage/sqlite/impl.py` needs to populate `bm25_score` with sigmoid normalization
- Phase 43: `combine_scores` in `application/combine.py` will use all signal fields
- Phase 43: `rerank` in `application/rerank.py` will populate `ce_score`

</code_context>

<specifics>
## Specific Ideas

No specific implementation examples requested — standard approaches acceptable.

**Code locations (confirmed during scout):**
- ArticleListItem: `src/application/articles.py:20`
- search_articles_semantic: `src/storage/vector.py:265`
- _pub_date_to_timestamp: `src/storage/vector.py:30-61`

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 41 scope.

### Reviewed Todos (not folded)
None — no cross-reference todos reviewed in this session.

</deferred>

---

*Phase: 41-articlelistitem-semantic-search-core*
*Context gathered: 2026-03-28*
