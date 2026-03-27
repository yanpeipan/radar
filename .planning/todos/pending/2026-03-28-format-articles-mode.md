---
created: 2026-03-28T14:15:00Z
title: 重构 format_articles 脏代码，统一 mode 分支处理
area: search
files:
  - src/application/search.py:39-74
---

## Problem

`format_articles` 函数使用 if/elif/elif 硬编码分支处理不同 mode：

```python
if mode == "list":
    return _format_list_items(items, verbose)
elif mode == "fts":
    return _format_fts_items(items, verbose)
elif mode == "semantic":
    return _format_semantic_items(items, verbose)
```

每个分支返回不同的硬编码字符串作为 score 字段（"LIST"、"FTS"），而不是统一的 ArticleListItem 接口。

## Solution

TBD

需要分析：
1. `_format_list_items`、`_format_fts_items`、`_format_semantic_items` 的差异是否真的只是硬编码的 "LIST"/"FTS" 字符串
2. 如果逻辑一致，应该统一为一个函数，或者让每个格式化函数都接受 dict 输入（rank_*_results 已返回 dict）
3. 移除硬编码的 score 字符串，统一使用 0-1 的 score 值（通过 rank_*_results 函数添加）
