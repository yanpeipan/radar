# 个人资讯系统

## What This Is

一个 CLI 工具，帮助用户收集、订阅和组织来自互联网的信息来源。用户添加 RSS 订阅源或网站 URL，系统自动抓取内容并存储到本地 SQLite 数据库中，便于后续阅读和检索。

## Core Value

用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。

## Current Milestone: v2.0 Search Ranking Architecture

**Goal:** 实现 Route A — 三种搜索方法返回原始信号，应用层 `combine_scores` 统一合并，可选 Cross-Encoder 重排

**Target features:**
- `ArticleListItem` 扩展原始信号字段（`vec_sim`, `bm25_score`, `freshness`, `source_weight`, `ce_score`, `final_score`）
- `search_articles_semantic` 移除硬编码加权，返回原始 `cos_sim`
- BM25 归一化修复为 Sigmoid 变换
- `list_articles` 填充 `freshness` 分数
- Cross-Encoder 重排（lazy import）
- `combine_scores` 统一合并函数
- CLI search 命令接入权重配置

**Status:** ⏳ Planning

---

## Current State

**Shipped: v1.11 Comprehensive uvloop Audit** (2026-03-28)
- Phase 40 complete: Zero `asyncio.run()` calls in `src/`
- All 5 `uvloop.run()` calls at correct CLI boundaries (feed.py ×4, discover.py ×1)
- No blocking I/O outside `asyncio.to_thread()`
- 5 anti-patterns identified and fixed

**Shipped: v1.10 uvloop Best Practices Review** (2026-03-28)
- Phase 39 complete: Simplified `install_uvloop()` to just `uvloop.install()`
- Removed dead code: `_default_executor`, `_get_default_executor()`, `run_in_executor_crawl()`, `_main_loop`
- `asyncio_utils.py` reduced from 93 lines to 44 lines

**Shipped: v1.9 Automatic Discovery Feed** (2026-03-27)
- Phase 34-37 complete: Discovery Core Module, CLI, Integration, Deep Crawling
- `discover <url>` command with `--discover-deep` support
- BFS crawler with robots.txt compliance and rate limiting (2s/host)
- Multi-factor ranking: `final_score = 0.5*norm_similarity + 0.3*norm_freshness + 0.2*source_weight`

**Shipped: v1.8 ChromaDB 语义搜索** (2026-03-27)
- Phase 30-33 complete: ChromaDB infrastructure, embedding write path, semantic search CLI
- `search --semantic` and `article related` commands
- Embedding model pre-downloaded on startup

**Shipped: v1.7 pytest测试框架** (2026-03-25)
- Phase 26-29 complete: 85 total tests across all phases
- `tests/conftest.py` with 5 fixtures (temp_db_path, initialized_db, sample_feed, sample_article, cli_runner)
- `tests/test_providers.py` — 24 provider tests (RSSProvider, GitHubReleaseProvider, ProviderRegistry)
- `tests/test_storage.py` — 42 storage tests (Article, Feed, Tag CRUD)
- `tests/test_cli.py` — 19 CLI integration tests (Feed, Article, Tag commands)

**Shipped: v1.6 uvloop并发支持** (2026-03-25)

---

## Requirements

### Active (v2.0)

- [ ] SEARCH-01: `ArticleListItem` 扩展原始信号字段 — P0
- [ ] SEARCH-02: `search_articles_semantic` 返回原始 `cos_sim`，移除硬编码组合 — P0
- [ ] SEARCH-03: BM25 归一化修复为 Sigmoid 变换 — P1
- [ ] SEARCH-04: `list_articles` 填充 `freshness` 分数 — P1
- [ ] SEARCH-05: Cross-Encoder 重排（lazy import）— P2
- [ ] SEARCH-06: `combine_scores` 统一合并函数 — P2
- [ ] SEARCH-07: CLI search 命令接入权重配置 — P2

### Validated (v1.11)

- [x] UVLOOP-AUDIT-01: Zero `asyncio.run()` calls in `src/` — Phase 40 complete
- [x] UVLOOP-AUDIT-02: No blocking I/O outside `asyncio.to_thread()` — Phase 40 complete
- [x] UVLOOP-AUDIT-03: All async providers use true async patterns — Phase 40 complete

