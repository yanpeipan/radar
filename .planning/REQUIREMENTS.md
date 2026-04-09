# Requirements: Feedship v1.11 LLM 智能报告生成

**Defined:** 2026-04-07
**Core Value:** Users can centrally manage all information sources without visiting each website individually. LLM adds AI-powered article analysis for efficient information digestion.

## v1 Requirements

### LLM Infrastructure (INFRA)

- [ ] **INFRA-01**: LiteLLM 客户端集成 — 统一接口支持 OpenAI / Ollama / Azure / Anthropic，提供 provider fallback chain (Ollama → OpenAI → Azure)
- [ ] **INFRA-02**: Cost 架构 — feed weight gating (仅 weight ≥ 0.7 处理), recency gating (仅最近 48h), deduplication (content hash), hard daily cap
- [ ] **INFRA-03**: Content truncation — tiktoken token 计数，truncate to first 8K tokens，超长文章输出警告
- [ ] **INFRA-04**: Async wrapper — asyncio 包装，timeout handling，progress bar 支持
- [ ] **INFRA-05**: Provider fallback — Ollama 离线时自动切换云端，health check on startup，`--force-provider` 覆盖标志
- [ ] **INFRA-06**: Rate limiting — LiteLLM `max_retries=3`, exponential backoff, controlled concurrency (max 5 concurrent)

### Storage (STOR)

- [ ] **STOR-01**: SQLite schema migration — ALTER TABLE articles ADD COLUMN summary TEXT, quality_score REAL, keywords TEXT, tags TEXT, summarized_at TIMESTAMP
- [ ] **STOR-02**: Storage functions — `update_article_llm()`, `get_article_with_llm()`, `list_articles_for_llm()`
- [ ] **STOR-03**: ChromaDB collections — `article_summaries` (摘要向量), `article_keywords` (关键词向量), collection registry

### Summarization (SUMM)

- [ ] **SUMM-01**: `feedship summarize --url <url>` — 抓取 URL，生成单篇 3-5 句摘要，存入 SQLite，--force 强制重新生成
- [ ] **SUMM-02**: `feedship summarize --id <article_id>` — 为指定 article 生成摘要
- [ ] **SUMM-03**: `feedship summarize --group <group>` — 为指定 group 下所有未摘要的文章生成摘要
- [ ] **SUMM-04**: `feedship summarize --feed-id <feed_id>` — 为指定 feed 下所有未摘要的文章生成摘要
- [ ] **SUMM-05**: `feedship summarize --all` — 为所有未摘要的文章生成摘要（受 weight gating 限制）
- [ ] **SUMM-06**: JSON output — `--json` 输出机器可读格式，包含 summary, tokens_used, model_used

### Quality Scoring (QUAL)

- [ ] **QUAL-01**: Quality scoring — 0.0-1.0 float score，多因子 LLM 评估 (content richness, source authority, writing quality, uniqueness)，结合 feed weight
- [ ] **QUAL-02**: Quality 输出 breakdown — JSON 包含各因子分数，用于可解释性
- [ ] **QUAL-03**: Quality 用于排序 — `feedship article list --sort quality` 按 quality_score 降序
- [ ] **QUAL-04**: Quality 阈值过滤 — `feedship article list --min-quality 0.5` 过滤低分文章

### Keyword Extraction (KEYW)

- [ ] **KEYW-01**: Keyword extraction — 每篇文章提取 3-5 个关键词，存入 SQLite keywords 字段 (JSON 数组)
- [ ] **KEYW-02**: Keyword ChromaDB 存储 — 关键词 embedding 存入 `article_keywords` collection，支持语义搜索
- [ ] **KEYW-03**: 自动 tag 生成 — 基于关键词自动生成 tags 字段，支持自由标签

### Topic Clustering (CLUST)

- [ ] **CLUST-01**: 主题聚类 — 将文章按主题分组，使用 embedding 相似度 + LLM 分类
- [ ] **CLUST-02**: AI 五层蛋糕分类 — Application / Model / Infrastructure / Chip / Energy 五层分类映射
- [ ] **CLUST-03**: Cluster summary — 每个 cluster 生成 2-3 段落综合摘要

