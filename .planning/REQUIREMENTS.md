# Requirements: 个人资讯系统 (RSS Reader CLI)

**Defined:** 2026-03-25
**Core Value:** 用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。

## v1.5 Requirements

Requirements for uvloop async concurrency milestone.

### uvloop并发支持

- [x] **UVLP-01**: uvloop.install() 在应用启动时调用，Linux/macOS自动使用uvloop，Windows降级到asyncio
- [x] **UVLP-02**: ContentProvider 协议添加 crawl_async() 方法，默认实现使用 run_in_executor 包装同步 crawl()
- [x] **UVLP-03**: RSSProvider 实现 crawl_async()，使用 httpx.AsyncClient 进行异步HTTP请求
- [x] **UVLP-04**: fetch_all_async() 函数使用 asyncio.Semaphore 控制并发数，默认10
- [x] **UVLP-05**: SQLite写入通过 asyncio.to_thread() 串行化，避免数据库锁冲突
- [ ] **UVLP-06**: fetch --all 命令通过 uvloop.run() 调用异步fetch逻辑
- [ ] **UVLP-07**: CLI增加 --concurrency 参数，可配置并发数（默认10）

## Out of Scope

| Feature | Reason |
|---------|--------|
| aiohttp替代httpx | httpx.AsyncClient已足够 |
| 异步生成器流式返回 | 当前架构不需要，复杂度高 |
| 连接池复用 | 每次fetch独立请求，无需keep-alive |
| 动态并发自动调节 | 简单配置足够，复杂度高 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| UVLP-01 | Phase 19 | Complete |
| UVLP-02 | Phase 19 | Complete |
| UVLP-03 | Phase 20 | Complete |
| UVLP-04 | Phase 21 | Complete |
| UVLP-05 | Phase 21 | Complete |
| UVLP-06 | Phase 22 | Pending |
| UVLP-07 | Phase 22 | Pending |

**Coverage:**
- v1.5 requirements: 7 total
- Mapped to phases: 7
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-25*
*Last updated: 2026-03-25 after roadmap created*