### Validated (v1.10)

- [x] UVLOOP-BEST-01: `install_uvloop()` simplified to `uvloop.install()` — Phase 39 complete
- [x] UVLOOP-BEST-02: Dead code removed from `asyncio_utils.py` — Phase 39 complete

### Validated (v1.9)

- [x] DISC-01: HTML `<link>` tag 解析 — Phase 34 complete
- [x] DISC-02: 常见路径探测 fallback — Phase 34 complete
- [x] DISC-03: 相对 URL 解析 — Phase 34 complete
- [x] DISC-04: Feed 验证 (HEAD + Content-Type) — Phase 34 complete
- [x] DISC-05: `discover <url>` CLI 命令 — Phase 35 complete
- [x] DISC-06: `feed add --discover --automatic` 集成 — Phase 36 complete
- [x] DISC-07: Depth > 1 BFS 爬取 — Phase 37 complete
- [x] DISC-08: robots.txt 遵守 — Phase 37 complete
- [x] DISC-09: `docs/Automatic Discovery Feed.md` 文档 — Phase 37 complete
- [x] RANK-01: Multi-factor ranking algorithm — Phase 38 complete

### Validated (v1.7)

- [x] TEST-01: 引入pytest测试框架，配置conftest.py和基础fixtures
- [x] TEST-02: 为Provider插件架构编写单元测试
- [x] TEST-03: 为Storage层SQLite操作编写单元测试
- [x] TEST-04: 为CLI命令编写集成测试

### Validated (v1.5)

- [x] UVLP-01: uvloop作为asyncio事件循环，提升I/O性能
- [x] UVLP-02: httpx异步客户端支持并发请求
- [x] UVLP-03: 可配置并发数（默认10x）
- [x] UVLP-04: SQLite写入保持串行，避免锁冲突
- [x] UVLP-06: `fetch --all`使用uvloop.run()执行异步抓取
- [x] UVLP-07: CLI --concurrency参数可配置并发限制（默认10，范围1-100）

### Validated (v1.0 MVP)

- [x] 用户可以添加 RSS 订阅源 — v1.0
- [x] 系统可以解析和抓取 RSS 内容 — v1.0
- [x] 用户可以添加网站 URL 进行抓取 — v1.0
- [x] 系统将抓取的内容存储到 SQLite 数据库 — v1.0
- [x] 用户可以查看已采集的文章列表 — v1.0
- [x] 用户可以搜索已存储的内容 — v1.0
- [x] 用户可以刷新订阅源获取最新内容 — v1.0
- [x] 系统支持条件刷新（ETag/Last-Modified）— v1.0

### Validated (v1.1)

- [x] 用户可以添加 GitHub 仓库 URL 监控 — v1.1
- [x] 系统用 GitHub API 获取 releases 信息 — v1.1
- [x] 系统用 Scrapling 获取 changelog 文件内容 — v1.1
- [x] 新版本变化统一展示 — v1.1

### Validated (v1.2)

- [x] 用户可以在 article list 中看到 id 和 tags 列 — v1.2
- [x] 用户可以查看文章详情（detail 子命令）— v1.2
- [x] GitHub releases 可以通过 article tag 命令打标签 — v1.2

### Backlog

- [ ] OPML 导入/导出
- [ ] 标记已读/未读状态
- [ ] 文章书签功能
- [ ] 定时自动抓取（cron 集成）
- [ ] 多输出格式（JSON、CSV）

### Deferred (v1.6)

- [ ] NANO-01: store_article()使用nanoid.generate()替代uuid.uuid4() — deferred to v1.8
- [ ] NANO-02: 生成迁移脚本，修复~2479条URL-like ID的历史数据 — deferred to v1.8
- [ ] NANO-03: 验证所有article相关操作（CRUD、tagging、search）正常 — deferred to v1.8

### Out of Scope

- 复杂的标签/分类系统
- 多用户支持
- 云端同步
- 分享功能
- 移动端应用

## Key Decisions

