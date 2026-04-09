# Quick Task 260409-pg8: 去掉所有v2 - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Task Boundary

统一使用v2（cluster-first pipeline），命名去掉v2标志。
将 `cluster_articles_for_report_v2` 改名为 `cluster_articles_for_report`，`render_report_v2` 改名为 `render_report`。

</domain>

<decisions>
## Implementation Decisions

### 函数重命名
- `cluster_articles_for_report_v2` → `cluster_articles_for_report`
- `render_report_v2` → `render_report`
- 内部函数 `_cluster_articles_v2_async` → `_cluster_articles_async`

### 影响范围
- 有其他模块导入这些函数，需要同步修改
- src/cli/report.py
- src/llm/evaluator.py
- tests/test_report.py

### 命名策略
- 所有 v2 标志都去掉
- 保持功能不变，只改名称

### Claude's Discretion
- 所有 v1 相关代码已在上一轮移除，现在只有 v2 代码
- 不需要保留向后兼容

</decisions>

<specifics>
## Specific Ideas

搜索所有 `cluster_articles_for_report_v2` 和 `render_report_v2` 的引用：
- src/application/report.py（定义处）
- src/cli/report.py（导入和使用处）
- src/llm/evaluator.py（导入和使用处）
- tests/test_report.py（测试处）

</specifics>

<canonical_refs>
## Canonical References

[No external specs — requirements fully captured in decisions above]

</canonical_refs>
