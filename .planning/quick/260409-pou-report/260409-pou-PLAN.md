---
name: 260409-pou
description: 运行report命令、解决所有异常、评估新闻质量
type: quick
status: completed
date: 2026-04-09
quick_id: 260409-pou
must_haves:
  - litellm model pricing 注册修复
  - MiniMax thinking block 过滤
  - default.md 模板修复
  - report 命令运行成功
  - 新闻质量评估输出
---

## Task 1: Fix litellm model pricing

**files:**
- src/llm/core.py

**action:**
litellm 1.83.0 严格要求 model pricing。启动时注册 MiniMax-M2.7 零成本定价防止异常。

**verify:**
`uv run feedship report --since 2026-04-07 --until 2026-04-10` 不再报 model not mapped 错误

**done:**
✓

---

## Task 2: Strip MiniMax thinking blocks from LLM responses

**files:**
- src/application/report.py

**action:**
MiniMax 返回包含 <think>...</think> thinking blocks，破坏分类解析。在 classify_article_layer 和 classify_cluster_layer 中用正则去除。

**verify:**
分类不再因 thinking block 而 fallback 到 default

**done:**
✓

---

## Task 3: Fix default.md template to use v2 data structure

**files:**
- ~/.config/feedship/templates/default.md

**action:**
模板原使用 v1 变量（articles_by_layer, layer_summaries），更新为 v2 结构（layers, signals, creation）

**verify:**
模板渲染无 "'articles_by_layer' is undefined" 错误

**done:**
✓

---

## Task 4: Run report and evaluate news quality

**files:**
- 全项目

**action:**
运行完整 report 生成流程，评估输出新闻质量

**verify:**
报告成功生成到 ~/.local/share/feedship/reports/

**done:**
✓
