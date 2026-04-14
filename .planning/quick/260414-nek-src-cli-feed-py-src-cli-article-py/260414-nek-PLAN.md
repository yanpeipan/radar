---
name: 260414-nek
description: 使用最佳实践，合理的代码结构、精简以下代码：src/cli/feed.py, src/cli/article.py
type: quick
status: completed
commit: e38f832
date: 2026-04-14
quick_id: 260414-nek

must_haves:
  - 移除 feed.py 中未使用的 _fetch_with_progress 函数
  - feed.py 中 cProfile/io/pstats 改为 lazy import
  - 提取 _build_feed_meta 消除 FeedMetaData 重复构造
  - cli import 移至顶部而非中间
  - article.py 中 datetime/get_timezone 移至模块级
  - _print_content_view 移至使用处之前而非文件末尾
---

## Task 1: Refactor src/cli/feed.py

**files:**
- src/cli/feed.py

**action:**
1. 移除未使用的 `_fetch_with_progress` 异步函数 (lines 53-60)
2. 将 `cProfile`, `io`, `pstats` 改为 lazy import 到 `if profile:` 块内
3. 提取 `_build_feed_meta(feed)` helper 函数消除3处重复的 `FeedMetaData(...)` 构造
4. 将 `from src.cli import cli` 从 line 95 移至顶部与其他 imports 一起

**verify:**
- `git diff src/cli/feed.py` shows only structural changes
- No functionality changed

**done:** true

---

## Task 2: Refactor src/cli/article.py

**files:**
- src/cli/article.py

**action:**
1. 将 `datetime` 和 `get_timezone` imports 从 `_format_date()` 函数内部移至模块级
2. 将 `_print_content_view` 从文件底部移至 `article_view` 命令定义之前

**verify:**
- `git diff src/cli/article.py` shows clean reorganization
- No functionality changed

**done:** true
