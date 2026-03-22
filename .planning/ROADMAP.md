# Roadmap: Personal Information System

## Milestones

- ✅ **v1.0 MVP** — Phases 1-3 (shipped 2026-03-22)
- 🚧 **v1.1 GitHub Monitoring** — Phases 4-6 (in progress)

## Phases

- [x] **Phase 1: Foundation** - Storage, feed parsing, CLI interface (v1.0)
- [x] **Phase 2: Search & Refresh** - FTS5 search, feed refresh mechanism (v1.0)
- [x] **Phase 3: Web Crawling** - Website crawling with robots.txt, rate limiting (v1.0)
- [x] **Phase 4: GitHub API Client + Releases Integration** - Add repos, fetch releases via GitHub API, token auth, rate limit handling (completed 2026-03-22)
- [x] **Phase 5: Changelog Detection + Scraping** - Detect changelog files, scrape content, store as articles (completed 2026-03-22)
- [ ] **Phase 6: Unified Display + Refresh Integration** - Display GitHub content in unified format, integrate with refresh

---

## Phase Details

### Phase 4: GitHub API Client + Releases Integration

**Goal**: Users can add GitHub repositories to monitor and receive release updates

**Depends on**: Phase 3

**Requirements**: GH-01, GH-02, GH-03, GH-04

**Success Criteria** (what must be TRUE):
  1. User can add a GitHub repository URL via CLI and it is stored
  2. System fetches release tag_name, body, published_at, html_url from GitHub API
  3. System uses GITHUB_TOKEN from environment variable when available
  4. System displays a friendly message when GitHub API rate limit is exceeded (without token)

**Plans**: 2 plans
- [x] 04-01-PLAN.md - GitHub API client module (models, DB schema, github.py)
- [x] 04-02-PLAN.md - CLI commands for repo management (add, list, remove, refresh)

### Phase 5: Changelog Detection + Scraping

**Goal**: System detects and scrapes changelog files from GitHub repositories

**Depends on**: Phase 4

**Requirements**: GH-05, GH-06

**Success Criteria** (what must be TRUE):
  1. System detects presence of CHANGELOG.md, HISTORY.md, CHANGES.md in repository
  2. System fetches changelog content via raw.githubusercontent.com
  3. Changelog content is stored as article in database with repository association

**Plans**: 2 plans
- [x] 05-01-PLAN.md - Changelog detection and scraping module (DB schema, github.py functions)
- [x] 05-02-PLAN.md - CLI commands for viewing and refreshing changelogs

### Phase 6: Unified Display + Refresh Integration

**Goal**: GitHub releases and changelogs appear alongside other content in unified display

**Depends on**: Phase 5

**Requirements**: GH-07, GH-08

**Success Criteria** (what must be TRUE):
  1. GitHub releases appear in article list with unified formatting (same layout as feed articles)
  2. Changelog entries appear alongside other articles when listing or searching
  3. `fetch --all` command refreshes GitHub repositories alongside RSS feeds
  4. User can see GitHub source indicated for each article (repo name, release tag)

**Plans**: TBD

---

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.0 | 3/3 | ✅ Complete | 2026-03-22 |
| 2. Search & Refresh | v1.0 | 4/4 | ✅ Complete | 2026-03-22 |
| 3. Web Crawling | v1.0 | 2/2 | ✅ Complete | 2026-03-22 |
| 4. GitHub API Client | v1.1 | 2/2 | Complete   | 2026-03-22 |
| 5. Changelog Detection | v1.1 | 2/2 | Complete   | 2026-03-22 |
| 6. Unified Display | v1.1 | 0/0 | Not started | - |

---

_For completed milestone details, see `.planning/milestones/v1.0-MVP-ROADMAP.md`_
