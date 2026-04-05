---
gsd_state_version: 1.0
milestone: v1.10
milestone_name: article view 增强
status: discussing
last_updated: "2026-04-06T00:00:00.000Z"
last_activity: "2026-04-06 -- Phase 19 context gathered (auto mode), advancing to plan-phase"
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# State: Feedship

**Milestone:** v1.10 - article view 增强
**Project:** Feedship - Python RSS Reader CLI Tool
**Updated:** 2026-04-06

## Current Position

Phase: 19 (article view 命令增强)
Plan: —
Status: Context gathered, ready for planning
Last activity: 2026-04-06 — Context captured (auto mode), advancing to plan-phase

## Current Milestone: v1.10 article view 增强

**Goal:** 增强 `feedship article view` 命令，支持 --url/--id/--json 参数，Trafilatura 最佳实践提取内容

**Status:** Planning

**Requirements:**
- VIEW-01: `article view --url <URL>` — 直接抓取 URL，Trafilatura 提取内容，返回 Markdown，不入库
- VIEW-02: `article view --id <article_id>` — 从数据库查 article，抓取 link，Trafilatura 回填 content 字段，更新数据库，返回内容
- VIEW-03: `article view --json` — JSON 格式输出（--url/--id 共用）
- VIEW-04: Trafilatura 最佳实践：output_format=markdown，include_images=False，include_tables=True

**Phase:** Phase 19

**Context:** `.planning/phases/19-article-view/19-CONTEXT.md`

## Quick Tasks Completed

(None yet)

---
