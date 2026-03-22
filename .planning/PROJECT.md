# 个人资讯系统

## What This Is

一个 CLI 工具，帮助用户收集、订阅和组织来自互联网的信息来源。用户添加 RSS 订阅源或网站 URL，系统自动抓取内容并存储到本地 SQLite 数据库中，便于后续阅读和检索。

## Core Value

用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。

## Current State

**Shipped: v1.0 MVP** (2026-03-22)
- CLI 工具，支持 feed 订阅和网页抓取
- SQLite 本地存储，FTS5 全文搜索
- 7 个 Python 源文件，约 1,282 行代码

**Current Milestone: v1.1**

**Goal:** 用户可以监控 GitHub 仓库的 releases 和 changelog 变化

**Target features:**
- GitHub Releases：用 GitHub API 获取版本号 + release notes
- GitHub Changelog：用 Scrapling 网页抓取监控 CHANGELOG.md 文件变化
- 手动添加 GitHub 仓库 URL，定期检查新版本
- 统一展示（releases 和 changelog 展示方式一致）

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

### Active (v1.1)

**GitHub 监控：**
- [ ] GH-01: 用户可以添加 GitHub 仓库 URL 监控
- [ ] GH-02: 系统用 GitHub API 获取 releases 信息
- [ ] GH-03: 系统用 Scrapling 获取 changelog 文件内容
- [ ] GH-04: 新版本变化统一展示

**后续功能（暂不纳入 v1.1）：**
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

## Tech Stack

- **CLI**: click 8.1.x
- **HTTP**: httpx 0.27.x
- **Feed 解析**: feedparser 6.0.x
- **HTML 提取**: readability-lxml 0.8.4.1, BeautifulSoup4 4.12.x
- **robots.txt**: robotexclusionrulesparser 1.7.1
- **网页抓取 (v1.1)**: Scrapling (adaptive, JS 支持)
- **数据库**: sqlite3 (内置)

## Context

- 运行在本地机器上（macOS/Linux）
- 数据存储在本地 SQLite 文件中
- 需要定期运行（手动或 cron）来更新内容

## Constraints

- **Tech**: Python (CLI 工具)
- **Storage**: SQLite（单一数据库文件）
- **No API**: 纯本地应用，无后端服务

---

*Last updated: 2026-03-23 after v1.1 milestone start*
