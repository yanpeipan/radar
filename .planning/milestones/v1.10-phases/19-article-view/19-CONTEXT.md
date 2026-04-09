# Phase 19: article view 命令增强 - Context

**Gathered:** 2026-04-06 (assumptions + auto mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

增强 `feedship article view` 命令，支持 `--url`、`--id`、`--json` 参数。功能范围：
- `--url <URL>`: 直接抓取 URL，Trafilatura 提取 Markdown 内容，返回内容，不入库
- `--id <article_id>`: 从数据库查 article，抓取 link URL，Trafilatura 回填 content 字段，更新数据库，返回 Markdown
- `--json`: JSON 格式输出

向后兼容：不传 `--url`/`--id` 时保持现有行为（只查看已有 content）。
</domain>

<decisions>
## Implementation Decisions

### Response Structure (--url/--json)
- **D-01:** 返回结构包含 `url`、`title`、`content`（Markdown）、`extracted_at` 四个字段
- **D-02:** 成功时 HTTP 200，JSON 直接返回内容字典（不是包装器）
- **D-03:** `--url --json` 和 `--id --json` 共用同一个结构

### Error Handling
- **D-04:** Trafilatura 提取失败时，exit code 1，输出友好错误信息到 stderr
- **D-05:** 网络超时（30s）视为错误，直接退出
- **D-06:** URL 无效或抓取失败时，显示具体错误原因

### Content Update Policy (--id)
- **D-07:** 总是覆盖 article.content 字段（不管原来是否有值）
- **D-08:** 同时更新 article 的 `updated_at` 时间戳

### Mutual Exclusivity
- **D-09:** `--url` 和 `--id` 互斥，同时使用时报错退出

### Architecture
- **D-10:** 业务逻辑放在 `src/application/article_view.py`，CLI 只调用不写逻辑
- **D-11:** 数据库更新用 `storage.update_article_content(article_id, content)` 新函数
- **D-12:** 抓取使用 `src/utils/scraping_utils.py` 的 `fetch_with_fallback`
- **D-13:** Trafilatura 直接写在 `src/application/article_view.py`，不复用 WebpageProvider

### TDD
- **D-14:** 先在 `tests/` 写单元测试，再实现代码
- **D-15:** Mock `fetch_with_fallback` 和 `trafilatura.extract` 进行测试

### Trafilatura Options
- **D-16:** `output_format="markdown"`，`include_images=False`，`include_tables=True`，`date_extraction=True`
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `src/cli/article.py` — 现有 `article view` 命令实现
- `src/application/articles.py` — application 层模式
- `src/utils/scraping_utils.py` — fetch_with_fallback, StealthFetcher
- `src/storage/sqlite/impl.py` — storage 层，get_article_detail, 数据库 schema
- `src/providers/webpage_provider.py` — Trafilatura 使用示例（参考参数）
- `.planning/ROADMAP.md` Phase 19 — 成功标准

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/utils/scraping_utils.py::fetch_with_fallback` — HTTP 抓取，支持 stealth，已集成 circuit breaker
- `src/providers/webpage_provider.py::trafilatura.extract` 调用 — 参数参考（output_format, include_images, include_tables）
- `src/storage/sqlite/impl.py::get_article_detail` — 现有 article 查询，返回 dict

### Established Patterns
- CLI 层在 `src/cli/` 调用 `src/application/` 层函数，结果传给 `print_json()`
- `--json` flag 统一行为：成功返回结构化 JSON，失败调用 `print_json_error()` 并 exit 1
- application 层无状态，输入输出都是简单数据结构（dict/list）

### Integration Points
- `src/cli/article.py` article_view 命令 → 调用 `src/application/article_view.py`
- `src/application/article_view.py` → `storage.update_article_content()` + `scraping_utils.fetch_with_fallback` + `trafilatura.extract`
- 数据库 articles 表 content 字段用于存储提取的 Markdown
</code_context>

<deferred>
## Deferred Ideas

(None — phase scope was precise)
</deferred>

---

*Phase: 19-article-view*
*Context gathered: 2026-04-06*
