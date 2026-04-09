---
status: resolved
trigger: "feedship feed add https://openai.com/ returns 'No feeds discovered' but other URLs work"
created: 2026-04-02T00:00:00Z
updated: 2026-04-02T00:00:00Z
---

## Current Focus
**RESOLVED** - The fix has been verified

## Symptoms
expected: Discover and add RSS feeds from openai.com - should find RSS feeds on the website
actual: "No feeds discovered." - the discover command finds no feeds on openai.com
errors: No error message, just "No feeds discovered"
reproduction: Run `.venv/bin/python -m src.cli feed add https://openai.com/`
timeline: Worked before, now broken - this is a regression
compare: Other URLs work fine, only openai.com fails

## Eliminated
- hypothesis: openai.com blocking scrapers
  evidence: Page fetches successfully (200 status, 409KB content)

## Evidence
- timestamp: 2026-04-02
  checked: openai.com page fetch
  found: Page fetches successfully (200 status, 409KB content)
  implication: Issue is not with fetching

- timestamp: 2026-04-02
  checked: openai.com HTML content for feed links
  found: Found link alternate tags (57 language variants) and CSS selector feed link at https://openai.com/news/rss.xml
  implication: Feed exists, but discovery isn't finding it

- timestamp: 2026-04-02
  checked: RSSProvider.match() logic
  found: When response is provided with HTML content (content-type: text/html), feedparser.parse() returns 0 entries, causing match() to return False
  implication: Bug in match() - it should fall through to URL-only matching for HTML pages

- timestamp: 2026-04-02
  checked: providers_discover() for openai.com
  found: No providers matched (matched providers: [])
  implication: Root cause identified - RSSProvider.match() returns False for HTML pages

- timestamp: 2026-04-02
  checked: Verification after fix
  found: RSSProvider.match('https://openai.com/', response) now returns ['RSSProvider']
  implication: Fix verified working

## Resolution
root_cause: "RSSProvider.match() incorrectly returns False when response is provided but content is HTML. When response is provided, the code tried to parse content with feedparser. For HTML pages, parsed.entries is empty, causing match() to return False. The code never reached the URL-only matching logic (lines 112-122) that would match HTTP URLs."
fix: "Added content-type check before feedparser validation. Only validate with feedparser if content-type indicates a feed (rss, atom, rdf, xml). For HTML pages (or other non-feed content-types), fall through to URL-only matching."
verification: "All 22 CLI tests pass including test_feed_add_openai_discovers_news_rss which specifically tests openai.com feed discovery. match('https://openai.com/', response) now correctly returns ['RSSProvider']."
files_changed:
  - src/providers/rss_provider.py: Added content-type check before feedparser validation
  - tests/test_providers.py: Fixed mock responses to include proper body content for RSS/Atom/XML content-type tests; fixed FeedType enum comparison
