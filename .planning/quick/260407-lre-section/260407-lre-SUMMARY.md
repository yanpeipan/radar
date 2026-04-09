# Quick Task 260407-lre-section: 删除精选推荐 section

**Date:** 2026-04-07
**Status:** Completed

## Summary

Removed 精选推荐 section from feedship-ai-daily skill, reducing from 6 sections (A-F) to 5 sections (A-E).

## Changes

1. **description** - Updated to reflect 5-section digest: (A) AI五层蛋糕, (B) 创业信号, (C) 创作点, (D) 政策解读, (E) 媒体热点
2. **Step 3** - Removed Step 3a (精选推荐), renumbered all remaining steps
3. **Report format table** - Removed 精选推荐 row, shifted B→A, C→B, D→C, E→D
4. **Section count** - Changed from "exactly 6 sections (A–F)" to "exactly 5 sections (A–E)"
5. **Cron message** - Updated A-F reference to A-E
6. **Version** - Bumped to 1.17.0
7. **Changelog** - Added 1.17.0 entry

## Commit

`f0d86b2` - feat(feedship-ai-daily): remove 精选推荐 section, reduce to 5 sections
