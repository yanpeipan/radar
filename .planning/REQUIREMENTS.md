# Requirements: 个人资讯系统 (RSS Reader CLI)

**Defined:** 2026-03-27
**Core Value:** 用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。

## v1.9 Requirements

Requirements for Automatic Discovery Feed milestone.

### Core Discovery

- [ ] **DISC-01**: HTML `<link>` tag 解析 — 解析 `<head>` 中的 `rel="alternate"` 标签（type 包含 rss/atom/rdf），发现 feed URL；大小写不敏感
- [ ] **DISC-02**: 常见路径探测 fallback — 对没有 autodiscovery 标签的站点，探测 `/feed`、`/feed/`、`/rss`、`/rss.xml`、`/atom.xml`、`/feed.xml`、`/index.xml`
- [ ] **DISC-03**: 相对 URL 解析 — 使用 `urllib.parse.urljoin` 正确解析 `<link href="/feed.xml">`，处理 `<base href>` 覆盖
- [ ] **DISC-04**: Feed 验证 — 发现后对 feed URL 发送 HEAD 请求，验证 HTTP 200 + Content-Type 包含 rss/atom/rdf；bozo feed 需被识别并过滤

### CLI Commands

- [ ] **DISC-05**: `discover <url> --discover-deep [n]` — 仅发现 feed，列出所有发现的 feeds（RSS/Atom/RDF），不订阅；默认 depth=1
- [ ] **DISC-06**: `feed add <url> --discover [on/off] --automatic [on/off] --discover-deep [n]` — 发现并订阅；--discover 默认 on，--automatic 默认 off

### Deep Crawling

- [ ] **DISC-07**: Depth > 1 BFS 爬取 — visited-set 防重复、depth limit 限制深度、rate limiting（2s/host）、cycle 检测；depth=1 只看当前页，depth>1 遍历站内链接
- [ ] **DISC-08**: robots.txt 遵守 — 深度爬取时使用 robotexclusionrulesparser（已安装）检查 robots.txt，lazy 模式同现有 crawl 行为

### Documentation

- [ ] **DISC-09**: `docs/Automatic Discovery Feed.md` — 自动发现逻辑文档化（discovery 算法、URL 解析规则、feed 类型支持列表）

## Future (Deferred)

- OPML 导入/导出
- 标记已读/未读状态
- 文章书签功能
- 定时自动抓取（cron 集成）
- 多输出格式（JSON、CSV）

## Out of Scope

| Feature | Reason |
|---------|--------|
| Playwright/Selenium | basic HTML parsing sufficient for `<link>` tags |
| Scrapy | overkill for feed discovery |
| feedfinder2 | abandoned (0.0.4, unmaintained) |
| 动态 JS 渲染 | autodiscovery via `<link>` tags 不需要 JS |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DISC-01 | Phase 34 | Pending |
| DISC-02 | Phase 34 | Pending |
| DISC-03 | Phase 34 | Pending |
| DISC-04 | Phase 34 | Pending |
| DISC-05 | Phase 35 | Pending |
| DISC-06 | Phase 36 | Pending |
| DISC-07 | Phase 37 | Pending |
| DISC-08 | Phase 37 | Pending |
| DISC-09 | Phase 37 | Pending |

**Coverage:**
- v1.9 requirements: 9 total
- Mapped to phases: 9/9 (100%)
- Phase 34: 4 requirements (DISC-01, DISC-02, DISC-03, DISC-04)
- Phase 35: 1 requirement (DISC-05)
- Phase 36: 1 requirement (DISC-06)
- Phase 37: 3 requirements (DISC-07, DISC-08, DISC-09)

---
*Requirements defined: 2026-03-27*
*Last updated: 2026-03-27*