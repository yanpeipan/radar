---
name: 260409-nrf
description: 只保留v2 Cluster-first pipeline，删除v1
type: quick
status: pending
date: 2026-04-09
quick_id: 260409-nrf
must_haves:
  - v1 functions removed from report.py
  - cli/report.py updated to use only v2
  - evaluator.py updated
  - tests updated
  - all refs to v1 functions eliminated
---

## Task 1: Remove v1 from report.py

**files:**
- src/application/report.py

**action:**
删除以下 v1 函数和相关内容：
- `cluster_articles_for_report` (sync wrapper)
- `_cluster_articles_async` 
- `render_report` (async)
- `_translate_report_async`
- 相关的 LAYER_KEYS 分类逻辑

保留 v2 函数：
- `cluster_articles_for_report_v2`
- `render_report_v2`
- `_cluster_articles_v2_async`
- `_cluster_articles_into_topics`
- `classify_cluster_layer`
- `generate_cluster_summary`
- 所有翻译相关

**verify:**
grep "cluster_articles_for_report[^_]" 只返回 v2 函数

**done:**
v1 逻辑已删除

---

## Task 2: Update cli/report.py

**files:**
- src/cli/report.py

**action:**
- 删除 `cluster_articles_for_report` 和 `render_report` import
- 删除 `--template` 选项（统一用 v2）
- 删除所有 v1/v2 条件分支，统一走 v2
- 更新 filename 生成逻辑（去掉 template 名）

**verify:**
uv run feedship report --help 显示简洁的用法

**done:**
CLI 统一使用 v2

---

## Task 3: Update evaluator.py

**files:**
- src/llm/evaluator.py

**action:**
- 将 `cluster_articles_for_report` 替换为 `cluster_articles_for_report_v2`
- 将 `render_report` 替换为 `render_report_v2`

**verify:**
grep "render_report" 只有 render_report_v2

**done:**
evaluator 使用 v2

---

## Task 4: Update tests

**files:**
- tests/test_report.py

**action:**
- 删除 v1 相关测试（test_report_cli_no_articles, test_report_cli_no_articles_json_output, test_report_cli_template_error, test_report_cli_v2_template 等）
- 删除 cluster_articles_for_report 引用
- 删除 render_report 引用
- 保留 v2 测试

**verify:**
pytest tests/test_report.py -v 通过

**done:**
测试精简为纯 v2
