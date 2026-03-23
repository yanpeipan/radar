# Roadmap: Personal Information System

## Milestones

- ✅ **v1.0 MVP** — Phases 1-3 (shipped 2026-03-22)
- ✅ **v1.1 GitHub Monitoring + Tagging** — Phases 4-8 (shipped 2026-03-23)
- ✅ **v1.2 Article List Enhancements** — Phases 8.1-11 (shipped 2026-03-23)
- ⏳ **v1.3** — (planned)

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

### v1.3 (Planned)


**Goal:** `python -m src.cli feed add` 支持 GitHub blob URL，自动委派给 changelog 流程
**Depends on:** Phase 5 (changelog detection), Phase 8 (GitHub URL metadata)
**Problem:** `feed add` 不检测 GitHub URL，直接当 RSS 解析导致 403/422 错误
**Success Criteria:**
  1. `feed add https://github.com/{owner}/{repo}/blob/{branch}/CHANGELOG.md` 成功添加
  2. `feed add https://github.com/{owner}/{repo}/blob/{branch}/README.md` 成功添加
  3. `fetch --all` 对 GitHub URL feed 不报错
**Plans:** 2/2 plans complete ✅ (2026-03-23)
**UI hint:** no

### Phase 9: Enhanced Article List
**Goal:** Users can see article IDs and tags as separate columns in article list
**Depends on:** Nothing
**Requirements:** ARTICLE-01, ARTICLE-02, ARTICLE-03, ARTICLE-04
**Success Criteria** (what must be TRUE):
  1. User sees truncated article ID (8 chars) in first column of `article list` output
  2. User sees tags displayed in a separate dedicated column (not inline with title)
  3. `article list` with 20+ articles loads in under 1 second (N+1 fix verified)
  4. User can run `article list --verbose` to see full 32-char article IDs
**Plans:** 1/1
**Plan list:**
- [x] 09-01-PLAN.md -- Enhanced article list with rich table, ID column, tags column, N+1 fix
**UI hint:** yes

### Phase 10: Article Detail View
**Goal:** Users can view complete article information without opening browser
**Depends on:** Phase 9
**Requirements:** ARTICLE-05, ARTICLE-06, ARTICLE-07
**Success Criteria** (what must be TRUE):
  1. User can run `article view <id>` and see title, source/feed, date, tags, link, and full content
  2. User can run `article open <id>` to open article URL in default browser
  3. Detail view shows `content` field (not just `description`)
  4. View command works with truncated ID (8 chars) or full ID
**Plans:** 1/1 plans complete
**Plan list:**
- [x] 10-01-PLAN.md -- Article detail view with `article view` and `article open` commands
**UI hint:** yes

### Phase 11: GitHub Release Tagging
**Goal:** Tags can be applied to GitHub releases using article tag commands
**Depends on:** Phase 10
**Requirements:** GITHUB-01, GITHUB-02
**Success Criteria** (what must be TRUE):
  1. User can run `article tag <github-release-id>` to tag a GitHub release
  2. User can run `article tag <article-id>` to tag a feed article (existing behavior preserved)
  3. `article list --tag <tag>` shows both feed articles and GitHub releases with that tag
  4. Tag CRUD operations work uniformly for both article types
**Plans:** 1/1 plans complete
**Plan list:**
- [x] 11-01-PLAN.md -- GitHub release tagging with unified tagging commands

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

---
_For completed milestone details, see `.planning/milestones/`_
