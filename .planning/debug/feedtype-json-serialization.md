---
status: fixing
trigger: "feed add https://twitter.com/elonmusk --json throws TypeError: Object of type FeedType is not JSON serializable"
created: 2026-04-02T00:00:00Z
updated: 2026-04-02T00:00:00Z
---

## Current Focus
hypothesis: "Confirmed: _serialize_discovered_feed() returns feed.feed_type (enum) instead of feed.feed_type.value (string)"
test: "Apply fix: change line 321 from feed.feed_type to feed.feed_type.value"
expecting: "JSON serialization will work after fix"
next_action: "Apply fix to src/cli/ui.py"

## Symptoms
expected: JSON output with feed details
actual: TypeError: Object of type FeedType is not JSON serializable
errors:
  - "TypeError: Object of type FeedType is not JSON serializable"
  - "File \"src/cli/feed.py\", line 281, in feed_add\""
  - "File \"src/cli/ui.py\", line 250, in print_json\""
reproduction: "Run `feedship feed add https://twitter.com/elonmusk --json`"
started: After FeedType enum refactoring

## Eliminated

## Evidence
- timestamp: 2026-04-02
  checked: "src/cli/ui.py _serialize_discovered_feed() function"
  found: "Line 321: 'type': feed.feed_type - returns enum directly instead of string"
  implication: "FeedType enum is not JSON serializable, needs .value to get string"
- timestamp: 2026-04-02
  checked: "src/models.py FeedType enum definition"
  found: "FeedType is an Enum with string values (RSS='rss', GITHUB_RELEASE='github_release', TAVILY='tavily')"
  implication: "Using .value will return the string representation"

## Resolution
root_cause: "_serialize_discovered_feed() used feed.feed_type (enum) instead of feed.feed_type.value (string)"
fix: "Change line 321 in src/cli/ui.py from 'type': feed.feed_type to 'type': feed.feed_type.value"
verification: ""
files_changed: []
