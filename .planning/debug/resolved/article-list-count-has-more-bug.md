---
status: resolved
trigger: "feedship article list --since 2026-04-04 --json --limit 1 returns count=1, has_more=false, expected has_more=true"
created: 2026-04-06T00:00:00Z
updated: 2026-04-06T00:00:00Z
---

## Current Focus
hypothesis: "has_more is calculated as `len(items) > limit` but should be `len(items) >= limit`"
test: "Run reproduction command"
expecting: "When count == limit, has_more should be true"
next_action: "Archive session"

## Symptoms
expected: "When count == limit, has_more should be true (indicating more results exist)"
actual: "count=1, has_more=false (has_more is false even though limit=1 was reached)"
errors: []
reproduction: "uv run feedship article list --since 2026-04-04 --json --limit 1"
started: "Unknown - likely a regression"

## Eliminated

## Evidence

## Resolution
root_cause: "In format_article_list(), has_more was calculated as `len(items) > limit` instead of `len(items) >= limit`. When exactly limit items are returned, has_more should be true to indicate more results exist."
fix: "Changed `has_more` condition from `len(items) > limit` to `len(items) >= limit` in src/cli/ui.py line 343"
verification: "Reproduction command now returns has_more=true when count=1 and limit=1"
files_changed: ["src/cli/ui.py"]