### Daily Report (REPORT)

- [ ] **REPORT-01**: `feedship report --template <name> --since <date> --until <date>` — 生成结构化日报
- [ ] **REPORT-02**: 日期范围过滤 — 仅包含 --since/--until 范围内发布的文章
- [ ] **REPORT-03**: Jinja2 模板系统 — 模板文件在 `~/.config/feedship/templates/`，支持用户自定义模板
- [ ] **REPORT-04**: 模板结构 — 支持 H1/H2/H3 多级标题，每个 section 包含：单句摘要 + 来源列表 + B节专属字段
- [ ] **REPORT-05**: Section B 专属字段 — 「降维打击点」「靶向案例」「需求本质」「技术底座」「MVP SOP」等字段，来源：文章内容提取 + AI 自由推理
- [ ] **REPORT-06**: Report 输出 — 支持 `--output <file>` 保存为 Markdown 文件，`--json` 输出结构化 JSON
- [ ] **REPORT-07**: 模板扩展 — AI 可为未预见的分类自动扩展模板

### CLI Integration (CLI)

- [ ] **CLI-01**: Progress bar — Rich Progress 显示处理进度，支持 batch 操作
- [ ] **CLI-02**: Error handling — 单篇失败不影响整体，错误汇总报告
- [ ] **CLI-03**: `--dry-run` — 预览会处理哪些文章，不实际调用 LLM

## v2 Requirements

### Advanced Features

- **ADV-01**: Chain-of-thought quality prompting — 带置信度的 quality scoring
- **ADV-02**: Self-verification prompts — LLM 自我验证摘要准确性
- **ADV-03**: Topic trend analysis — 跨时间维度的热点趋势分析
- **ADV-04**: Export to Obsidian/Notion — 日报导出集成

## Out of Scope

| Feature | Reason |
|---------|--------|
| LangChain/LlamaIndex integration | 过度工程，简单场景不需要 |
| Real-time LLM chat | CLI 工具，非对话界面 |
| 多语言翻译 | 非核心需求，可后续扩展 |
| 视频/音频内容处理 | 当前 RSS 不支持 |
| 社交分享功能 | 非核心，CLI 场景不需要 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 20 | Pending |
| INFRA-02 | Phase 20 | Pending |
| INFRA-03 | Phase 20 | Pending |
| INFRA-04 | Phase 20 | Pending |
| INFRA-05 | Phase 20 | Pending |
| INFRA-06 | Phase 20 | Pending |
| STOR-01 | Phase 21 | Pending |
| STOR-02 | Phase 21 | Pending |
| STOR-03 | Phase 21 | Pending |
| SUMM-01 | Phase 22 | Pending |
| SUMM-02 | Phase 22 | Pending |
| SUMM-03 | Phase 22 | Pending |
| SUMM-04 | Phase 22 | Pending |
| SUMM-05 | Phase 22 | Pending |
| SUMM-06 | Phase 22 | Pending |
| QUAL-01 | Phase 22 | Pending |
| QUAL-02 | Phase 22 | Pending |
| QUAL-03 | Phase 22 | Pending |
| QUAL-04 | Phase 22 | Pending |
| KEYW-01 | Phase 22 | Pending |
| KEYW-02 | Phase 22 | Pending |
| KEYW-03 | Phase 22 | Pending |
| CLI-01 | Phase 22 | Pending |
| CLI-02 | Phase 22 | Pending |
| CLI-03 | Phase 22 | Pending |
| CLUST-01 | Phase 23 | Pending |
| CLUST-02 | Phase 23 | Pending |
| CLUST-03 | Phase 23 | Pending |
| REPORT-01 | Phase 23 | Pending |
| REPORT-02 | Phase 23 | Pending |
| REPORT-03 | Phase 23 | Pending |
| REPORT-04 | Phase 23 | Pending |
| REPORT-05 | Phase 23 | Pending |
| REPORT-06 | Phase 23 | Pending |
| REPORT-07 | Phase 23 | Pending |

**Coverage:**
- v1 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-07*
*Last updated: 2026-04-07 after v1.11 roadmap created*
