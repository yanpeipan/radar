---
gsd_state_version: 1.0
milestone: v1.11
milestone_name: milestone
status: completed
last_updated: "2026-04-15T12:15:19.204Z"
last_activity: "2026-04-15 - Completed quick task 260415-s0i: 优化提示词INSIGHT_PROMPT，融合4步战略分析框架"
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 4
  completed_plans: 4
  percent: 100
---

# State: Feedship

**Milestone:** v1.11 — LLM 智能报告生成
**Project:** Feedship - Python RSS Reader CLI Tool
**Updated:** 2026-04-08

## Current Position

Phase: 23 (Report Generation) — Complete
Plan: 23-PLAN.md
Status: Implementation complete
Last activity: 2026-04-16 - Completed quick task 260416-k6h: InsightChain 拆分为两部分，1. 递归cluster,  2. 对每个递归的cluster 执行Insight

## Current Milestone: v1.11 — LLM 智能报告生成

**Goal:** 引入 LLM，为订阅源生成带结构化模板的 AI 日报

**Target features:**

- `feedship summarize --url/--id/--group --force`
- `feedship report --template xxx --since --until`
- Quality scoring (0-1)
- 关键词提取 + tags (SQLite + ChromaDB)
- 主题聚类
- 混合 LLM (Ollama + OpenAI/Azure)

**Last shipped:** v1.10 — article view 增强 (SHIPPED 2026-04-06)

## Phases

| Phase | Name | Status |
|-------|------|--------|
| 20 | LLM Infrastructure | ✅ Complete |
| 21 | Storage Extension | ✅ Complete |
| 22 | Summarization Commands | ✅ Complete |
| 23 | Report Generation | ✅ Complete |

## Quick Tasks Completed

