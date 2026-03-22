# Roadmap: Personal Information System

## Overview

A CLI-based personal information system for subscribing to RSS/Atom feeds and crawling websites. Phase 1 establishes the core subscription and storage infrastructure. Phase 2 adds full-text search and efficient conditional fetching. Phase 3 delivers website crawling as the differentiating feature.

## Phases

- [ ] **Phase 1: Foundation** - Feed subscription, article storage, and CLI commands
- [ ] **Phase 2: Search & Refresh** - FTS5 search and conditional fetching
- [ ] **Phase 3: Web Crawling** - Website crawling with robots.txt and rate limiting

## Phase Details

### Phase 1: Foundation
**Goal**: User can subscribe to RSS/Atom feeds, store articles locally, and list them via CLI
**Depends on**: Nothing (first phase)
**Requirements**: FEED-01, FEED-02, FEED-03, FEED-04, FETCH-01, FETCH-02, FETCH-03, FETCH-04, STOR-01, STOR-02, STOR-03, CLI-01, CLI-02, CLI-03, CLI-05, CLI-07
**Success Criteria** (what must be TRUE):
  1. User can add a RSS/Atom feed by URL and see it in the feed list
  2. User can remove a subscribed feed
  3. User can view a list of recent articles from subscribed feeds
  4. System parses RSS 2.0 and Atom feeds, extracting title, link, guid, pubDate, description
  5. System stores articles in SQLite with UNIQUE(feed_id, guid) deduplication
  6. System handles malformed XML gracefully without crashing
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md -- Foundation: database, models, project config
- [ ] 01-02-PLAN.md -- Feed operations: add/list/remove/refresh, parsing, deduplication
- [ ] 01-03-PLAN.md -- CLI: article list, fetch --all, click commands

### Phase 2: Search & Refresh
**Goal**: User can search articles by keyword and refresh feeds efficiently with conditional fetching
**Depends on**: Phase 1
**Requirements**: FETCH-05, STOR-04, CLI-06
**Success Criteria** (what must be TRUE):
  1. User can search articles by keyword and see matching results
  2. System uses FTS5 for fast full-text search
  3. System sends ETag/Last-Modified headers when refreshing feeds
  4. System skips downloading unchanged feeds (304 response handling)
**Plans**: TBD

### Phase 3: Web Crawling
**Goal**: User can crawl websites and store extracted content as articles
**Depends on**: Phase 2
**Requirements**: CLI-04, CRAWL-01, CRAWL-02, CRAWL-03, CRAWL-04
**Success Criteria** (what must be TRUE):
  1. User can crawl a website URL and content is stored as an article
  2. System extracts article-like content from HTML pages
  3. System respects robots.txt directives and does not crawl disallowed paths
  4. System rate-limits requests (1-2s delay between requests to same host)
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/3 | Ready to execute | - |
| 2. Search & Refresh | 0/TBD | Not started | - |
| 3. Web Crawling | 0/TBD | Not started | - |
