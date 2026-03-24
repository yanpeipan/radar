# Requirements: 个人资讯系统 (RSS Reader CLI)

**Defined:** 2026-03-25
**Core Value:** 用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。

## v1.6 Requirements

Requirements for nanoid ID generation milestone.

### nanoid ID生成

- [ ] **NANO-01**: store_article()使用nanoid.generate()替代uuid.uuid4()生成article id
- [ ] **NANO-02**: 生成迁移脚本，修复~2479条URL-like ID的历史数据
- [ ] **NANO-03**: 验证所有article相关操作（CRUD、tagging、search）正常

## v1.5 Requirements

Requirements for uvloop async concurrency milestone.

### uvloop并发支持

- [x] **UVLP-01**: uvloop.install() 在应用启动时调用，Linux/macOS自动使用uvloop，Windows降级到asyncio
- [x] **UVLP-02**: ContentProvider 协议添加 crawl_async() 方法，默认实现使用 run_in_executor 包装同步 crawl()
- [x] **UVLP-03**: RSSProvider 实现 crawl_async()，使用 httpx.AsyncClient 进行异步HTTP请求
- [x] **UVLP-04**: fetch_all_async() 函数使用 asyncio.Semaphore 控制并发数，默认10
- [x] **UVLP-05**: SQLite写入通过 asyncio.to_thread() 串行化，避免数据库锁冲突
- [x] **UVLP-06**: fetch --all 命令通过 uvloop.run() 调用异步fetch逻辑
- [x] **UVLP-07**: CLI增加 --concurrency 参数，可配置并发数（默认10）

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
| NANO-01 | Phase 23 | Pending |
| NANO-02 | Phase 24 | Deferred |
| NANO-03 | Phase 25 | Pending |
| UVLP-01 | Phase 19 | Complete |
| UVLP-02 | Phase 19 | Complete |
| UVLP-03 | Phase 20 | Complete |
| UVLP-04 | Phase 21 | Complete |
| UVLP-05 | Phase 21 | Complete |
| UVLP-06 | Phase 22 | Complete |
| UVLP-07 | Phase 22 | Complete |

**Coverage:**
- v1.6 requirements: 3 total
- Mapped to phases: 3 ✓
- v1.5 requirements: 7 total
- Mapped to phases: 7 ✓

---
*Requirements defined: 2026-03-25*
*Last updated: 2026-03-25 after v1.6 roadmap creation*
