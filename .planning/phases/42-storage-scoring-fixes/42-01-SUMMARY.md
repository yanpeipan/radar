---
phase: 42-storage-scoring-fixes
plan: "01"
subsystem: database
tags: [bm25, sigmoid-normalization, freshness, newton-cooling, sqlite]

# Dependency graph
requires:
  - phase: "41-articlelistitem-semantic-search-core"
    provides: ArticleListItem dataclass with vec_sim, bm25_score, freshness, source_weight, ce_score, final_score fields
provides:
  - BM25 sigmoid normalization via 1 / (1 + exp(bm25 * factor)) in search_articles
  - Freshness population via Newton's cooling law in list_articles
  - _pub_date_to_timestamp handles INTEGER inputs from SQLite
  - get_bm25_factor() configurable via config.yaml (default 0.5)
affects: [43-scoring-infrastructure, 44-cli-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Sigmoid normalization for BM25 scores: 1 / (1 + exp(x * factor))
    - Newton's cooling law for freshness: exp(-days_ago / 7)
    - Helper function pattern for computing ArticleListItem fields

key-files:
  created: []
  modified:
    - src/application/config.py - added get_bm25_factor()
    - config.yaml - added bm25_factor: 0.5
    - src/storage/sqlite/impl.py - sigmoid BM25 in search_articles, freshness in list_articles
    - src/storage/vector.py - _pub_date_to_timestamp handles int inputs

key-decisions:
  - "BM25 sigmoid factor from config.py (key: bm25_factor, default 0.5)"
  - "Freshness half_life_days = 7 per Newton's cooling law"
  - "list_articles sets vec_sim=0.0, bm25_score=0.0, ce_score=0.0 since no semantic data"
  - "Helper function _compute_article_item inline in list_articles for freshness computation"

patterns-established:
  - "Sigmoid normalization for converting raw BM25 scores to 0-1 range"
  - "Freshness via time decay: exp(-days_ago / half_life_days)"

requirements-completed: [SEARCH-03, SEARCH-04]

# Metrics
duration: 8min
completed: 2026-03-28
---

# Phase 42: Storage Scoring Fixes Summary

**BM25 sigmoid normalization and freshness scoring populated in storage layer, enabling Phase 43 combine_scores application layer**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-28T11:27:22Z
- **Completed:** 2026-03-28T11:35:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- search_articles now uses sigmoid normalization: 1 / (1 + exp(bm25 * factor)) instead of abs()
- ArticleListItem.bm25_score field populated via sigmoid in search_articles
- list_articles computes freshness via Newton's cooling law: exp(-days_ago / 7)
- list_articles sets vec_sim=0.0, bm25_score=0.0, ce_score=0.0 (no semantic data in list mode)
- _pub_date_to_timestamp handles INTEGER unix timestamps from SQLite
- get_bm25_factor() added to config.py with config.yaml setting bm25_factor: 0.5

## Task Commits

Each task was committed atomically:

1. **Task 1: BM25 Sigmoid Normalization (SEARCH-03)** - `c256e85` (feat)
2. **Task 2: Freshness Population (SEARCH-04)** - `c256e85` (feat, same commit as both tasks were in one atomic commit)

**Plan metadata:** no separate plan commit (plan already existed)

## Files Created/Modified
- `src/application/config.py` - Added get_bm25_factor() function
- `config.yaml` - Added bm25_factor: 0.5
- `src/storage/sqlite/impl.py` - Sigmoid BM25 in search_articles, freshness computation in list_articles
- `src/storage/vector.py` - _pub_date_to_timestamp now handles int inputs

## Decisions Made
- Used helper function _compute_article_item inside list_articles for clean freshness computation
- Kept score field unchanged (dataclass default 1.0) for backward compatibility
- factor = 0.5 default for BM25 sigmoid (per D-17)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 43 (Scoring Infrastructure) can now use bm25_score and freshness fields populated by this phase
- combine_scores in application layer will combine signals from search_articles and list_articles

---
*Phase: 42-storage-scoring-fixes*
*Completed: 2026-03-28*
