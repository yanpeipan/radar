---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: provider-architecture
status: Defining requirements
last_updated: "2026-03-23"
---

# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** 用户能够在一个地方集中管理所有资讯来源，无需逐一访问各个网站。
**Current focus:** Phase 12 — Provider Architecture (planning)

## Current Position

Phase: Not started (defining requirements)
Plan: —

## Performance Metrics

**v1.0 velocity:**

- 3 phases, 9 plans, ~3 hours

**v1.1 velocity:**

- 4 phases, 10 plans, ~1 day

**v1.2 velocity:**

- 4 phases, 5 plans, ~1 day

**v1.3 (current):**

- Provider architecture refactor

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.

### Technical Notes

**Provider Architecture (v1.3):**

- Plugin directory: `src/providers/` and `src/tags/`
- Discovery: `glob()` + dynamic import, alphabetical order
- Rule: Providers must not import each other (avoid circular deps)
- Provider interface: match/priority/crawl/parse/tag_parsers/parse_tags
- Crawl failure: log.error and continue to next provider
- Tag merging: union of all tag parsers, deduplicated
- Default RSS: match() returns False, only used as fallback
- Database: feeds.metadata JSON field for provider-specific data
- github_repos table to be dropped after migration

### Blockers/Concerns

None identified.

## Session Continuity

Last session: 2026-03-23
Stopped at: v1.3 milestone started
