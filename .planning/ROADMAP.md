# Roadmap: Personal Information System

## Milestones

- [x] **v1.0 MVP** — Phases 1-3 (shipped 2026-03-22)
- [x] **v1.1 GitHub Monitoring + Tagging** — Phases 4-8 (shipped 2026-03-23)
- [x] **v1.2 Article List Enhancements** — Phases 8.1-11 (shipped 2026-03-23)
- [ ] **v1.3 Provider Architecture** — Phases 12-14 (planned)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-3) — SHIPPED 2026-03-22</summary>

- [x] Phase 1: Foundation (v1.0)
- [x] Phase 2: Search & Refresh (v1.0)
- [x] Phase 3: Web Crawling (v1.0)
  - [x] Phase 3.1: Fix httpx User-Agent (gap closure)

</details>

<details>
<summary>✅ v1.1 GitHub Monitoring + Tagging (Phases 4-8) — SHIPPED 2026-03-23</summary>

- [x] Phase 4: GitHub API Client + Releases Integration
- [x] Phase 5: Changelog Detection + Scraping
- [x] Phase 6: Unified Display + Refresh Integration
- [x] Phase 7: Tagging System
- [x] Phase 8: GitHub URL Metadata

</details>

<details>
<summary>✅ v1.2 Article List Enhancements (Phases 8.1-11) — SHIPPED 2026-03-23</summary>

- [x] Phase 8.1: Unified Feed Add (gap closure)
- [x] Phase 9: Enhanced Article List
- [x] Phase 10: Article Detail View
- [x] Phase 11: GitHub Release Tagging

</details>

### v1.3 Provider Architecture

- [x] **Phase 12: Provider Core Infrastructure** — Provider Protocol, Registry, Error Isolation, Fallback, DB migrations (completed 2026-03-23)
- [x] **Phase 13: Provider Implementations + Tag Parsers** — RSS Provider, GitHub Provider, Tag Parser chaining (completed 2026-03-23)
- [ ] **Phase 14: CLI Integration** — fetch/feed commands wired to Registry, repo command deletion

---

### Phase 12: Provider Core Infrastructure

**Goal:** Plugin architecture foundation with Provider Protocol, Registry, error isolation, fallback, and database migrations

**Depends on:** Nothing (new milestone)

**Requirements:** PROVIDER-01, PROVIDER-02, PROVIDER-03, PROVIDER-04, DB-01, DB-02, DB-03

**Success Criteria** (what must be TRUE):
1. System loads providers dynamically from `src/providers/` directory at startup, ordered by priority
2. All providers implement `ContentProvider` Protocol with `match()`, `priority()`, `crawl()`, `parse()`, `tag_parsers()`, `parse_tags()` methods
3. Single provider failure (crawl/parse exception) logs error and continues to next provider without crashing
4. Unknown URL types fall back to default RSS provider (priority=0) without errors
5. `feeds` table has `metadata` TEXT column storing JSON, `github_repos` data migrated, `github_repos` table deleted

**Plans:** 2/2 plans complete

Plans:
- [x] 12-01-PLAN.md — Provider Protocol and Registry (PROVIDER-01, PROVIDER-02, PROVIDER-03, PROVIDER-04)
- [x] 12-02-PLAN.md — Database migrations for feeds.metadata and github_repos (DB-01, DB-02, DB-03)

---

### Phase 13: Provider Implementations + Tag Parsers

**Goal:** RSS and GitHub providers implementing ContentProvider interface, with tag parser chaining

**Depends on:** Phase 12

**Requirements:** PROVIDER-05, PROVIDER-06, TAG-01, TAG-02

**Success Criteria** (what must be TRUE):
1. RSS Provider handles RSS/Atom feeds with priority=50, wrapping existing feeds.py logic
2. GitHub Provider handles GitHub URLs with priority=100, wrapping existing github.py logic
3. Tag parser chaining runs multiple TagParsers and returns union with duplicates removed
4. Default tag parser applies existing tag_rules.py logic for auto-tagging

**Plans:** 2/2 plans complete

Plans:
- [x] 13-01-PLAN.md — RSS and GitHub providers implementing ContentProvider (PROVIDER-05, PROVIDER-06)
- [x] 13-02-PLAN.md — Tag parser registry and DefaultTagParser (TAG-01, TAG-02)

---

### Phase 14: CLI Integration

**Goal:** CLI commands use Provider Registry for unified feed management

**Depends on:** Phase 13

**Requirements:** CLI-01, CLI-02, CLI-03, CLI-04

**Success Criteria** (what must be TRUE):
1. `fetch --all` iterates all providers via ProviderRegistry and calls crawl + parse for each
2. `feed add <url>` auto-detects provider type via ProviderRegistry.discover() without user specifying type
3. `repo add`, `repo list`, `repo remove`, `repo refresh` commands are deleted (统一到 feed 命令)
4. `feed list` output includes provider_type column showing "RSS" or "GitHub"

**Plans:** 3/3 plans

Plans:
- [ ] 14-01-PLAN.md — fetch --all via ProviderRegistry (CLI-01)
- [ ] 14-02-PLAN.md — feed add/list via ProviderRegistry + provider_type display (CLI-02, CLI-04)
- [ ] 14-03-PLAN.md — Delete repo command group (CLI-03)

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | Complete | ✅ | 2026-03-22 |
| 2. Search & Refresh | Complete | ✅ | 2026-03-22 |
| 3. Web Crawling | Complete | ✅ | 2026-03-22 |
| 4. GitHub API Client | Complete | ✅ | 2026-03-23 |
| 5. Changelog Detection | Complete | ✅ | 2026-03-23 |
| 6. Unified Display | Complete | ✅ | 2026-03-23 |
| 7. Tagging System | Complete | ✅ | 2026-03-23 |
| 8. GitHub URL Metadata | Complete | ✅ | 2026-03-23 |
| 8.1 Unified Feed Add | 2/2 | ✅ Complete | 2026-03-23 |
| 9. Enhanced Article List | 1/1 | ✅ Complete | 2026-03-23 |
| 10. Article Detail View | 1/1 | ✅ Complete | 2026-03-23 |
| 11. GitHub Release Tagging | 1/1 | ✅ Complete | 2026-03-23 |
| 12. Provider Core Infrastructure | 2/2 | Complete    | 2026-03-23 |
| 13. Provider Implementations | 2/2 | Complete    | 2026-03-23 |
| 14. CLI Integration | 0/3 | Not started | - |

---
_For completed milestone details, see `.planning/milestones/`_
