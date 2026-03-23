# Requirements: Personal Information System

**Defined:** 2026-03-23
**Core Value:** 用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。

## v1.3 Requirements

### Provider Infrastructure

- [x] **PROVIDER-01**: Provider Registry — 动态加载 `src/providers/` 下的 provider，按 priority 排序，封装为 `ProviderRegistry` 单例
- [x] **PROVIDER-02**: Provider Protocol — 定义 `match(url) / priority() / crawl(url) / parse(raw) / tag_parsers() / parse_tags(article)` 接口，用 `@runtime_checkable` 的 `Protocol`
- [x] **PROVIDER-03**: Error Isolation — 单个 provider 失败（crawl/parse 异常）log.error 并继续下一个 provider，不影响主流程
- [x] **PROVIDER-04**: Provider Fallback — 无 provider 匹配时使用默认 RSS provider（match() 返回 False，priority() 返回 0）

### Provider Implementations

- [x] **PROVIDER-05**: RSS Provider — 封装现有 `feeds.py` 的 RSS/Atom 处理逻辑，实现 `ContentProvider` 接口，priority=50
- [x] **PROVIDER-06**: GitHub Provider — 封装现有 `github.py` 的 GitHub releases/changelog 处理逻辑，实现 `ContentProvider` 接口，priority=100

### Tag Parser

- [x] **TAG-01**: Tag Parser Chaining — 支持多个 TagParser 链式执行，结果并集去重，接口：`parse_tags(article) -> List[Tag]`
- [x] **TAG-02**: Default Tag Parser — `src/tags/default_tag_parser.py` 实现，基于现有 tag_rules.py 逻辑，支持 AI-powered tagging

### Database

- [x] **DB-01**: feeds.metadata 字段 — `feeds` 表新增 `metadata` TEXT 字段（JSON），存储 provider 特定数据（如 github_token）
- [x] **DB-02**: github_repos 数据迁移 — 将 `github_repos` 表的 owner/repo/token 数据迁移到对应 `feeds.metadata`，然后删除 `github_repos` 表
- [x] **DB-03**: github_releases 保留 — `github_releases` 表保留不变（文章级联通过 `feed_id` 关联）

### CLI Integration

- [x] **CLI-01**: fetch --all 使用 Registry — `fetch --all` 遍历 `ProviderRegistry`，每个 provider 调用 `crawl` + `parse`
- [x] **CLI-02**: feed add 自动路由 — `feed add <url>` 通过 `ProviderRegistry.discover()` 自动选择匹配 provider，无需用户指定类型
- [x] **CLI-03**: 删除 repo 命令 — 删除 `repo add`、`repo list`、`repo remove`、`repo refresh` 命令，统一由 `feed` 命令处理
- [x] **CLI-04**: feed list 显示 provider type — `feed list` 输出增加 provider type 列（如 RSS / GitHub）

## Out of Scope

| Feature | Reason |
|---------|--------|
| Async parallel refresh | v2+ feature，复杂性高，顺序刷新对个人工具足够 |
| External plugin discovery | v2+，内部 provider 足够满足当前需求 |
| Plugin hot-reload | CLI 重启即可，个人工具不需要热更新 |
| Per-feed tag rules | feed rules 函数为空（这次不做），全局 tag rules 足够 |

## Traceability

| Requirement | Phase | Status |
|------------|-------|--------|
| PROVIDER-01 | Phase 12 | Complete |
| PROVIDER-02 | Phase 12 | Complete |
| PROVIDER-03 | Phase 12 | Complete |
| PROVIDER-04 | Phase 12 | Complete |
| DB-01 | Phase 12 | Complete |
| DB-02 | Phase 12 | Complete |
| DB-03 | Phase 12 | Complete |
| PROVIDER-05 | Phase 13 | Complete |
| PROVIDER-06 | Phase 13 | Complete |
| TAG-01 | Phase 13 | Complete |
| TAG-02 | Phase 13 | Complete |
| CLI-01 | Phase 14 | Complete |
| CLI-02 | Phase 14 | Complete |
| CLI-03 | Phase 14 | Complete |
| CLI-04 | Phase 14 | Complete |

**Coverage:**
- v1.3 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0

---
*Requirements defined: 2026-03-23*
*Last updated: 2026-03-23 after v1.3 roadmap created*
