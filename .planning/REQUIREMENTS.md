# Requirements — v2.0 Search Ranking Architecture

## Milestone v2.0 Requirements

### Core Infrastructure

- [ ] **SEARCH-01**: `ArticleListItem` 扩展原始信号字段：`vec_sim`, `bm25_score`, `freshness`, `source_weight`, `ce_score`, `final_score`；保留 `score` 字段兼容，最终由 `final_score` 统一排序

### Storage Layer (P0)

- [ ] **SEARCH-02**: `storage/vector.py` — `search_articles_semantic` 移除硬编码加权公式（`0.5×cos + 0.2×fresh + 0.3×weight`），score 直接返回 ChromaDB cosine similarity；确保 `pub_date` 以 INTEGER unix timestamp 传给 ChromaDB metadata filter
- [ ] **SEARCH-03**: `storage/sqlite/impl.py` — `search_articles` BM25 归一化修复：改用 Sigmoid 变换 `sigmoid_norm(bm25_raw, factor)`，factor 从 `config.py` 读取（默认 0.5），填充 `ArticleListItem.bm25_score`
- [ ] **SEARCH-04**: `storage/sqlite/impl.py` — `list_articles` 填充 freshness 分数（时间衰减，0-1），无 vec_sim/bm25_score/ce_score 时设为 0.0

### Application Layer (P1)

- [ ] **SEARCH-05**: 新增 `application/rerank.py` — Cross-Encoder 重排，使用 `BAAI/bge-reranker-base`；`torch` 和 `transformers` 在 `rerank()` 函数内部 lazy import；全局缓存 `_model`/`_tokenizer` 避免重复加载
- [ ] **SEARCH-06**: 新增 `application/combine.py` — `combine_scores(candidates, alpha, beta, gamma, delta)` 统一合并函数；牛顿冷却定律计算 freshness（half_life_days=7天）；按 final_score 降序返回

### CLI Integration (P2)

- [ ] **SEARCH-07**: CLI `article search` 命令调整：
  - `--semantic` 时：`vector_search` → 可选 `rerank` → `combine_scores(gamma=0.2, delta=0.0)`
  - 默认 FTS5 时：`search_articles` → 可选 `rerank` → `combine_scores(gamma=0.0, delta=0.2)`
  - `alpha/beta` 始终传入（默认 0.3）；`gamma/delta` 根据搜索类型显式传入

### Bug Fix (P0)

- [ ] **SEARCH-00**: 修复 `search_articles_semantic` 第363行崩溃：`_pub_date_to_timestamp` 对 INTEGER pub_date 调用 `datetime.fromisoformat(pub_date.replace("Z", "+00:00"))` 会失败；改为统一使用 `_pub_date_to_timestamp()` 处理所有 timestamp 转换

---

## Out of Scope

- BM25 分数的 `factor` 通过 CLI 参数暴露（由 `config.py` 管理，默认 0.5）
- ChromaDB 批量查询优化
- 多语言/多模型 Cross-Encoder 支持

---

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| SEARCH-00 | — | — |
| SEARCH-01 | — | — |
| SEARCH-02 | — | — |
| SEARCH-03 | — | — |
| SEARCH-04 | — | — |
| SEARCH-05 | — | — |
| SEARCH-06 | — | — |
| SEARCH-07 | — | — |
