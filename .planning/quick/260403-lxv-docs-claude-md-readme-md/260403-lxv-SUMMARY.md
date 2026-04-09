# Quick Task Summary: docs 文档整理

**Quick ID**: 260403-lxv
**Date**: 2026-04-03
**Status**: Completed

## Changes Made

### 1. README.md 修复
- `docs/cli.md` → `docs/cli-commands.md` (cli.md 已删除)
- `httpx` → `scrapling` (httpx 已废弃)
- 移除 `@docs/Automatic Discovery Feed.md` 引用 (discover 命令已在 cli-commands.md 文档化)

### 2. CLAUDE.md 修复
- `docs/Architecture.md` → `docs/structure.md` (Architecture.md 不存在)
- `docs/Conventions.md` → `docs/structure.md` (Conventions.md 不存在)
- 所有 docs 引用已验证存在

### 3. 删除的文件
- `docs/cli.md` - 已合并到 cli-commands.md

## 未执行的任务

### Task 4: 简化 Search.md
**决策**: 保留 Search.md。该文件包含 v2.0 搜索架构实现细节，作为内部技术参考有价值。

### 删除 docs/optional-dependencies.md
**决策**: 保留。该文件提供用户友好的安装说明和故障排除，与 technology-stack.md 的定位不同。

## 验证

```bash
# README 无过期引用
grep -E "cli\.md|httpx" README.md  # 无结果 ✓

# 所有 CLAUDE.md docs 引用存在
docs/release.md ✓
docs/structure.md ✓
docs/technology-stack.md ✓
```

## Commit

`docs(quick-260403-lxv): 整理 docs 文档 - 修复 README.md 和 CLAUDE.md 过期链接`