| Decision | Rationale | Status |
|----------|-----------|--------|
| SQLite 存储 | 轻量、无需独立服务、本地优先 | ✅ Good |
| Python 实现 | 生态系统丰富，RSS/HTML 解析库成熟 | ✅ Good |
| CLI 优先 | 简单透明，易于自动化 | ✅ Good |
| Readability 提取 | Firefox Reader View 算法，质量最高 | ✅ Good |
| FTS5 搜索 | SQLite 内置，零依赖，高性能 | ✅ Good |
| robots.txt lazy 模式 | 默认忽略，需要时强制遵守 | ✅ Good |
| 固定 2s 限速 | 简单可靠，避免被封禁 | ✅ Good |
| Scrapling 引入 | JS 渲染和 adaptive parsing 支持 | ✅ Good (v1.1) |
| Provider 插件架构 | 动态加载 + match 路由，支持多种 URL 类型 | ✅ Good (v1.3) |
| Tag Parser 插件链 | 多 parser 结果并集去重，支持扩展 | ✅ Good (v1.3) |
| github_repos 并入 feeds | metadata JSON 字段存储 provider 特定数据 | ✅ Good (v1.3) |
| GitHubReleaseProvider | 独立 provider，priority=200 优于 GitHubProvider | ✅ Good (v1.4) |
| cli.py → src/cli/ | 包结构拆分，单一职责，便于维护和测试 | ✅ Good (v1.4) |
| Storage layer enforcement | get_db() internal to src/storage/ only，所有模块调用 storage functions | ✅ Good (v1.4) |
| feed_meta() httpx优化 | 使用 httpx.get + feedparser 替代 crawl()，5s timeout | ✅ Good (v1.4) |
| asyncio.Semaphore并发限制 | fetch_all_async() uses Semaphore(default 10) to limit concurrent crawls | ✅ Good (v1.5) |
| asyncio.Lock + to_thread | SQLite writes serialized via asyncio.Lock + asyncio.to_thread() — prevents "database is locked" | ✅ Good (v1.5) |
| uvloop.run() in CLI | `fetch --all` wraps async fetch with uvloop.run() for event loop optimization | ✅ Good (v1.5) |
| --concurrency CLI参数 | Click IntRange(1, 100) validation, passed to fetch_all_async() Semaphore | ✅ Good (v1.5) |
| nanoid替代uuid | 使用nanoid.generate()替代uuid.uuid4()生成更短（21字符）URL-safe的article ID | ✅ Good (v1.6) |
| Discovery 独立模块 | `src/discovery/` 作为 service 模块而非 Provider 插件 | ✅ Good (v1.9) |
| Scrapling 替代 BeautifulSoup | Adaptive parsing + JS 支持，更好的 HTML 解析 | ✅ Good (v1.9) |
| CSS selector link discovery | 动态发现站内链接而非硬编码子目录名 | ✅ Good (v1.9) |
| Multi-factor ranking | `0.5*sim + 0.3*fresh + 0.2*weight` 公式可配置 | ✅ Good (v1.9) |
| uvloop.install() 简化 | 只调用 `uvloop.install()`，platform check + error handling | ✅ Good (v1.10) |
| uvloop.run() at CLI boundaries | 所有 CLI 入口点使用 uvloop.run()，async 代码通过 to_thread 调用 | ✅ Good (v1.11) |

## Tech Stack

- **CLI**: click 8.1.x
- **HTTP**: httpx 0.27.x
- **Feed 解析**: feedparser 6.0.x
- **HTML 提取**: readability-lxml 0.8.4.1, BeautifulSoup4 4.12.x
- **robots.txt**: robotexclusionrulesparser 1.7.1
- **网页抓取**: Scrapling (adaptive, JS 支持)
- **数据库**: sqlite3 (内置)
- **GitHub API**: PyGithub 2.x
- **Semantic Search**: ChromaDB + sentence-transformers (all-MiniLM-L6-v2)
- **Vector DB**: ChromaDB persistent client

## Context

- 运行在本地机器上（macOS/Linux）
- 数据存储在本地 SQLite 文件中
- 需要定期运行（手动或 cron）来更新内容

## Constraints

- **Tech**: Python (CLI 工具)
- **Storage**: SQLite（单一数据库文件）
- **No API**: 纯本地应用，无后端服务

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

---

*Last updated: 2026-03-28 — v2.0 Search Ranking Architecture started*
