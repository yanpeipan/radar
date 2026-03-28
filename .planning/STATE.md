---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Search Ranking Architecture
status: planning
stopped_at: Milestone v2.0 roadmap created
last_updated: "2026-03-28"
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (v2.0 Search Ranking Architecture)

**Core value:** 用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。
**Current focus:** Phase 41 — ArticleListItem & Semantic Search Core

| Phase | Goal | Requirements | Status |
|-------|------|--------------|--------|
| 40. Comprehensive uvloop Audit | Zero asyncio.run(), uvloop at CLI boundaries | UVLOOP-AUDIT-01, 02, 03 | ✅ Complete |
| 41. ArticleListItem & Semantic Search Core | ArticleListItem with scoring fields; raw cos_sim | SEARCH-00, SEARCH-01, SEARCH-02 | 📋 Planned |
| 42. Storage Scoring Fixes | BM25 sigmoid; list_articles freshness | SEARCH-03, SEARCH-04 | 📋 Planned |
| 43. Scoring Infrastructure | Cross-Encoder rerank; combine_scores | SEARCH-05, SEARCH-06 | 📋 Planned |
| 44. CLI Integration | Search command wired with weight config | SEARCH-07 | 📋 Planned |

## Performance Metrics

**v1.0 velocity:**
- 3 phases, 9 plans, ~3 hours

**v1.1 velocity:**
- 4 phases, 10 plans, ~1 day

**v1.2 velocity:**
- 4 phases, 5 plans, ~1 day

**v1.4 velocity:**
- 3 phases (16, 17, 18), 4 plans, ~20 min

**v1.5 velocity:**
- 4 phases, 4 plans

**v1.7 velocity:**
- 4 phases, 4 plans (shipped 2026-03-25)

**v1.8 velocity:**
- 4 phases, 5 plans (ChromaDB semantic search shipped 2026-03-27)

**v1.9 velocity:**
- 4 phases, 9 requirements (shipped 2026-03-27)

**v1.10-v1.11 velocity:**
- 2 phases, 2 plans (shipped 2026-03-28)

**v2.0 planned:**
- 4 phases, 8 requirements

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.

- [Phase 40]: uvloop.run() at CLI boundaries only; no asyncio.run() in src/
- [Phase 40]: asyncio.to_thread() for all blocking I/O
- [v2.0]: Route A — search methods return raw signals, combine_scores() unifies at application layer
- [v2.0]: ArticleListItem extended with vec_sim, bm25_score, freshness, source_weight, ce_score, final_score
- [v2.0]: Cross-Encoder uses BAAI/bge-reranker-base with lazy import
- [v2.0]: Newton's cooling law for freshness (half_life_days=7)

### Technical Notes

**v1.8 ChromaDB Semantic Search Architecture:**
- ChromaDB PersistentClient with local directory storage
- sentence-transformers all-MiniLM-L6-v2 model (384-dim embeddings)
- ChromaDB collection: "articles" with id, content, title, url metadata
- Semantic search via ChromaDB query() with cosine similarity

**v2.0 Search Ranking Architecture:**
- Route A: vector_search + FTS5 + list all return raw signals
- combine_scores(alpha, beta, gamma, delta) at application layer
- Optional Cross-Encoder reranking via BAAI/bge-reranker-base
- BM25 uses sigmoid normalization (factor from config.py, default 0.5)

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-03-28
Stopped at: v2.0 roadmap created — Phase 41 ready to plan

## Quick Tasks Completed

None in this session yet.
