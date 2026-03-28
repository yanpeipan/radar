---
phase: 41-articlelistitem-semantic-search-core
plan: "41-01"
subsystem: search
tags: [semantic-search, chromadb, scoring, article-list]

# Dependency graph
requires:
  - phase: 40-comprehensive-uvloop-audit
    provides: Clean asyncio boundaries, uvloop at CLI only
provides:
  - ArticleListItem with 6 scoring fields (vec_sim, bm25_score, freshness, source_weight, ce_score, final_score)
  - search_articles_semantic returns raw cos_sim without weighted formula
  - P0 crash fix for INTEGER pub_date timestamps
affects: [42-storage-scoring-fixes, 43-scoring-infrastructure, 44-cli-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: [Route A scoring - raw signals at storage layer]

key-files:
  created: []
  modified:
    - src/application/articles.py (ArticleListItem dataclass)
    - src/storage/vector.py (search_articles_semantic function)

key-decisions:
  - "vec_sim=0.0, bm25_score=0.0, freshness=0.0, source_weight=0.3, ce_score=0.0, final_score=0.0 defaults per D-01"
  - "score field retained for backward compatibility, final_score is canonical sort field per D-02"
  - "Return raw cos_sim as vec_sim, not combined score per D-04"
  - "cos_sim = 1 - distance / 2 (hnsw:space=cosine) per D-06"
  - "Freshness/source_weight signals removed from storage layer per D-07"

patterns-established:
  - "Route A: storage returns raw signals, combine_scores() unifies at application layer"

requirements-completed: [SEARCH-00, SEARCH-01, SEARCH-02]

# Metrics
duration: ~3 min
completed: 2026-03-28
---

# Phase 41 Plan 01: ArticleListItem & Semantic Search Core Summary

**Extended ArticleListItem with 6 scoring fields; fixed search_articles_semantic P0 crash on INTEGER pub_date; returns raw cos_sim without weighted formula**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-28T11:01:23Z
- **Completed:** 2026-03-28T11:04:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- ArticleListItem dataclass extended with vec_sim, bm25_score, freshness, source_weight, ce_score, final_score fields
- source_weight defaults to 0.3 (per locked decision D-01), all others default to 0.0
- Original score field retained for backward compatibility
- search_articles_semantic P0 crash fixed - INTEGER unix timestamps no longer cause datetime.fromisoformat() to fail
- Removed hardcoded weighted scoring formula (0.5*cos_sim + 0.2*freshness + 0.3*source_weight)
- ChromaDB results now returned with raw cos_sim as vec_sim

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend ArticleListItem with 6 scoring fields (SEARCH-01)** - `832ed20` (feat)
2. **Task 2: Fix pub_date crash and return raw cos_sim (SEARCH-00, SEARCH-02)** - `3f1c2ea` (fix)

## Files Created/Modified
- `src/application/articles.py` - ArticleListItem dataclass with 6 new scoring fields
- `src/storage/vector.py` - search_articles_semantic fixed to use _pub_date_to_timestamp(), returns raw cos_sim

## Decisions Made
- vec_sim=0.0, bm25_score=0.0, freshness=0.0, source_weight=0.3, ce_score=0.0, final_score=0.0 defaults per D-01
- score field retained for backward compatibility; final_score is canonical sort field per D-02
- Return raw cos_sim as vec_sim, not combined score per D-04
- cos_sim = 1 - distance / 2 (hnsw:space=cosine) per D-06
- Freshness/source_weight signals removed from storage layer per D-07

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## Next Phase Readiness
- Phase 42 (Storage Scoring Fixes) can proceed
- SEARCH-00, SEARCH-01, SEARCH-02 requirements completed
- ArticleListItem with scoring fields ready for combine_scores() in Phase 43

---
*Phase: 41-articlelistitem-semantic-search-core*
*Completed: 2026-03-28*
