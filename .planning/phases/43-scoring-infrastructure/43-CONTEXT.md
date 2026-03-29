# Phase 43: Scoring Infrastructure - Context

**Gathered:** 2026-03-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 43 delivers two application-layer components: (1) Cross-Encoder rerank module (`application/rerank.py`) and (2) `combine_scores()` unified scoring function (`application/combine.py`). Both are prerequisites for Phase 44 CLI integration.

**Delivers:**
- `application/rerank.py` with `rerank(query, candidates, top_k)` using BAAI/bge-reranker-base
- Lazy import of torch/transformers inside `_load_reranker()` function
- Global caching of `_model` and `_tokenizer`
- `application/combine.py` with `combine_scores(candidates, alpha, beta, gamma, delta)`
- Newton's cooling law for freshness: `exp(-days_ago / 7)` with half_life_days=7
- Returns candidates sorted by `final_score` descending

**Depends on:** Phase 42 (complete)
**Requirements:** SEARCH-05, SEARCH-06
**Success Criteria (from ROADMAP.md):**
1. Cross-Encoder rerank module uses BAAI/bge-reranker-base with lazy import
2. torch and transformers loaded inside rerank() function, not at module level
3. Global caching of _model and _tokenizer to avoid repeated loading
4. combine_scores computes final_score from alpha*ce_score + beta*freshness + gamma*vec_sim + delta*bm25_score
5. combine_scores populates freshness field via Newton's cooling law
6. combine_scores sorts by final_score descending
</domain>

<decisions>
## Implementation Decisions

### Cross-Encoder Rerank (SEARCH-05)
- **D-01:** Model: `BAAI/bge-reranker-base` (from HuggingFace)
- **D-02:** Lazy import: `torch` and `transformers` imports inside `_load_reranker()` function, NOT at module level
- **D-03:** Global caching: `_model` and `_tokenizer` module-level variables outside functions
- **D-04:** `rerank(query, candidates, top_k)` signature; returns top_k reranked candidates
- **D-05:** ce_score field populated for each candidate via model output logits
- **D-06:** Candidates sorted by ce_score descending before truncation to top_k
- **D-07:** Error handling: raise RuntimeError with install instructions if torch/transformers not available
- **D-08:** Input pairs: (query, title) for each candidate — title only, no content