| 2026-04-15 | fast | --json 模式保存 .md 并在 JSON 里返回 file_path | ✅ |
| 260413-1wt | 修改TLDRChain: 去掉top_n过滤，所有clusters生成TLDR；batch调用时取每个cluster的top_n个article，用CEO+AI新闻分析师视角详细总结深度挖掘 | 2026-04-12 | 0456714 | Verified | [260413-1wt-tldrchain-top-n-clusters-tldr-batch-clus](./quick/260413-1wt-tldrchain-top-n-clusters-tldr-batch-clus/) |
| 260413-2k9 | 补充report的相关文档 | 2026-04-12 | f5714c6 | Verified | [260413-2k9-report](./quick/260413-2k9-report/) |
| 260413-3hm | 调研langchain-litellm最佳实践，重构LLM调用代码 | 2026-04-12 | 7ab6932 | Verified | [260413-3hm-langchain-litellm-llm](./quick/260413-3hm-langchain-litellm-llm/) |
| 260413-3x9 | 重构_get_llm_wrapper并移动到core.py，使用ChatLiteLLMRouter | 2026-04-12 | fedb6b9 | Verified | [260413-3x9-...](./quick/260413-3x9-get-llm-wrapper-core-py-chatlitellmroute/) |
| 260413-02d | BuildReportDataChain 直接接受 HeadingNode，移除 ReportDataAdapter | 2026-04-12 | | | [260413-02d...](./quick/260413-02d-buildreportdatachain-headingnode/) |
| 260413-65n | src/llm/evaluator.py 删除 | 2026-04-12 | 3f57914 | | [260413-65n-src-llm-evaluator-py](./quick/260413-65n-src-llm-evaluator-py/) |
| 260413-8et | Optimize duplicate code and database connection handling | 2026-04-13 | d0d6384 | Verified | [260413-8et-optimize-duplicate-code-and-database-con](./quick/260413-8et-optimize-duplicate-code-and-database-con/) |
| 260413-90j | LangChain LCEL optimization + report module refactor: event loop fix, write lock consolidation, LCEL factories, streaming dedup, retry wrapper | 2026-04-13 | 2b69802 | Verified | [260413-90j-langchain-gitnexus-report](./quick/260413-90j-langchain-gitnexus-report/) |
| 260413-nco | 调研LangChain文档并提出重构BatchClassifyChain最佳方案：RunnableLambda工厂模式替换类，保留LLMWrapper重试逻辑 | 2026-04-13 | 2d051e5 | Verified | [260413-nco-https-www-langchain-com-cn-docs-how-to-b](./quick/260413-nco-https-www-langchain-com-cn-docs-how-to-b/) |
| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|
| 260407-tbk | 为 feedship fetch --url 添加端到端测试 | 2026-04-07 | c5a80e0 | | [260407-tbk-feedship-fetch-url](./quick/260407-tbk-feedship-fetch-url/) |
| 260407-m4s | 实现修改feed功能：调整权重，修改分组，补充meta等等 | 2026-04-07 | 2c90033 | | [260407-m4s-feed-meta](./quick/260407-m4s-feed-meta/) |
| 260408-1rz | LLM重构+LangChain+Report自包含+质量优化 | 2026-04-07 | 2563e77 | | [260408-1rz-llm-langchain-report](./quick/260408-1rz-llm-langchain-report/) |
| 260408-jgw | 100次迭代报告质量评估+增强evaluator | 2026-04-08 | 637109b | | [260408-jgw-100](./quick/260408-jgw-100/) |
| 260408-l0b | 完整使用LangChain — LCEL chains接入report生成 | 2026-04-08 | 4630503 | | [260408-l0b-langchain-lcel-chains-report](./quick/260408-l0b-langchain-lcel-chains-report/) |
| 260408-lp2 | AI架构师+新闻记者视角report质量优化10项修复 | 2026-04-08 | 8a8c8d0 | | [260408-lp2-ai-report-10](./quick/260408-lp2-ai-report-10/) |
| 260410-fju | github lint Error: Unable to resolve action `anchore/grype@latest` | 2026-04-10 | c5beb23 | Verified | [260410-fju-github-lint-error-unable-to-resolve-acti](./quick/260410-fju-github-lint-error-unable-to-resolve-acti/) |
| 260409-20c | 优化 report pipeline：每簇分类而非每篇分类，降低 LLM 调用次数 | 2026-04-08 | a84ec4f | [260409-20c-report-pipeline-llm](./quick/260409-20c-report-pipeline-llm/) |
| 260409-3a7 | 修复 report.py 3个高优先级asyncio问题 + centroids索引bug | 2026-04-09 | 5cc1084 | [260409-3a7-ai-report-ai](./quick/260409-3a7-ai-report-ai/) |
| 260408-mks | report增加翻译流程，--language指定最终报告语言 | 2026-04-08 | 8731675 | [260408-mks-report-language](./quick/260408-mks-report-language/) |
| 260408-o21 | 实现 report v2 模板数据结构 | 2026-04-08 | 998db43 | [260408-o21-report-v2](./quick/260408-o21-report-v2/) |
| 260408-p1q | loop 50次迭代测试report命令 | 2026-04-08 | 998db43 | — |
| 260408-sfv | report自动保存markdown到~/.local/share/feedship/reports/ | 2026-04-08 | 70cc58f | [260408-sfv-report-markdown](./quick/260408-sfv-report-markdown/) |
| 260408-uf8 | 大规模去重+话题聚类+智能摘要生成 | 2026-04-08 | 4b49dfe | [260408-uf8-dedup-cluster](./quick/260408-uf8-dedup-cluster/) |
| 260409-pg8 | 去掉所有v2命名，统一使用cluster-first pipeline | 2026-04-09 | 060a3ac | [260409-pg8-v2](./quick/260409-pg8-v2/) |
| 260409-pou | 运行report命令、解决异常、评估新闻质量 | 2026-04-09 | e1c7da5 | [260409-pou-report](./quick/260409-pou-report/) |
| 260416-k6h | InsightChain 拆分为两部分，1. 递归cluster,  2. 对每个递归的cluster 执行Insight | 2026-04-16 | d9ec445 | [260416-k6h-insightchain-1-cluster-2-cluster-insight](./quick/260416-k6h-insightchain-1-cluster-2-cluster-insight/) |
| 260409-qbr | 修复日报质量问题（链接、聚合、翻译诊断） | 2026-04-09 | — | [260409-qbr-fix-report](./quick/260409-qbr-fix-report/) |
| 260409-r5y | 最终日报不完整，没有翻译 | 2026-04-09 | 2e5103f | [260409-r5y-ultimate-report-incomplete-no-translation](./quick/260409-r5y-ultimate-report-incomplete-no-translation/) |
| 260409-sv2 | 合并topic_title和classify_cluster_layer为一次LLM调用 | 2026-04-09 | 9f24fc1 | [260409-sv2](./quick/260409-sv2/) |
| 260409-ty1 | 去重前置+批量摘要优化 | 2026-04-09 | ff01c9e | [260409-ty1](./quick/260409-ty1/) |
| 260410-qgc | 使用 litellm Router 配置 minimax 模型 | 2026-04-10 | 21712b0 | | [260410-qgc-litellm-router-minimax](./quick/260410-qgc-litellm-router-minimax/) |
| 260410-qux | 精简 src/llm/core.py 代码 | 2026-04-10 | 837fc9e | ✅ | [260410-qux-src-llm-core-py](./quick/260410-qux-src-llm-core-py/) |
| 260410-wx0 | Report P0 LLM resilience: NER + EntityTopic chain retry | 2026-04-10 | f655624 | Verified | [260410-wx0-report-p0-p1-llm-resilience-pipeline](./quick/260410-wx0-report-p0-p1-llm-resilience-pipeline/) |
| 260411-27t | 把 deduplicate_articles 接到 list_articles 和 SignalFilter 之间 | 2026-04-11 | 4acb631 | | [260411-27t-deduplicate-articles-list-articles-signa](./quick/260411-27t-deduplicate-articles-list-articles-signa/) |
| 260411-0sg | 梳理report逻辑架构并计算3333篇新闻LLM调用次数，激活AI架构师给出完整优化方案 | 2026-04-10 | faadc78 | Verified | [260411-0sg-report-3333-llm](./quick/260411-0sg-report-3333-llm/) |
| 260411-11i | 移除逐条标题翻译，改为最终报告一次性翻译，大幅减少LLM调用 | 2026-04-10 | d510140 | ✅ | [260411-11i-llm](./quick/260411-11i-llm/) |
| 260411-2z5 | 清空废弃代码 - 删除 src/llm/chains.py 中5个废弃 chain 函数 | 2026-04-10 | 7e0ac9d | Verified | [260411-2z5-clear-deprecated-chains](./quick/260411-2z5-clear-deprecated-chains/) |
| 260411-3cc | 修复 NER/EntityTopic JSON 解析失败，移除废弃标题翻译代码 | 2026-04-11 | 795166f | Verified | [260411-3cc-report-pipeline-ner-entitytopic-json](./quick/260411-3cc-report-pipeline-ner-entitytopic-json/) |
| 260411-42p | 参考litellm最佳实践，使用JSON格式 | 2026-04-10 | 495fae2 | Verified | [260411-42p-litellm-json-https-docs-litellm-ai-docs-](./quick/260411-42p-litellm-json-https-docs-litellm-ai-docs-/) |
| 260411-49x | 在 get_evaluate_chain()、get_entity_topic_chain()、get_tldr_chain() 启用 JSON mode | 2026-04-10 | b3ff523 | Verified | [260411-49x-get-evaluate-chain-get-entity-topic-chai](./quick/260411-49x-get-evaluate-chain-get-entity-topic-chai/) |
| 260411-4p1 | 验证、并解决所有 uv run feedship report --since 2026-04-07 --until 2026-04-10 --language zh报错 | 2026-04-10 | abefa8a | Verified | [260411-4p1-uv-run-feedship-report-since-2026-04-07](./quick/260411-4p1-uv-run-feedship-report-since-2026-04-07-/) |
| 260411-gb4 | 强制模型输出纯JSON - response_format参数应用到NER chain | 2026-04-11 | e6710dc | Verified | [260411-gb4-json-response-format-ner-chain](./quick/260411-gb4-json-response-format-ner-chain/) |
| 260411-h9z | 为所有 LLM chain 添加 Pydantic model + JsonOutputParser 严格校验 | 2026-04-11 | 83901a1 | Verified | [260411-h9z-llm-chain-pydantic-model-jsonoutputparse](./quick/260411-h9z-llm-chain-pydantic-model-jsonoutputparse/) |
| 260412-33d | 增加LLM分类pipeline | 2026-04-12 | 3dba87a | Verified | [260412-33d-llm-pipeline](./quick/260412-33d-llm-pipeline/) |
| 260412-3e6 | get_classify_translate_chain替换get_ner_chain、get_entity_topic_chain | 2026-04-12 | 55c1a0f | Verified | [260412-3e6-get-classify-translate-chain-get-ner-cha](./quick/260412-3e6-get-classify-translate-chain-get-ner-cha/) |
| 260412-3uh | 删除NERExtractor和src/application/report/ner.py | 2026-04-12 | d2e57d1 | Verified | [260412-3uh-nerextractor-src-application-report-ner-](./quick/260412-3uh-nerextractor-src-application-report-ner-/) |
| 260412-43j | 删除EntityClusterer，deduplicate后调用get_classify_translate_chain | 2026-04-12 | 28bbd85 | Verified | [260412-43j-entityclusterer-deduplicate-articles-get](./quick/260412-43j-entityclusterer-deduplicate-articles-get/) |
| 260412-4hg | 删除废弃代码：get_evaluate_chain、get_ner_chain、get_entity_topic_chain 三个函数及其所有引用 | 2026-04-11 | 4b6134e | Verified | [260412-4hg-get-evaluate-chain-get-ner-chain-get-ent](./quick/260412-4hg-get-evaluate-chain-get-ner-chain-get-ent/) |
| 260412-54h | 对filtered进行分批次调用，每批次默认50，5个并发调用get_classify_translate_chain | 2026-04-11 | b11cba7 | Verified | [260412-54h-filtered-50-5-get-classify-translate-cha](./quick/260412-54h-filtered-50-5-get-classify-translate-cha/) |
| 260412-7gy | 在templates下创建AI日报模板，解析以下，生成 Jinja2 + makrdown格式的 AI日报模板 | 2026-04-11 | 740a814 | Verified | [260412-7gy-templates-ai-jinja2-makrdown-ai](./quick/260412-7gy-templates-ai-jinja2-makrdown-ai/) |
| 2026-04-12 | fast | src/templates 移动到 上一层目录 | ✅ |
| 260412-7zy | 删除 leverage_articles、business_articles、creation_articles 相关代码 | 2026-04-12 | f6e173c | | [260412-7zy-leverage-articles-business-articles-crea](./quick/260412-7zy-leverage-articles-business-articles-crea/) |
| 260412-88j | 删除 render_entity_inline 函数 | 2026-04-12 | 9703c94 | | [260412-88j-render-entity-inline](./quick/260412-88j-render-entity-inline/) |
| 260412-9e8 | ArticleEnriched → ReportArticle 继承 ArticleListItem | 2026-04-12 | 65d45f1 | | [260412-9e8-articleenriched-reportarticle-articlelis](./quick/260412-9e8-articleenriched-reportarticle-articlelis/) |
| 260412-hjb | 删除 src/application/entity_report/entity_cluster.py | 2026-04-12 | 6a2f991 | | [260412-hjb-src-application-entity-report-entity-clu](./quick/260412-hjb-src-application-entity-report-entity-clu/) |
| 260412-htm | 删除 src/application/entity_report 整个目录 | 2026-04-12 | e8d1ae9 | | [260412-htm-src-application-entity-report](./quick/260412-htm-src-application-entity-report/) |
| 260412-hy9 | template.render() 传递 ReportData 而非分散参数 | 2026-04-12 | 0410354 | | [260412-hy9-template-render-reportdata](./quick/260412-hy9-template-render-reportdata/) |
| 260412-iku | render_report 调用改为传递 ReportData | 2026-04-12 | c855075 | | [260412-iku-render-report-reportdata](./quick/260412-iku-render-report-reportdata/) |
| 260412-in2 | _entity_report_async 返回 ReportData | 2026-04-12 | 05d2dcd | | [260412-in2-entity-report-async-reportdata](./quick/260412-in2-entity-report-async-reportdata/) |
| 260412-iyl | ReportData 增加 total_articles 属性 | 2026-04-12 | e7f558e | | [260412-iyl-reportdata-total-articles](./quick/260412-iyl-reportdata-total-articles/) |
| 2026-04-12 | fast | by_layer → clusters, EntityTopic → ReportCluster | ✅ |
| 2026-04-12 | fast | 去掉 tldr_top10/by_cluster/deep_dive | ✅ |
| 2026-04-12 | fast | total_articles 改用 reportData.total_articles | ✅ |
| 260412-xxx | 删除 LAYER_KEYS 常量及所有引用 | 2026-04-12 | d7274a0 | | — |
| 260412-jhx | src/application/report 下新增template类，处理模板相关功能 | 2026-04-12 | a84e6a2 | | [260412-jhx-src-application-report-template](./quick/260412-jhx-src-application-report-template/) |
| 2026-04-12 | fast | 在 template.py 实现 HeadingNode + parse_markdown_headings + ReportTemplate.parse() | ✅ |
| 260412-jvp | ReportTemplate 初始化绑定 template_name，render/parse 不再传参 | 2026-04-12 | 89f1f45 | | [260412-jvp-reporttemplate-template-name-render-pars](./quick/260412-jvp-reporttemplate-template-name-render-pars/) |
| 2026-04-12 | fast | parse() 改用 template source 做元分析，去掉 _rendered 缓存 | ✅ |
| 2026-04-12 | fast | cli.report 新增 --template 参数，ReportTemplate(template_name).render(data)，移除 _render_and_translate_report | ✅ |
| 2026-04-12 | fast | 移除 report.render_report | ✅ |
| 260412-ki9 | cluster_articles_for_report 新增 heading_tree 参数 | 2026-04-12 | 1f37571 | | [260412-ki9-cluster-articles-for-report-report-templ](./quick/260412-ki9-cluster-articles-for-report-report-templ/) |
| 2026-04-12 | fast | HeadingNode.titles 递归获取所有标题 | ✅ |
| 2026-04-12 | fast | HeadingNode.titles 过滤空和 non | ✅ |
| 260412-kuy | heading_tree 直接构建 clusters，移除 group_clusters | 2026-04-12 | 3cdddd9 | | [260412-kuy-heading-tree-reportcluster](./quick/260412-kuy-heading-tree-reportcluster/) |
| 2026-04-12 | fast | HeadingNode.titles 在返回前统一过滤空值 | ✅ |
| 2026-04-12 | fast | ReportArticle 增加 translation 属性 | ✅ |
| 2026-04-12 | fast | 修复 template default ai-daily → ai_daily_report | ✅ |
| 2026-04-12 | fast | 修复 template 加载: .md.j2 后缀, loader.get_source | ✅ |
| 2026-04-12 | fast | ReportArticle增加from_article方法，add_article使用from_article简化 | ✅ |
| 260412-tiz | 用report_data.add_article替换generator.py中旧的tag_groups构建逻辑 | 2026-04-12 | 97009a3 | Verified | [260412-tiz-report-data-add-article-generator-py-tag](./quick/260412-tiz-report-data-add-article-generator-py-tag/) |
| 260412-ozx | 把JSON提取逻辑移到LCEL管道里，用CustomOutputParser替换process_batch中的regex | 2026-04-12 | 44775f2 | | [260412-ozx-json-lcel-customoutputparser-process-bat](./quick/260412-ozx-json-lcel-customoutputparser-process-bat/) |
| 260412-pji | 把process_batch重构为BatchClassifyProcessor(Runnable)并链式调用（最终方案：_run_classify_batch + _build_news_list） | 2026-04-12 | a074d65 | | [260412-pji-process-batch-batchclassifyprocessor-run](./quick/260412-pji-process-batch-batchclassifyprocessor-run/) |
| 260412-r0m | 创建BatchClassifyChain类，提取分批次+并发逻辑到classify.py | 2026-04-12 | f85aa55 | | [260412-r0m-batchclassifychain-batch-classify](./quick/260412-r0m-batchclassifychain-batch-classify/) |
| 260412-rh2 | BatchClassifyChain返回enriched ArticleListItem，下游简化 | 2026-04-12 | 4ca542c | | [260412-rh2-batchclassifychain-articlelistitem-tags-](./quick/260412-rh2-batchclassifychain-articlelistitem-tags-/) |
| 260412-rwp | 重命名report_generation.py → generator.py | 2026-04-12 | 2a8e213 | | |
| 260412-s9g | ReportData增加add_article(cluster_name, item)方法 | 2026-04-12 | 9b9052c | | |
| 260412-st2 | ReportData增加get_cluster方法，递归查找内嵌ReportCluster | 2026-04-12 | a79b26e | Verified | [260412-st2-reportdata-get-cluster-reportcluster-rep](./quick/260412-st2-reportdata-get-cluster-reportcluster-rep/) |
| 260412-trg | ReportData增加add_articles和build方法，generator.py使用这两个方法 | 2026-04-12 | 52d85ac, 1417768 | | [260412-trg-add-articles-build-reportdata](./quick/260412-trg-add-articles-build-reportdata/) |
| 260412-w8x | BuildReportDataChain + TLDRChain pipeline refactor | 2026-04-12 | b4f71f7 | Verified | [260412-w8x-buildreportdatachain-tldrchain-pipeline-](./quick/260412-w8x-buildreportdatachain-tldrchain-pipeline-/) |
| 260412-x4s | BatchClassifyChain & BuildReportDataChain & TLDRChain LCEL pipe composition | 2026-04-12 | def3ec6 | | [260412-x4s-batchclassifychain-buildreportdatachain-](./quick/260412-x4s-batchclassifychain-buildreportdatachain-/) |
| 260413-02d | BuildReportDataChain 直接接受 HeadingNode，移除 ReportDataAdapter | 2026-04-13 | 77510b4 | | [260413-02d-buildreportdatachain-headingnode-reportd](./quick/260413-02d-buildreportdatachain-headingnode-reportd/) |
| 260412-u7q | Fix P0 crash (report_data initialization order) + remove EntityTag | 2026-04-12 | — | Blocked (pre-commit: B008 in models.py:59) | [260412-u7q-p0-bug-entitytag](./quick/260412-u7q-p0-bug-entitytag/) |
| 260414-nda | 增加约束：UNIQUE(link) 删除feed 里的link重复文章 | 2026-04-14 | 2251307 | Verified | [260414-nda-unique-link-feed-link](./quick/260414-nda-unique-link-feed-link/) |
| 260414-331 | report引入InsightChain(top_n=100, target_lang)取代TLDRChain：1 Cluster生成n Topics放入children；删除TLDRChain | 2026-04-13 | 951031c | Verified | [260414-331-report-chain-insightchain-top-n-100-targ](./quick/260414-331-report-chain-insightchain-top-n-100-targ/) |
| 260414-nek | 使用最佳实践，精简 src/cli/feed.py 和 src/cli/article.py | 2026-04-14 | e38f832 | Verified | [260414-nek-src-cli-feed-py-src-cli-article-py](./quick/260414-nek-src-cli-feed-py-src-cli-article-py/) |
| 260414-trc | 修改模板：cluster.children不为空优先渲染children，否则渲染cluster.articles | 2026-04-14 | 9924217 | | [260414-trc-template-render-cluster-children](./quick/260414-trc-template-render-cluster-children/) |
| 260414-nek2 | CLI不要包含业务逻辑：_build_feed_meta移至FeedMetaData，_format_date移至application层 | 2026-04-14 | 85a14c2 | Verified | [260414-nek2-src-cli-feed-py-src-cli-article-py](./quick/260414-nek2-src-cli-feed-py-src-cli-article-py/) |
| 2026-04-14 | fast | CLASSIFY_TRANSLATE_PROMPT过滤tags=[]的数据 | ✅ |
| 260414-uxw | ReportCluster 新增属性 content，name 改为 title | 2026-04-14 | cee7acd | Verified | [260414-uxw-reportcluster-content-name-title](./quick/260414-uxw-reportcluster-content-name-title/) |
| 260414-v8a | ReportData.clusters → cluster: ReportCluster，模板改为动态遍历 cluster.children | 2026-04-14 | — | Verified | [260414-v8a-reportdata-clusters-cluster-reportcluste](./quick/260414-v8a-reportdata-clusters-cluster-reportcluste/) |
| 260414-vzo | Remove BatchClassifyChain from report generation LCEL chain; route untagged articles to first heading title | 2026-04-14 | 88c0845 | Verified | [260414-vzo-remove-batchclassifychain-from-report-ge](./quick/260414-vzo-remove-batchclassifychain-from-report-ge/) |
| 260414-wjl | Fix "No articles found" issue: ReportData.build() skips rebuild when heading_tree has Jinja2 placeholders | 2026-04-14 | ca78c4f | Verified | [260414-wjl-fix-no-articles-found-issue-in-feedship-](./quick/260414-wjl-fix-no-articles-found-issue-in-feedship-/) |
| 260415-s0i | 优化提示词INSIGHT_PROMPT，融合4步战略分析框架(Surface Deconstruction/First Principles/Hidden Storylines/Value Creator) | 2026-04-15 | 5f1f883 | Verified | [260415-s0i-insight-prompt](./quick/260415-s0i-insight-prompt/) |
