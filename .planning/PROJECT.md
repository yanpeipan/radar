# Project: Feedship - Personal Information Aggregation System

**Type:** Python CLI Tool
**Core Value:** Users can centrally manage all information sources without visiting each website individually.
**Tech:** Python, SQLite, scrapling, feedparser, Rich, Click

---

## What This Is

A personal CLI tool that collects, subscribes to, and organizes information sources from the internet. Users add RSS feeds or website URLs, the system fetches and stores content locally in SQLite for reading and retrieval.

---

## Current Milestone: v1.11 — LLM 智能报告生成

**Goal:** 引入 LLM，为订阅源生成带结构化模板的 AI 日报，包含摘要、分类、评分、关键词提取

**Target features:**
- `feedship summarize --url/--id/--group --force` — 单篇/批量文章摘要
- `feedship report --template xxx --since --until` — 结构化日报生成
- Quality scoring (0-1)：用于排序 + 阈值过滤
- 关键词提取 + 标签：存入 SQLite + ChromaDB
- 主题聚类：同主题文章分组
- 混合 LLM：Ollama 本地优先，云端兜底（OpenAI/Azure）

**Last shipped:** v1.10 article view 增强 (SHIPPED 2026-04-06)

## Prior Milestone: v1.10 article view 增强

**Goal:** 增强 `feedship article view` 命令，支持 --url/--id/--json 参数，Trafilatura 最佳实践提取内容

**Status:** Complete (v1.10) — SHIPPED 2026-04-06

**Key deliverables:**
- `src/application/article_view.py` — business logic layer with `fetch_url_content()`, `fetch_and_fill_article()`
- `src/storage/sqlite/impl.py` — `update_article_content()` for DB backfill
- `src/cli/article.py` — `article view` with `--url/--id/--json` options

## Prior Milestone: v1.6 OpenClaw Skills

**Goal:** 完善 feedship skills 并准备发布到 clawhub

**Status:** Complete (v1.6) — SHIPPED 2026-04-03

| Requirement | Phase | Status |
|-------------|-------|--------|
| SKILL-01~05 | Phase 10 | Complete |
| FEED-01~03 | Phase 10 | Complete |
| AID-01~02 | Phase 10 | Complete |
| PUBLISH-01~03 | Phase 10 | Complete |

**Key deliverables:**
- feedship SKILL.md v1.5 — YAML fixed, info command docs, --json flags
- ai-daily SKILL.md v1.1 — YAML fixed, diagnostic tips
- Both skills published to ClawHub

---

## Prior Milestone: v1.5 Info Command

**Goal:** Add `info` CLI command for diagnostics and introspection

**Status:** Complete (v1.5)

| Command | Description |
|---------|-------------|
| `feedship info` | Display version, config path, config values, storage path, and storage stats |
| `feedship info --version` | Version only |
| `feedship info --config` | Config details only |
| `feedship info --storage` | Storage details only |
| `feedship info --json` | Machine-readable JSON output |

---

## Prior Milestone: v1.4 Patch Releases

**Goal:** Bug fixes — patchright dependency, config path using platformdirs

**Status:** Complete (v1.4.4)

| Version | Fix |
|---------|-----|
| v1.4.0 | Initial patch release |
| v1.4.1 | patchright dependency missing |
| v1.4.2 | SKILL.md docs update |
| v1.4.3 | Config path fix (platformdirs) |
| v1.4.4 | PyPI publish fix |

---

## Prior Milestone: v1.3 全面优化重构版

**Goal:** 系统性优化 — 从原则到框架到代码到性能

**Status:** Complete

---

## Current State (v1.10)

**Last milestone:** v1.10 article view 增强 — SHIPPED 2026-04-06
**Prior:** v1.9 (planned) — fetch --url

**Files:** ~3,500 LOC Python (src/)
**Storage:** SQLite (articles, feeds) + ChromaDB (embeddings)
**Providers:** RSS, Nitter, GitHub Release, GitHub Trending, Tavily, Webpage

---

## Requirements

### Validated

