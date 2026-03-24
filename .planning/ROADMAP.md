# Roadmap: Personal Information System

## Milestones

- [x] **v1.0 MVP** — Phases 1-3 (shipped 2026-03-22)
- [x] **v1.1 GitHub Monitoring + Tagging** — Phases 4-8 (shipped 2026-03-23)
- [x] **v1.2 Article List Enhancements** — Phases 8.1-11 (shipped 2026-03-23)
- [x] **v1.3 Provider Architecture** — Phases 12-15 (shipped 2026-03-23)

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

<details>
<summary>✅ v1.3 Provider Architecture (Phases 12-15) — SHIPPED 2026-03-23</summary>

- [x] Phase 12: Provider Core Infrastructure (2/2 plans) — completed 2026-03-23
- [x] Phase 13: Provider Implementations + Tag Parsers (2/2 plans) — completed 2026-03-23
- [x] Phase 14: CLI Integration (3/3 plans) — completed 2026-03-23
- [x] Phase 15: PyGithub Refactor (2/2 plans) — completed 2026-03-23

</details>

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
| 14. CLI Integration | 3/3 | Complete    | 2026-03-23 |
| 15. PyGithub Refactor | 2/2 | Complete    | 2026-03-23 |

### Phase 16: github_release_provider using pygithub repo.get_latest_release

**Goal:** Create a GitHubReleaseProvider using PyGithub's repo.get_latest_release() to fetch release information
**Requirements**: (none mapped)
**Depends on:** Phase 15 (PyGithub Refactor)
**Plans:** 1/1 plans complete

Plans:
- [x] 16-01-PLAN.md — Create GitHubReleaseProvider (priority 200) and ReleaseTagParser

### Phase 17: Anti-屎山 Refactoring

**Goal:** Implement Phase 2 of docs/feed.md target architecture — split cli.py, fix feed_meta(), adopt DB context manager
**Requirements**: (none mapped)
**Depends on:** None
**Plans:** 2/2 plans created

Plans:
- [x] 17-01-PLAN.md — CLI package split (cli.py → cli/)
- [x] 17-02-PLAN.md — DB context manager + feed_meta fix

---
_For completed milestone details, see `.planning/milestones/`_
