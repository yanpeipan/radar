---
phase: quick-260327-fsm
plan: "01"
type: execute
wave: 1
depends_on: []
files_modified:
  - src/cli/feed.py
autonomous: true
must_haves:
  truths:
    - "User can fetch specific subscribed feeds by ID"
    - "fetch command accepts ids instead of urls"
    - "Error handling for invalid feed IDs"
  artifacts:
    - path: "src/cli/feed.py"
      provides: "Modified fetch command with ids parameter"
      min_lines: 150
  key_links:
    - from: "src/cli/feed.py"
      to: "src/application/feed.py"
      via: "fetch_one(feed_id) call"
      pattern: "fetch_one\\(.*\\)"
---

<objective>
Change the `fetch` command's parameter from `urls` to `ids` so users can fetch specific subscribed feeds by their feed ID instead of crawling arbitrary URLs directly.
</objective>

<execution_context>
@/Users/y3/radar/.claude/get-shit-done/workflows/quick.md
</execution_context>

<context>
@src/cli/feed.py (lines 166-340: fetch command)
@src/application/feed.py (lines 117-150: fetch_one function)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Change fetch command urls parameter to ids</name>
  <files>src/cli/feed.py</files>
  <action>
    In the `fetch` command (lines 166-340):
    1. Change `@click.argument("urls", nargs=-1, required=False)` to `@click.argument("ids", nargs=-1, required=False)`
    2. Rename variable from `urls: tuple` to `ids: tuple`
    3. Change `fetch_url_async(url)` to `fetch_one(id)` for each id
    4. Update the async function `fetch_one_with_semaphore(url: str)` to `fetch_one_with_semaphore(id: str)` and call `fetch_one(id)` instead
    5. Update help text and examples in docstring:
       - "Fetch new articles from feeds or crawl specific URLs" -> "Fetch new articles from subscribed feeds by ID"
       - Examples: "rss-reader fetch https://example.com" -> "rss-reader fetch <feed_id> [<feed_id>...]"
    6. Update progress messages from "Fetching N URLs" to "Fetching N feeds by ID"
    7. Update summary messages: "Fetched N articles from N URL(s)" -> "Fetched N articles from N feed(s)"
    8. Update error message: "Failed to fetch URLs" -> "Failed to fetch feeds"
    9. Update the "No arguments" case message to reference IDs not URLs
  </action>
  <verify>
    <automated>cd /Users/y3/radar && python -c "from src.cli.feed import fetch; import inspect; sig = inspect.signature(fetch.callback); print([p.name for p in sig.parameters.values()])"</automated>
  </verify>
  <done>fetch command accepts ids parameter, calls fetch_one() for each id</done>
</task>

</tasks>

<verification>
- `python -m src.cli fetch` help shows `ids` argument not `urls`
- `fetch_one()` is called with feed IDs, not `fetch_url_async()` with URLs
</verification>

<success_criteria>
`rss-reader fetch <id>` fetches the feed with that ID using the existing feed refresh logic
</success_criteria>

<output>
After completion, create `.planning/quick/260327-fsm-src-cli-feed-py-urls-ids/260327-fsm-SUMMARY.md`
</output>
