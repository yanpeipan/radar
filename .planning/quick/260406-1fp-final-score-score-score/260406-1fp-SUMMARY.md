---
phase: quick
plan: "01"
subsystem: application
tags:
  - refactor
  - dataclass
  - scoring
dependency_graph:
  requires: []
  provides: []
  affects:
    - src/application/articles.py
    - src/application/combine.py
    - src/cli/ui.py
    - src/storage/sqlite/impl.py
tech_stack:
  added: []
  patterns: []
  removed:
    - ArticleListItem.final_score field
    - ArticleListItem.score = 1.0 field
key_files:
  created: []
  modified:
    - src/application/articles.py
    - src/application/combine.py
    - src/cli/ui.py
    - src/storage/sqlite/impl.py
decisions: []
metrics:
  duration: ~
  completed: 2026-04-05
---

# Phase quick Plan 01: Merge final_score into score Summary

## One-liner

Refactored ArticleListItem dataclass to use a single `score` field instead of separate `score` and `final_score` fields.

## Changes Made

### src/application/articles.py
- Removed `score: float = 1.0` field (was always unused default)
- Changed `final_score: float = 0.0` to `score: float = 0.0`
- Updated docstrings: `final_score` -> `score` in 6 locations
- Updated inline comments about recomputing score after reranking

### src/application/combine.py
- Changed `c.final_score = ...` to `c.score = ...`
- Changed sort lambda from `x.final_score` to `x.score`
- Updated docstrings to reference `score` instead of `final_score`

### src/cli/ui.py
- Simplified `_serialize_article`: `"score": item.final_score if item.final_score > 0 else item.score` -> `"score": item.score`

### src/storage/sqlite/impl.py
- Changed `final_score=0.0` to `score=0.0` in `_compute_article_item` function

## Deviations from Plan

None - plan executed exactly as written.

## Verification

- `grep -r "final_score" src/` returns no matches
- `uv run pre-commit run --all` passes all checks

## Commits

- `9c1b6a0` refactor(articles): merge final_score into score field

## Self-Check: PASSED

- `src/application/articles.py` contains `score: float = 0.0`, no `final_score` references
- `src/application/combine.py` contains `c.score =`, no `final_score` references
- `src/cli/ui.py` contains `"score": item.score`, no `final_score` references
- Commit `9c1b6a0` verified in git history
