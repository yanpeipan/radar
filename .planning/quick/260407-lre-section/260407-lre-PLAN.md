---
name: "260407-lre-section"
description: "删除精选推荐 section"
date: "2026-04-07"
status: "in_progress"
---

## Plan

### Task 1: Remove 精选推荐 from metadata description
**Files:** `skills/feedship-ai-daily/SKILL.md`
**Action:** Remove 精选推荐 from the 6-section list in the description
**Verify:** `grep "精选推荐" skills/feedship-ai-daily/SKILL.md` returns nothing in description area
**Done:** When description no longer references 精选推荐

### Task 2: Remove Step 3a (精选推荐 generated last)
**Files:** `skills/feedship-ai-daily/SKILL.md`
**Action:** Delete the entire "Step 3a: Generate Section B (精选推荐)" block (the one marked "generated last")
**Verify:** No "精选推荐" step in Step 3
**Done:** When Step 3 only has 3b-3f sections

### Task 3: Update format section list and table
**Files:** `skills/feedship-ai-daily/SKILL.md`
**Action:**
- Remove 精选推荐 from the Python script section_map (section B)
- Remove 精选推荐 row from the report format table (Section A row)
- Reorder remaining sections: B→A, C→B, D→C, E→D, F→E
**Verify:** Only A-E sections remain in table and script
**Done:** When section table shows only A-E

### Task 4: Update version and changelog
**Files:** `skills/feedship-ai-daily/SKILL.md`
**Action:**
- Bump version from 1.16.0 to 1.17.0
- Update both version fields
- Add changelog entry
**Verify:** Version is 1.17.0
**Done:** When version and changelog updated

### Task 5: Commit
**Action:** `git add -A && git commit -m "feat(feedship-ai-daily): remove 精选推荐 section"`
**Verify:** Commit exists with correct message
**Done:** When committed