| Requirement | Milestone | Phase | Status |
|-------------|-----------|-------|--------|
| RSS Provider | v1.0 | 1 | Complete |
| Article Storage (SQLite) | v1.0 | 1 | Complete |
| CLI Commands | v1.0 | 1 | Complete |
| TAVILY-01 | v1.1 | 1 | Complete |
| TAVILY-02 | v1.1 | 1 | Complete |
| TAVILY-03 | v1.1 | 1 | Complete |
| GITHUB-01 | v1.1 | 1 | Complete |
| NITTER-01 | v1.2 | 1 | Complete |
| NITTER-02 | v1.2 | 1 | Complete |
| NITTER-03 | v1.2 | 1 | Complete |
| NITTER-04 | v1.2 | 1 | Complete |
| CLI-JSON-01 | v1.2 | 2 | Complete |
| CLI-JSON-02 | v1.2 | 2 | Complete |
| INFO-01 | v1.5 | 1 | Complete |
| INFO-02 | v1.5 | 1 | Complete |
| INFO-03 | v1.5 | 1 | Complete |
| INFO-04 | v1.5 | 1 | Complete |
| INFO-05 | v1.5 | 1 | Complete |
| INFO-06 | v1.5 | 1 | Complete |
| INFO-07 | v1.5 | 1 | Complete |
| SKILL-01 | v1.6 | 10 | Complete |
| SKILL-02 | v1.6 | 10 | Complete |
| SKILL-03 | v1.6 | 10 | Complete |
| SKILL-04 | v1.6 | 10 | Complete |
| SKILL-05 | v1.6 | 10 | Complete |
| FEED-01 | v1.6 | 10 | Complete |
| FEED-02 | v1.6 | 10 | Complete |
| FEED-03 | v1.6 | 10 | Complete |
| AID-01 | v1.6 | 10 | Complete |
| AID-02 | v1.6 | 10 | Complete |
| PUBLISH-01 | v1.6 | 10 | Complete |
| PUBLISH-02 | v1.6 | 10 | Complete |
| PUBLISH-03 | v1.6 | 10 | Complete |
| VIEW-01 | v1.10 | 19 | Complete |
| VIEW-02 | v1.10 | 19 | Complete |
| VIEW-03 | v1.10 | 19 | Complete |
| VIEW-04 | v1.10 | 19 | Complete |

### Active

- [ ] **SUMM-01**: `feedship summarize --url/--id/--group/--feed-id --force` — 单篇/批量文章摘要
- [ ] **SUMM-02**: `feedship report --template xxx --since --until` — 结构化日报生成
- [ ] **SUMM-03**: Quality scoring (0-1) — 排序依据 + 阈值过滤
- [ ] **SUMM-04**: 关键词提取 + tags 字段 — 存入 SQLite + ChromaDB
- [ ] **SUMM-05**: 主题聚类 — 同主题文章分组
- [ ] **SUMM-06**: 混合 LLM 支持 — Ollama 本地优先，云端兜底

---

## Out of Scope

| Item | Reason |
|------|--------|
| Twitter/X API integration | OAuth complexity, API approval required |
| Nitter instance hosting | User must provide/configure their own |
| Tweet engagement metrics (likes, retweets) | Nitter RSS doesn't provide this |
| Quote tweets / replies threading | Nitter RSS basic mode only |
| Web API / HTTP server | CLI-only tool |
| Mobile app | Web-first, CLI tool |

---

## Key Decisions

| Date | Decision | Rationale | Status |
|------|----------|-----------|--------|
| 2026-04-01 | Use Nitter RSS over Twitter API | No auth required, open source | ✅ |
| 2026-04-01 | NitterProvider priority 300 | Same tier as GitHub providers | ✅ |
| 2026-04-01 | Auto-discover Nitter instance | Avoid single-point-of-failure | ✅ |
| 2026-04-02 | JSON output replaces Rich entirely | Clean machine/human separation | ✅ |
| 2026-04-02 | Object wrapper JSON format | Consistent structure, pagination metadata | ✅ |

---

## Context

### v1.4 Shipped

- patchright dependency fix
- platformdirs config path

### v1.3 Shipped

- SQLite batch operations & profiling
- HTTP resilience & rate limiting
- Type safety & configuration validation
- Security hardening & graceful degradation

### v1.2 Shipped Features

1. **NitterProvider** — Twitter/X via Nitter RSS feeds (`nitter:username`)
2. **CLI JSON Output** — `--json` flag on all commands for scripting

### Known Issues

- Nitter instances may rate-limit or go down (fallback instances configured)
- Stealth fetcher may timeout on slow Nitter instances (15s timeout set)

### Tech Stack

- **CLI:** click, rich
- **HTTP:** scrapling (Fetcher/AsyncFetcher), httpx (for compatibility)
- **RSS:** feedparser
- **Storage:** sqlite3, chromadb
- **Search:** sentence-transformers, scikit-learn (BM25)
- **Config:** dynaconf, PyYAML

---
*Last updated: 2026-04-07 after v1.11 milestone started*

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state
