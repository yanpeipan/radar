# 个人资讯系统

## What This Is

一个个人资讯系统，帮助用户收集、订阅和组织来自互联网的信息来源。用户添加 RSS 订阅源或网站 URL，系统自动抓取内容并存储到本地 SQLite 数据库中，便于后续阅读和检索。

## Core Value

用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] 用户可以添加 RSS 订阅源
- [ ] 系统可以解析和抓取 RSS 内容
- [ ] 用户可以添加网站 URL 进行抓取
- [ ] 系统将抓取的内容存储到 SQLite 数据库
- [ ] 用户可以查看已采集的文章列表
- [ ] 用户可以搜索已存储的内容

### Out of Scope

- 复杂的标签/分类系统
- 多用户支持
- 云端同步
- 分享功能
- 移动端应用

## Context

- 运行在本地机器上（macOS/Linux）
- 数据存储在本地 SQLite 文件中
- 需要定期运行（手动或 cron）来更新内容

## Constraints

- **Tech**: Python (CLI 工具)
- **Storage**: SQLite（单一数据库文件）
- **No API**: 纯本地应用，无后端服务

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SQLite 存储 | 轻量、无需独立服务、本地优先 | — Pending |
| Python 实现 | 生态系统丰富，RSS/HTML 解析库成熟 | — Pending |
| CLI 优先 | 简单透明，易于自动化 | — Pending |

---

*Last updated: 2026-03-22 after initialization*
