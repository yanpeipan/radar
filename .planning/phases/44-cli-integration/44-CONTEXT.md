# Phase 44: CLI Integration - Context

**Gathered:** 2026-03-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 44 delivers SEARCH-07: CLI `article search` command wired with Phase 43 scoring infrastructure. The search command must support two modes (semantic with `--semantic` flag, default FTS5) and pass appropriate weight configurations to `combine_scores()`.

**Delivers:**
- `src/cli/article.py` — `article search` command with `--semantic` flag
- Weight configuration passed to `combine_scores()` per search type
- Optional Cross-Encoder reranking (SEARCH-05)

**Depends on:** Phase 43 (rerank.py, combine.py must exist)
**Requirements:** SEARCH-07
</domain>

<decisions>
## Implementation Decisions

### SEARCH-07 Weight Configuration
- **D-01:** Semantic search (`--semantic`): `vector_search → optional rerank → combine_scores(alpha=0.3, beta=0.3, gamma=0.2, delta=0.0)`
- **D-02:** Default FTS5 search: `search_articles → optional rerank → combine_scores(alpha=0.3, beta=0.3, gamma=0.0, delta=0.2)`
- **D-03:** alpha and beta weights always passed (default alpha=0.3, beta=0.3)
- **D-04:** Both search modes produce ArticleListItem with final_score populated
- **D-05:** Cross-Encoder reranking is optional — gated behind `--rerank` flag or config

### Phase 43 Artifacts (Prerequisites)
- `src/application/rerank.py` — `rerank(query, candidates, top_k)` with BAAI/bge-reranker-base
- `src/application/combine.py` — `combine_scores(candidates, alpha, beta, gamma, delta)`
- `ArticleListItem` has fields: vec_sim, bm25_score, freshness, source_weight, ce_score, final_score
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v2.0 Architecture
- `docs/Search.md` — Complete technical design for Route A unified search ranking
- `.planning/phases/43-scoring-infrastructure/43-01-SUMMARY.md` — Phase 43 deliverable summary

### Requirements
- `.planning/REQUIREMENTS.md` — SEARCH-07 requirement for Phase 44

### Prior Phase Context
- `.planning/phases/43-scoring-infrastructure/43-CONTEXT.md` — Phase 43 decisions (Cross-Encoder, combine_scores)
- `src/application/articles.py` — ArticleListItem dataclass definition
- `src/storage/vector.py` — search_articles_semantic function
- `src/storage/sqlite/impl.py` — search_articles (BM25) function
- `src/cli/article.py` — Existing article CLI commands
</canonical_refs>

<codebase_context>
## Existing Code Insights

### Reusable Assets
- `ArticleListItem` dataclass in `articles.py`: has vec_sim, bm25_score, freshness, source_weight, ce_score, final_score fields
- `rerank()` in `rerank.py`: async function, takes query + candidates + top_k
- `combine_scores()` in `combine.py`: takes candidates + alpha/beta/gamma/delta weights
- `_format_date()` in `article.py`: formats pub_date for display

### Established Patterns
- Async search flow: `async def` functions with `asyncio.to_thread()` for blocking calls
- CLI argument parsing via Click decorators
- Weighted scoring: alpha*ce + beta*freshness + gamma*vec_sim + delta*bm25_score

### Integration Points
- Phase 44: CLI article search calls vector_search/search_articles → rerank → combine_scores
- rerank() and combine_scores() are application-layer functions
</codebase_context>

<specifics>
## Specific Ideas

**SEARCH-07 requirement:**
CLI `article search` command adjustment:
- `--semantic` 时：`vector_search` → 可选 `rerank` → `combine_scores(gamma=0.2, delta=0.0)`
- 默认 FTS5 时：`search_articles` → 可选 `rerank` → `combine_scores(gamma=0.0, delta=0.2)`
- `alpha/beta` 始终传入（默认 0.3）；`gamma/delta` 根据搜索类型显式传入

**CLI search command location:** `src/cli/article.py`
**Search command name:** `article search` (Click group `article`)
</specifics>

<deferred>
## Deferred Ideas

None — SEARCH-07 is well-scoped.
</deferred>

---
*Phase: 44-cli-integration*
*Context gathered: 2026-03-28*