### combine_scores (SEARCH-06)
- **D-09:** Function signature: `combine_scores(candidates, alpha=0.3, beta=0.3, gamma=0.2, delta=0.2)`
- **D-10:** alpha: Cross-Encoder score weight (ce_score > 0 only)
- **D-11:** beta: Freshness weight (Newton's cooling law)
- **D-12:** gamma: Vector similarity weight (vec_sim)
- **D-13:** delta: BM25 weight (bm25_score)
- **D-14:** half_life_days = 7 (Newton's cooling law constant)
- **D-15:** freshness formula: `exp(-days_ago / 7)` where days_ago = (now - pub_dt).days
- **D-16:** ce_score = 0 treated as "not reranked": alpha * 0 = 0 contribution
- **D-17:** final_score formula: `alpha*ce + beta*freshness + gamma*vec_sim + delta*bm25_score`
- **D-18:** Return sorted by final_score descending

### Weight Configuration (already specified in Search.md)
- **D-19:** Semantic search: alpha=0.3, beta=0.3, gamma=0.2, delta=0.0
- **D-20:** Keyword search: alpha=0.3, beta=0.3, gamma=0.0, delta=0.2
- **D-21:** Hybrid search (optional): alpha=0.3, beta=0.3, gamma=0.1, delta=0.1
- **D-22:** Note: delta=0 for semantic search means BM25 signal excluded

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v2.0 Architecture
- `docs/Search.md` — Complete technical design for Route A unified search ranking
  - §Cross-Encoder rerank: lazy import, BAAI/bge-reranker-base, full rerank() implementation
  - §combine_scores: full implementation, weight matrix, Newton's cooling law
  - §Search type weight matrix: semantic vs keyword vs hybrid
  - §Complete flow: vector_search → optional rerank → combine_scores → final result

### Requirements
- `.planning/REQUIREMENTS.md` — SEARCH-05, SEARCH-06 requirements for Phase 43

### State
- `.planning/STATE.md` §Accumulated Context — v2.0 decisions (Route A, ArticleListItem fields, Cross-Encoder lazy import, Newton's cooling law)
- `.planning/ROADMAP.md` §Phase 43 — success criteria and phase goal

### Prior Phase Context
- `.planning/phases/42-storage-scoring-fixes/42-CONTEXT.md` — Phase 42 decisions (sigmoid normalization, freshness)
- `.planning/phases/41-articlelistitem-semantic-search-core/41-CONTEXT.md` — Phase 41 decisions (ArticleListItem fields)

### Codebase Scout Results
- `src/application/articles.py` §ArticleListItem — existing dataclass with 6 scoring fields
- `src/storage/vector.py` §search_articles_semantic — semantic search returns raw vec_sim
- `src/storage/sqlite/impl.py` §search_articles — BM25 with sigmoid normalization
- `src/storage/sqlite/impl.py` §list_articles — freshness populated via exp(-days_ago/7)
- `src/application/config.py` — bm25_factor config available

</canonical_refs>

<codebase_context>
## Existing Code Insights

### Reusable Assets
- `ArticleListItem` dataclass in `articles.py`: has vec_sim, bm25_score, freshness, source_weight, ce_score, final_score fields
- `_pub_date_to_timestamp()` in `vector.py:30-61`: handles int/str pub_date conversion
- `get_bm25_factor()` in `config.py`: returns configured BM25 sigmoid factor

### Established Patterns
- Lazy import pattern: sentence_transformers imported inside get_embedding_function() (Phase 42 fix)
- Dataclass field pattern: ArticleListItem with float fields defaulting to 0.0
- Global singleton pattern: _chroma_client module-level variable with lock

### Integration Points
- Phase 44: CLI article search command will call rerank() and combine_scores()
- rerank() takes list[ArticleListItem] and returns reranked list[ArticleListItem]
- combine_scores() takes candidates + weights, populates final_score, returns sorted list
</codebase_context>

<specifics>
## Specific Ideas

**Code locations (confirmed from prior phases):**
- ArticleListItem: `src/application/articles.py:20`
- search_articles_semantic: `src/storage/vector.py:271+`
- search_articles: `src/storage/sqlite/impl.py:660+`
- list_articles: `src/storage/sqlite/impl.py:478+`

**Cross-Encoder rerank() full implementation (from Search.md):**
```python
# application/rerank.py
from sentence_transformers import CrossEncoder

_model = None
_tokenizer = None

def _load_reranker():
    global _model, _tokenizer
    if _model is None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        model_name = "BAAI/bge-reranker-base"
        _tokenizer = AutoTokenizer.from_pretrained(model_name)
        _model = AutoModelForSequenceClassification.from_pretrained(model_name)
        _model.eval()
    return _model, _tokenizer

async def rerank(query: str, candidates: list[ArticleListItem], top_k: int = 20) -> list[ArticleListItem]:
    if not candidates:
        return candidates
    model, tokenizer = _load_reranker()
    texts = [(query, c.title or "") for c in candidates]
    inputs = tokenizer(texts, padding=True, truncation=True, return_tensors="pt", max_length=512)
    with torch.no_grad():
        scores = model(**inputs).logits.squeeze(-1).numpy()
    for i, c in enumerate(candidates):
        c.ce_score = float(scores[i])
    candidates.sort(key=lambda x: x.ce_score, reverse=True)
    return candidates[:top_k]
```

**combine_scores() full implementation (from Search.md):**
```python
# application/combine.py
import math
from datetime import datetime, timezone

def combine_scores(candidates: list[ArticleListItem], alpha=0.3, beta=0.3, gamma=0.2, delta=0.2) -> list[ArticleListItem]:
    half_life_days = 7
    now = datetime.now(timezone.utc)
    for c in candidates:
        if c.pub_date:
            pub_dt = datetime.fromtimestamp(c.pub_date, tz=timezone.utc)
            days_ago = (now - pub_dt).days
            c.freshness = math.exp(-days_ago / half_life_days)
        else:
            c.freshness = 0.0
        ce = c.ce_score if c.ce_score > 0 else 0.0
        c.final_score = alpha * ce + beta * c.freshness + gamma * c.vec_sim + delta * c.bm25_score
    candidates.sort(key=lambda x: x.final_score, reverse=True)
    return candidates
```

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 43 scope.

### Reviewed Todos (not folded)
None — no cross-reference todos reviewed in this session.

</deferred>

---

*Phase: 43-scoring-infrastructure*
*Context gathered: 2026-03-28*
