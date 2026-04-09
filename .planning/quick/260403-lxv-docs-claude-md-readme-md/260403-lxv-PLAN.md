---
name: docs-reorganization
description: 分析优化整理 docs 下的所有文档，并把关键信息链接到claude.md 及 README.md
type: quick
date: 2026-04-03
quick_id: 260403-lxv
---

# Quick Plan: docs 文档整理

## 任务目标

分析并优化 docs/ 目录下的文档结构，修复 README.md 和 CLAUDE.md 中的过期链接。

## 发现的问题

1. **README.md** 引用了已删除的 `docs/cli.md`
2. **README.md** tech stack 列出了已废弃的 httpx
3. **docs/optional-dependencies.md** 和 **docs/technology-stack.md** 内容高度重复
4. **docs/providers.md** 和 **docs/feed.md** 有部分重复（provider 注册说明）
5. **docs/Search.md** 是 v2.0 搜索架构的详细设计文档，内容冗长，大部分细节应该简化或移除

## Tasks

### Task 1: 修复 README.md

**文件**: `README.md`

**操作**:
1. 将 `docs/cli.md` 链接改为 `docs/cli-commands.md`
2. 将 tech stack 中的 `httpx` 更新为 `scrapling`
3. 移除 `@docs/Automatic Discovery Feed.md` 引用（建议删除）

**验证**: `grep "cli.md\|httpx" README.md` 应无结果

---

### Task 2: 删除冗余文档

**操作**:
1. 删除 `docs/optional-dependencies.md`（内容已被 technology-stack.md 覆盖）
2. 删除 `docs/automatic-discovery-feed.md`（与 discover 命令重复）

**验证**: `ls docs/` 应不包含这两个文件

---

### Task 3: 更新 CLAUDE.md 中的文档链接

**文件**: `CLAUDE.md`

**操作**:
1. 确认 Technology Stack 部分引用的 `docs/technology-stack.md` 存在且正确
2. 更新 `docs/` 引用，确保路径与实际文件名一致

**验证**: `grep -E "docs/.*\.md" CLAUDE.md | while read f; do echo $f; done` 所有文件应存在

---

### Task 4: 简化 Search.md（可选）

**评估**: `docs/Search.md` 是 300+ 行的详细设计文档，记录了已完成的 v2.0 实现。如果这是历史文档且不再维护，考虑将其内容精简为基础使用说明。

**操作**: 将 Search.md 精简为基础搜索命令说明，移除实现细节

---

## 执行顺序

1. Task 1 (README.md) → 立即提交
2. Task 2 (删除冗余文档) → 立即提交
3. Task 3 (CLAUDE.md) → 立即提交
4. Task 4 (Search.md) → 评估后执行
