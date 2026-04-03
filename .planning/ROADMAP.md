# Roadmap: Feedship

## Milestones

- **v1.5 Info Command** - Phase 1 (in progress)
- **v1.4 Patch Releases** - Complete (v1.4.4)
- **v1.3 Optimization** - Complete
- **v1.2 Twitter/X via Nitter** - Complete (v1.2.5)
  - Phases: Nitter Provider, CLI JSON Output
  - See: `.planning/milestones/v1.2-ROADMAP.md`

---

## Current Milestone: v1.5 Info Command

**Goal:** Add `info` CLI command for diagnostics and introspection

### Requirements

| REQ-ID | Description | Phase |
|--------|-------------|-------|
| INFO-01 | Version display from importlib.metadata | 1 |
| INFO-02 | Config path display using platformdirs | 1 |
| INFO-03 | Config values display from _get_settings() | 1 |
| INFO-04 | Storage path display using get_db_path() | 1 |
| INFO-05 | Storage stats (article count, feed count, DB size) | 1 |
| INFO-06 | JSON output with --json flag | 1 |
| INFO-07 | Filter flags (--version, --config, --storage) | 1 |

---

## Phase Summary

- [ ] **Phase 1: Info Command MVP** - CLI command for diagnostics and introspection

---

## Phase Details

### Phase 1: Info Command MVP

**Goal:** Users can view version, config, and storage information via CLI

**Depends on:** Nothing (first phase of v1.5)

**Requirements:** INFO-01, INFO-02, INFO-03, INFO-04, INFO-05, INFO-06, INFO-07

**Success Criteria** (what must be TRUE):
1. User can run `feedship info` and see version, config path, config values, storage path, and storage stats
2. User can run `feedship info --version` and see only the version string
3. User can run `feedship info --config` and see only config path and all config values
4. User can run `feedship info --storage` and see only storage path and storage statistics
5. User can run `feedship info --json` and get machine-readable JSON output
6. User can combine filter flags with `--json` to get filtered JSON output

**Plans:** 1 plan

Plans:
- [x] 09-01-PLAN.md — Create `feedship info` CLI command with --version, --config, --storage, --json flags

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Info Command MVP | 0/1 | Planning complete | - |

---

## Prior Milestone Progress (v1.3 & v1.4)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 3. SQLite Batch Operations & Profiling | 1/1 | Complete   | 2026-04-02 |
| 4. HTTP Resilience & Rate Limiting | 1/2 | In Progress|  |
| 5. Type Safety & Configuration Validation | 1/1 | Complete   | 2026-04-02 |
| 6. Security Hardening & Graceful Degradation | 1/1 | Complete   | 2026-04-02 |
| 7. Feed Grouping | 1/1 | Complete    | 2026-04-02 |
| 8. Article/Search Group Filtering | 1/1 | Complete   | 2026-04-02 |
