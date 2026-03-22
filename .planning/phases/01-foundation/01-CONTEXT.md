# Phase 1: Foundation - Context

**Gathered:** 2026-03-23 (auto mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

User can subscribe to RSS/Atom feeds, store articles locally, and list them via CLI. This is the core infrastructure phase — no search, no web crawling, no advanced features.
</domain>

<decisions>
## Implementation Decisions

### CLI Framework
- **D-01:** 使用 `click` 框架
  - 原因: 现代 Python CLI 框架，装饰器风格，自动生成帮助文档
  - feedparser 用于 RSS 解析，httpx 用于 HTTP 请求

### Output Format
- **D-02:** 纯文本输出，带 ANSI 颜色
  - `feed list`: 表格形式显示 (名称, URL, 文章数, 最后更新)
  - `article list`: 列表形式，每行显示: 标题 | 来源 | 日期
  - 默认简洁输出，`-v` verbose 模式显示更多信息

### Error Handling
- **D-03:** 单个 feed 失败不影响其他 feeds
  - 网络错误: 显示错误信息，继续处理下一个 feed
  - 解析错误: 使用 feedparser bozo 检测，跳过损坏的 feed
  - 数据库错误: 回滚事务，整体失败

### Database Schema
- **D-04:** 标准规范化 schema
  - `feeds` 表: id, name, url, etag, last_modified, last_fetched, created_at
  - `articles` 表: id, feed_id, title, link, guid, pub_date, description, content, created_at
  - UNIQUE(feed_id, guid) 防止重复
  - 索引: feed_id, pub_date, link

### CLI Commands
- **D-05:** 命令结构
  - `feed add <url>` - 添加 feed
  - `feed list` - 列出所有 feeds
  - `feed remove <id>` - 删除 feed
  - `feed refresh <id>` - 刷新单个 feed
  - `article list` - 列出最近文章 (默认 20 条)
  - `fetch --all` - 刷新所有 feeds

### Claude's Discretion
- 确切的颜色方案和格式细节
- 错误日志格式和详细程度
- 文章排序规则 (默认按日期倒序)
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/PROJECT.md` — 项目约束: Python CLI, SQLite, 本地优先
- `.planning/REQUIREMENTS.md` — Phase 1 需求的 16 个 requirements
- `.planning/research/STACK.md` — 推荐的技术栈: feedparser, httpx, click, sqlite3
- `.planning/research/ARCHITECTURE.md` — 数据库 schema 设计建议, CLI 命令分层设计
- `.planning/research/PITFALLS.md` — 常见错误: RSS 解析 fragility, SQLite WAL mode, GUID deduplication

### Stack Decisions
- `.planning/research/STACK.md` §Recommended Stack Summary — feedparser 6.0.x, httpx 0.27.x, click 8.1.x

### Architecture Notes
- `.planning/research/ARCHITECTURE.md` §Database Schema — feeds/articles tables, FTS5 for search
- `.planning/research/ARCHITECTURE.md` §CLI Design — hierarchical commands with click

### Pitfalls
- `.planning/research/PITFALLS.md` §RSS Feed Parsing — bozo detection for malformed feeds
- `.planning/research/PITFALLS.md` §SQLite Concurrency — WAL mode, busy_timeout
- `.planning/research/PITFALLS.md` §GUID Deduplication — UNIQUE constraint fallback to link+pubDate hash
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- 无 (greenfield 项目)

### Established Patterns
- 使用标准 Python 项目结构: `src/` 或直接 `*.py` 在根目录
- 单一 database.sqlite 文件在 `$HOME/.config/rss-reader/` 或项目目录

### Integration Points
- CLI 入口点在 `cli.py` 或 `__main__.py`
- 数据库模块: `db.py` 处理连接和迁移
- Feed 模块: `feed.py` 处理 fetch 和 parse
</code_context>

<specifics>
## Specific Ideas

- 简单直接，不要过度工程化
- 本地 SQLite 文件存储在用户目录或项目目录
- 可以通过 cron 定期运行 `fetch --all`
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-03-23*
