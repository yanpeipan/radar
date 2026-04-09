---
status: awaiting_human_verify
trigger: "uv run feedship article list --on 2026-04-05 returns No articles found when articles should exist"
created: 2026-04-05T00:00:00Z
updated: 2026-04-05T00:00:00Z
---

## Current Focus
hypothesis: "CONFIRMED - published_at is stored as TEXT (YYYY-MM-DD HH:MM:SS) but queries compared to INTEGER timestamps"
test: "Verified by running --on filter and seeing articles now return"
expecting: "Fix verified - articles now return with --on, --since, --until filters"
next_action: "Awaiting human verification"

## Symptoms
expected: Articles published on 2026-04-05 should be listed
actual: "No articles found." is returned
errors: None (no error message, just empty results)
reproduction: Run `uv run feedship article list --on 2026-04-05`
started: Unknown — likely after recent Article dataclass refactor

## Eliminated

## Evidence
- timestamp: 2026-04-05
  checked: "Database schema in src/storage/sqlite/init.py line 60"
  found: "published_at column is defined as TEXT, not INTEGER"
  implication: "Column stores dates as 'YYYY-MM-DD HH:MM:SS' strings"

- timestamp: 2026-04-05
  checked: "Actual database contents using sqlite3"
  found: "published_at values are strings like '2026-04-02 10:30:00'"
  implication: "Storage format confirmed as TEXT"

- timestamp: 2026-04-05
  checked: "list_articles query parameters"
  found: "Conditions like 'a.published_at >= ?' use INTEGER timestamps from _date_to_timestamp()"
  implication: "Comparing TEXT date strings to INTEGER values always fails"

- timestamp: 2026-04-05
  checked: "Verified articles exist for 2026-04-05"
  found: "article list (no filter) shows articles with Date 2026-04-05"
  implication: "Articles exist, but date filter cannot find them due to type mismatch"

## Resolution
root_cause: "The list_articles function converts date filter values to Unix timestamps (integers) using _date_to_timestamp(), but the published_at column stores dates as TEXT strings in 'YYYY-MM-DD HH:MM:SS' format. SQLite comparison between TEXT and INTEGER always fails, returning no results."
fix: "Replace timestamp-based comparison with string-based comparison using the same YYYY-MM-DD HH:MM:SS format as the stored values."
verification: "After fix, `uv run feedship article list --on 2026-04-05` returns articles"
files_changed: ["src/storage/sqlite/impl.py"]
