---
status: investigating
trigger: "RSSProvider.discover hangs >30s when run via python -m src.cli --debug feed add https://openai.com/"
created: 2026-04-02T00:00:00Z
updated: 2026-04-02T00:00:00Z
---

## Current Focus
hypothesis: nested asyncio.run() causing hang
test: Read source code to identify the nested asyncio.run() pattern
expecting: Find where discover() or deep_crawl uses asyncio.run() inside an already-running event loop
next_action: Read src/providers/rss_provider.py and src/discovery/deep_crawl.py

## Symptoms
expected: RSSProvider.discover should return within seconds (with 0 feeds found or a result)
actual: Hangs > 30 seconds before returning
errors: None - just slow
reproduction: .venv/bin/python -m src.cli --debug feed add https://openai.com/
started: Recently - worked before

## Eliminated
<!-- EMPTY -->

## Evidence
<!-- EMPTY -->

## Resolution
root_cause:
fix:
verification:
files_changed: []
