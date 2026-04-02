# Roadmap: Feedship

## Milestones

- **v1.2** — Twitter/X via Nitter + CLI JSON Output (shipped 2026-04-02)
  - Phases: Nitter Provider, CLI JSON Output
  - See: `.planning/milestones/v1.2-ROADMAP.md`

---

## Current Milestone: v1.3 全面优化重构版

**Goal:** 系统性优化 — 从原则到框架到代码到性能

### Requirements

| REQ-ID | Description | Phase |
|--------|-------------|-------|
| PERF-01 | Batch Article Upsert | 3 |
| PERF-02 | Covering Index on (feed_id, published_at) | 3 |
| PERF-03 | Profiling Infrastructure | 3 |
| RESL-01 | Per-Domain TokenBucket Rate Limiter | 4 |
| RESL-02 | ETag/Last-Modified Conditional Fetch (304) | 4 |
| RESL-03 | Circuit Breaker Per Provider | 4 |
| TYPE-01 | Pydantic Settings for Configuration | 5 |
| TYPE-02 | Typed Feed/Article Models with Validators | 5 |
| TYPE-03 | Typed FeedMetadata Replacing JSON String | 5 |
| SEC-01 | Security Scanning in CI | 6 |
| SEC-02 | Feed Size Limits Before Parsing | 6 |
| SEC-03 | Memory Guard for Embedding Generation | 6 |
| SEC-04 | XML Entity Depth Validation | 6 |
| GROUP-01 | Add group field to Feed model | 7 |
| GROUP-02 | Add group column to feeds table | 7 |
| GROUP-03 | CLI --group option on feed add | 7 |
| GROUP-04 | CLI --group filter on feed list | 7 |

---

## Phase Summary

- [x] **Phase 3: SQLite Batch Operations & Profiling** — Fix N+1 query pattern, add profiling infrastructure
- [ ] **Phase 4: HTTP Resilience & Rate Limiting** — Prevent IP bans, enable graceful degradation
- [x] **Phase 5: Type Safety & Configuration Validation** — Catch config errors at startup, prevent data corruption (completed 2026-04-02)
- [x] **Phase 6: Security Hardening & Graceful Degradation** — Protect against malicious feeds, automated vulnerability detection (completed 2026-04-02)
- [x] **Phase 7: Feed Grouping** — Add group/labels to feeds for organization (completed 2026-04-02)

---

## Phase Details

### Phase 3: SQLite Batch Operations & Profiling

**Goal:** Fix N+1 query pattern, add profiling infrastructure

**Depends on:** None (first phase of v1.3)

**Requirements:** PERF-01, PERF-02, PERF-03

**Success Criteria** (what must be TRUE):
1. Multiple articles from a single feed fetch are stored in a single database transaction (not N individual calls)
2. Feed article queries use covering index `idx_articles_feed_published` for improved performance
3. `py-spy` can profile feed fetching operations to identify bottlenecks
4. Baseline benchmarks exist for feed fetching and article storage operations

**Plans:**
1/1 plans complete
- [x] 03-02-PLAN.md — Profiling infrastructure (Wave 2)

---

### Phase 4: HTTP Resilience & Rate Limiting

**Goal:** Prevent IP bans, enable graceful degradation during network issues

**Depends on:** Phase 3

**Requirements:** RESL-01, RESL-02, RESL-03

**Success Criteria** (what must be TRUE):
1. Fetching multiple feeds from the same domain respects TokenBucket rate limits (default 10 req/min)
2. When a feed has not changed (304 Not Modified), no article parsing occurs and bandwidth is saved
3. When a provider fails repeatedly, circuit breaker opens and other providers continue working
4. Rate limit events and circuit breaker state changes are logged for debugging

**Plans:**
1/2 plans executed
- [ ] 04-PLAN.md (Wave 2: 304 handling) — RESL-02 for Nitter/Webpage
- [ ] 04-PLAN.md (Wave 3: Circuit breaker integration) — RESL-03 in fetch_one_async

---

### Phase 5: Type Safety & Configuration Validation

**Goal:** Catch configuration errors at startup, prevent data corruption

**Depends on:** Phase 4

**Requirements:** TYPE-01, TYPE-02, TYPE-03

**Success Criteria** (what must be TRUE):
1. Misconfigured settings produce clear error messages at application startup (not random runtime failures)
2. Invalid feed data (titles too long, malformed URLs, unparseable dates) raises validation errors
3. FeedMetadata is stored as a typed Pydantic model, not a raw JSON string
4. IDE autocomplete works for configuration fields and model attributes

**Plans:** 1/1 plans complete

---

### Phase 6: Security Hardening & Graceful Degradation

**Goal:** Protect against malicious feeds, automated vulnerability detection

**Depends on:** Phase 5

**Requirements:** SEC-01, SEC-02, SEC-03, SEC-04

**Success Criteria** (what must be TRUE):
1. CI pipeline fails when pull requests introduce high or critical security vulnerabilities (bandit, pip-audit)
2. Feeds larger than 10MB are rejected before parsing; feeds with more than 1000 entries are truncated
3. When system memory exceeds 80%, embedding generation is skipped with logged warnings
4. XML entity expansion is limited to depth 100, preventing billion-laughs attacks

**Plans:** 1/1 plans complete
- [x] 06-PLAN.md — Security hardening (SEC-01, SEC-02, SEC-03, SEC-04)

### Phase 7: feed增加分组（group）功能，可以在add的时候指定，并保存到feeds表中

**Goal:** Add group/labels to feeds so users can organize feeds into categories. Users can specify a group when adding a feed via `--group` flag, and filter feeds by group in `feed list`.

**Depends on:** Phase 6

**Requirements:** GROUP-01, GROUP-02, GROUP-03, GROUP-04

**Success Criteria** (what must be TRUE):
1. User can add a feed with `--group` flag to specify group
2. User can list feeds filtered by `--group` exact match
3. User can see group column in feed list output
4. Existing feeds without group have NULL group
5. Group names are free-form text up to 100 characters

**Plans:** 1/1 plans complete
- [x] 07-PLAN.md — Add group functionality (6 tasks: DB migration, model, storage, business logic, CLI add, CLI list)

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 3. SQLite Batch Operations & Profiling | 1/1 | Complete   | 2026-04-02 |
| 4. HTTP Resilience & Rate Limiting | 1/2 | In Progress|  |
| 5. Type Safety & Configuration Validation | 1/1 | Complete   | 2026-04-02 |
| 6. Security Hardening & Graceful Degradation | 1/1 | Complete   | 2026-04-02 |
| 7. Feed Grouping | 1/1 | Complete    | 2026-04-02 |
