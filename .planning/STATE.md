---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Search Ranking Architecture
status: v2.0 milestone complete
stopped_at: Completed 43-01-PLAN.md
last_updated: "2026-03-29T08:13:00Z"
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 4
  completed_plans: 4
---

# Project State

## Project Reference

See: .planning/PROJECT.md (v2.0 Search Ranking Architecture)

**Core value:** 用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。
**Current focus:** Phase 44 — CLI Integration

| Phase | Goal | Requirements | Status |
|-------|------|--------------|--------|
| 40. Comprehensive uvloop Audit | Zero asyncio.run(), uvloop at CLI boundaries | UVLOOP-AUDIT-01, 02, 03 | ✅ Complete |
| 41. ArticleListItem & Semantic Search Core | ArticleListItem with scoring fields; raw cos_sim | SEARCH-00, SEARCH-01, SEARCH-02 | ✅ Complete |
| 42. Storage Scoring Fixes | BM25 sigmoid; list_articles freshness | SEARCH-03, SEARCH-04 | ✅ Complete |
| 43. Scoring Infrastructure | Cross-Encoder rerank; combine_scores | SEARCH-05, SEARCH-06 | 🔵 In progress |
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
- [Phase ?]: SEARCH-00 fixed: search_articles_semantic now uses _pub_date_to_timestamp()
- [Phase ?]: SEARCH-01: ArticleListItem has 6 scoring fields with source_weight=0.3 default
- [Phase ?]: SEARCH-02: search_articles_semantic returns raw cos_sim as vec_sim
- [Phase 42]: BM25 sigmoid normalization: 1 / (1 + exp(bm25 * factor)), factor from config.py default 0.5
- [Phase 42]: Freshness via Newton's cooling law: exp(-days_ago / 7)
- [Phase 42]: BM25 sigmoid normalization: 1 / (1 + exp(bm25 * factor)), factor from config.py default 0.5
- [Phase 42]: Freshness via Newton's cooling law: exp(-days_ago / 7) in list_articles

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

Last activity: 2026-03-29 - Enhanced parse_link_elements with trafilatura LINK_VALIDATION_RE fallback (260329-m9c)

## Quick Tasks Completed

| # | Description | Date | Commit |
|---|-------------|------|--------|
| 260328 | Refactor provider priority: GitHubRelease=300, RSS=200, Webpage=100; removed github.com hardcoding | 2026-03-28 | 213ad74 |
| 260329a | Refactor WebpageProvider: SITE_CONFIGS → config.yaml; zero domain hardcoding in Python | 2026-03-29 | 42a0a6b |
| 260329b | Replace httpx with scrapling Fetcher in providers and discovery (rss_provider, fetcher, deep_crawl) | 2026-03-29 | 6283e09 |
| 260329m9a | Refactor RSSProvider.discover(): trafilatura.fetch_url() + xml.etree for title extraction | 2026-03-29 | 0ce4e21 |
| 260329m9b | Merge validate+extract into single HTTP request in deep_crawl | 2026-03-29 | 54a551b |
| 260329m9c | Enhance parse_link_elements with LINK_VALIDATION_RE fallback + BLACKLIST filter | 2026-03-29 | e43dda1 |
| 260329m10 | Dedupe feed MIME types: use trafilatura.feeds.FEED_TYPES instead of hardcoded | 2026-03-29 | |

- Phase 44-01: Wired article search with --rerank flag, combine_scores weight config for semantic (gamma=0.2, delta=0.0) and FTS5 (gamma=0.0, delta=0.2) paths

## Planned Tasks

| # | Description | Priority | Notes |
|---|-------------|----------|-------|
| TBD-asyncfetcher | 用 AsyncFetcher 替换 asyncio.to_thread(Fetcher.get)，提升异步并发性能 | 高 | 影响文件: rss_provider.py, fetcher.py, deep_crawl.py, discover.py |
