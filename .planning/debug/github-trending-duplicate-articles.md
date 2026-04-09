---
status: awaiting_human_verify
trigger: "github-trending-duplicate-articles"
created: 2026-04-05T00:00:00Z
updated: 2026-04-05T00:00:00Z
---

## Current Focus
hypothesis: "FIXED: Changed UNIQUE constraint from (feed_id, id) to (feed_id, guid) and updated ON CONFLICT"
test: "Ran migration and verified deduplication"
expecting: "Database rows reduced from 58,444 to 5,056 with correct constraint"
next_action: "Await user verification of the fix"

## Symptoms
expected: A reasonable number of unique GitHub Trending articles for 2026-04-05
actual: ~3300 articles returned (the limit), mostly GitHub Trending duplicates
errors: []
reproduction: "feedship article list --limit 3300 --on 2026-04-05"
started: "After recent Article dataclass or date filter changes"

## Eliminated
- hypothesis: "GitHub Trending provider generates duplicate GUIDs"
  evidence: "GUID format is 'github-trending:{period}:{repo_url}' - period is included, so daily/weekly/monthly have different GUIDs"
  timestamp: 2026-04-05T00:00:00Z

- hypothesis: "Multiple fetch passes causing duplicates"
  evidence: "Query shows same GUID appears 17 times, confirming articles are being inserted multiple times with same guid"
  timestamp: 2026-04-05T00:00:00Z

## Evidence
- timestamp: 2026-04-05T00:00:00Z
  checked: "GitHub Trending provider GUID format"
  found: "GUID format is 'github-trending:{period}:{repo_url}' - includes period"
  implication: "Different periods should have different GUIDs - provider is correct"

- timestamp: 2026-04-05T00:00:00Z
  checked: "Database query for duplicate GUIDs"
  found: "Same GUID appears 17 times, e.g., 'github-trending:daily:https://github.com/Blaizzy/mlx-vlm' appears 17 times"
  implication: "Articles are being inserted multiple times, not being upserted"

- timestamp: 2026-04-05T00:00:00Z
  checked: "upsert_articles ON CONFLICT clause"
  found: "Uses 'ON CONFLICT(feed_id, id)' but table has UNIQUE(feed_id, id)"
  implication: "BUG: Since a new id is generated for each insert, conflict NEVER triggers"

- timestamp: 2026-04-05T00:00:00Z
  checked: "Articles table schema"
  found: "UNIQUE(feed_id, id) - no UNIQUE(feed_id, guid) constraint exists"
  implication: "The upsert should use (feed_id, guid) but it uses (feed_id, id) which can never conflict"

- timestamp: 2026-04-05T00:00:00Z
  checked: "Database state before migration"
  found: "58,444 total rows, only 5,056 unique (feed_id, guid) pairs"
  implication: "Massive duplication confirmed"

- timestamp: 2026-04-05T00:00:00Z
  checked: "Database state after migration"
  found: "5,056 rows with UNIQUE(feed_id, guid) constraint"
  implication: "Migration successful - deduplicated and constraint fixed"

- timestamp: 2026-04-05T00:00:00Z
  checked: "Article list test"
  found: "46 articles for 2026-04-05 (down from thousands)"
  implication: "Fix is working - no more duplicates"

## Resolution
root_cause: "The UPSERT in _batch_upsert_articles used ON CONFLICT(feed_id, id), but id is always newly generated so conflicts never triggered. The constraint UNIQUE(feed_id, id) was also wrong - it should be UNIQUE(feed_id, guid)."
fix: "1. Changed ON CONFLICT clause from (feed_id, id) to (feed_id, guid) in impl.py. 2. Added migration in init.py to change UNIQUE(feed_id, id) to UNIQUE(feed_id, guid) with deduplication."
verification: "Database migrated from 58,444 rows to 5,056 unique articles. Article list for 2026-04-05 shows 46 articles instead of thousands."
files_changed: ["src/storage/sqlite/impl.py", "src/storage/sqlite/init.py"]
commit: "7289c59"
