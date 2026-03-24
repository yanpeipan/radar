# 个人资讯系统

## What This Is

一个 CLI 工具，帮助用户收集、订阅和组织来自互联网的信息来源。用户添加 RSS 订阅源或网站 URL，系统自动抓取内容并存储到本地 SQLite 数据库中，便于后续阅读和检索。

## Core Value

用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。

## Current State

**Shipped: v1.4 Storage Layer Enforcement** (2026-03-25)
- Phase 17 complete: Anti-屎山 refactoring — cli.py (798 lines) split into `src/cli/` package with 5 modules; DB context manager adopted
- Phase 18 complete: All database operations centralized in `src/storage/sqlite.py`
  - `get_db()` is now internal to storage layer only
  - AI tagging, feed, article, crawl, and CLI modules all delegate to storage functions
  - 16 new storage functions added covering all database operations

**Shipped: v1.4 GitHubReleaseProvider** (2026-03-24)
- Phase 16 complete: GitHubReleaseProvider (priority=200) using PyGithub repo.get_latest_release()
  - Separate from GitHubProvider — coexists with different focus
  - ReleaseTagParser extracts owner/version/release-type tags with semantic versioning
  - Provider runs first for all GitHub URLs (priority 200 > GitHubProvider 100)

**Shipped: v1.3 Provider Architecture** (2026-03-24)
- Phase 12 complete: Provider plugin architecture foundation + DB migrations
  - ContentProvider & TagParser Protocols with @runtime_checkable
  - ProviderRegistry with dynamic provider loading
  - feeds.metadata column migration + github_repos data migration
- Phase 13 complete: RSS/GitHub providers + Tag parser chaining
  - RSSProvider (priority=50) and GitHubProvider (priority=100) wrapping feeds/github.py
  - TagParser registry with chain_tag_parsers() and DefaultTagParser
- Phase 14 complete: CLI wired to ProviderRegistry (fetch --all, feed add/list via discover_or_default, repo commands deleted)
- Phase 15 complete: PyGithub Refactor — custom GitHub API replaced with PyGithub library
  - src/github.py deleted, src/github_utils.py + src/github_ops.py created
  - GitHubProvider and crawl.py now use PyGithub for all GitHub API calls

**Shipped: v1.2 Article List Enhancements** (2026-03-23)
- CLI 工具，支持 feed 订阅、网页抓取、GitHub 仓库监控
- GitHub Releases 和 Changelog 统一展示
- Rich table formatting for article list with ID and tags columns
- Article detail view and open-in-browser commands
- GitHub release tagging with unified tagging commands
- SQLite 本地存储，FTS5 全文搜索
- ~10 个 Python 源文件，约 2,800 行代码

## Requirements

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

## Tech Stack

- **CLI**: click 8.1.x
- **HTTP**: httpx 0.27.x
- **Feed 解析**: feedparser 6.0.x
- **HTML 提取**: readability-lxml 0.8.4.1, BeautifulSoup4 4.12.x
- **robots.txt**: robotexclusionrulesparser 1.7.1
- **网页抓取**: Scrapling (adaptive, JS 支持)
- **数据库**: sqlite3 (内置)
- **GitHub API**: PyGithub 2.x

## Context

- 运行在本地机器上（macOS/Linux）
- 数据存储在本地 SQLite 文件中
- 需要定期运行（手动或 cron）来更新内容

## Constraints

- **Tech**: Python (CLI 工具)
- **Storage**: SQLite（单一数据库文件）
- **No API**: 纯本地应用，无后端服务

---

*Last updated: 2026-03-25 after v1.4 milestone shipped*
