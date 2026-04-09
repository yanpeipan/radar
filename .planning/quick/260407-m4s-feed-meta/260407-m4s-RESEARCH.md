# Phase Quick: Feed Metadata Enhancement - Research

**Researched:** 2026/04/07
**Domain:** Feed model, SQLite schema, CLI feed management
**Confidence:** HIGH

## Summary

The feedship RSS reader stores feed metadata in a SQLite `feeds` table with a Pydantic `Feed` model. The model already supports `weight` (0.0-1.0 range) and `group` (string), plus a `metadata` JSON field for provider-specific data (`FeedMetaData` with `selectors` and `feed_type`). The database uses an ALTER TABLE migration pattern to add columns. No `feed update` command exists in the CLI - only `feed add`, `feed list`, and `feed remove`.

**Primary recommendation:** Implement `feed update <feed_id>` command supporting weight adjustment, group changes, and metadata editing. New fields can be stored in the existing `metadata` JSON column to avoid schema migrations.

## Standard Stack

| Library | Version | Purpose |
|---------|---------|---------|
| pydantic | - | Feed/Article/FeedMetaData models |
| sqlite3 | built-in | Local SQLite database |
| click | - | CLI commands |
| nanoid | - | Feed ID generation |

**No new dependencies required.**

## Architecture Patterns

### Feed Model (`src/models.py`)
```
Feed:
  id: str              # nanoid
  name: str            # max 200 chars
  url: str            # validated URL pattern
  created_at: str      # YYYY-MM-DD HH:MM:SS
  etag: str | None    # HTTP ETag for conditional fetch
  modified_at: str | None  # HTTP Last-Modified
  fetched_at: str | None  # last successful fetch timestamp
  metadata: str | FeedMetaData | None  # JSON for provider-specific data
  weight: float | None  # 0.0-1.0, semantic search ranking
  group: str | None    # max 100 chars, feed grouping
```

### FeedMetaData (`src/models.py`)
```
FeedMetaData:
  selectors: list[str] | None  # path prefix filters for WebpageProvider
  feed_type: str | None        # 'rss', 'atom', 'webpage', 'github_release', etc.
```

### Database Schema (`src/storage/sqlite/init.py`)
```sql
CREATE TABLE IF NOT EXISTS feeds (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    etag TEXT,
    modified_at TEXT,
    fetched_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT,
    weight REAL DEFAULT 0.3,
    "group" TEXT
)
```

### Migration Pattern (from `init.py`)
Columns are added via `ALTER TABLE` with `IF NOT EXISTS` checks. Example:
```python
cursor.execute('ALTER TABLE feeds ADD COLUMN "group" TEXT')
```

### How Weight is Currently Used
- **Default:** 0.3 (set by `get_default_feed_weight()` in `src/application/config.py`)
- **Storage:** `weight REAL DEFAULT 0.3` in feeds table
- **In model:** `weight: float | None = Field(default=None, ge=0.0, le=1.0)` (note: None defaults to None, not 0.3)
- **CLI display:** `weight if weight is not None else 0.3` (line 322, 357 in feed.py)
- **Usage:** Appears in `ArticleListItem.source_weight = 0.3` (impl.py line 779), suggesting weight is used in ranking but hardcoded there - may need verification

### How Groups are Currently Implemented
- **Storage:** `"group" TEXT` column in feeds table
- **Model:** `group: str | None = Field(default=None, max_length=100)`
- **Filtering:** `feed list --group <name>` supports exact match filter (feed.py lines 292-299)
- **Query filtering:** Used in `list_articles()` and `search_articles_fts()` via `f."group" IN (...)` (impl.py lines 739-741, 991-994, 1011-1013)
- **No hierarchy:** Groups are flat strings, no nested groups

## Don't Hand-Roll

| Problem | Use Instead | Notes |
|---------|-------------|-------|
| Feed ID generation | `nanoid.generate()` | Already used in `src/utils.py` |
| Database migration | `ALTER TABLE ADD COLUMN` pattern | Already established in `init.py` |
| JSON metadata | `FeedMetaData` + `to_json()` | Already serializes excluding None values |

## Common Pitfalls

### Pitfall 1: Weight defaults inconsistently
**What:** Model defaults `weight=None` but database defaults to `0.3` and CLI uses `0.3` when displaying. This means `weight=None` in DB is treated differently than `weight=0.3`.
**How to avoid:** Decide on a canonical default (None vs 0.3) and use consistently.

### Pitfall 2: metadata field is JSON string in DB
**What:** `metadata` is stored as JSON string in SQLite, but Pydantic can accept `FeedMetaData` object. The conversion happens in `FeedMetaData.to_json()`.
**How to avoid:** When updating metadata, always use `FeedMetaData.to_json()` to serialize.

### Pitfall 3: No update command exists
**What:** The CLI only has `feed add`, `feed list`, `feed remove`. No `feed update`.
**How to avoid:** Implement `feed update` command following the pattern of `register_feed()` which uses `upsert_feed()`.

### Pitfall 4: Quoted "group" column name
**What:** SQLite column named `group` must be quoted as `"group"` in SQL queries because `group` is a reserved keyword.
**How to avoid:** Always use double quotes when referencing the group column in raw SQL.

## Code Examples

### Register/Update Feed (upsert pattern)
```python
# From src/application/feed.py:register_feed()
feed = Feed(
    id=generate_feed_id(),
    name=feed_name or feed_url,
    url=feed_url,
    weight=weight if weight is not None else get_default_feed_weight(),
    metadata=feed_meta_data.to_json() if feed_meta_data else None,
    group=group,
)
return upsert_feed(feed)
```

### Upsert Feed Implementation
```python
# From src/storage/sqlite/impl.py:upsert_feed()
# UPDATE existing
cursor.execute(
    """UPDATE feeds SET name = ?, etag = ?, modified_at = ?, fetched_at = ?,
       weight = ?, metadata = ?, "group" = ? WHERE url = ?""",
    (feed.name, feed.etag, feed.modified_at, feed.fetched_at,
     feed.weight, feed.metadata, feed.group, feed.url),
)
# OR INSERT new
cursor.execute(
    """INSERT INTO feeds (id, name, url, etag, modified_at, fetched_at,
       created_at, weight, metadata, "group") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    (feed.id, feed.name, feed.url, feed.etag, feed.modified_at, feed.fetched_at,
     feed.created_at, feed.weight, feed.metadata, feed.group),
)
```

### FeedMetaData Serialization
```python
# From src/models.py:FeedMetaData
def to_json(self) -> str | None:
    data = self.model_dump(exclude_none=True)
    return json.dumps(data) if data else None
```

### Feed List with Group Filter
```python
# From src/cli/feed.py:feed_list()
if group is not None:
    if group == "" or group.lower() == "none":
        feeds = [f for f in feeds if f.group is None]
    else:
        feeds = [f for f in feeds if f.group == group]
```

## Migration Approach for New Fields

**Option 1: Add to metadata JSON (no schema change)**
- Pros: No migration needed, stored in existing `metadata` column
- Cons: Cannot query/sort by these fields in SQL
- Best for: Display-only or provider-specific data

**Option 2: Add to feeds table with ALTER TABLE**
- Pros: Can query, index, join on new fields
- Cons: Requires migration logic
- Pattern: Follow existing `init.py` pattern:
  ```python
  cursor.execute("PRAGMA table_info(feeds)")
  existing = {row[1] for row in cursor.fetchall()}
  if "new_column" not in existing:
      cursor.execute('ALTER TABLE feeds ADD COLUMN new_column TEXT')
  ```

## Open Questions

1. **Weight usage verification:** `ArticleListItem.source_weight` is hardcoded to `0.3` in `list_articles()`. Need to verify if feed `weight` field is actually used in semantic search ranking.
2. **Which meta fields are needed:** Task description mentions "补充meta" but doesn't specify which. Need clarification on what new metadata fields are desired.
3. **Feed name editing:** Should `feed update` also support renaming feeds (changing `name` field)?

## Sources

- `src/models.py` - Feed/FeedMetaData models (verified)
- `src/storage/sqlite/impl.py` - Database operations (verified)
- `src/storage/sqlite/init.py` - Schema initialization (verified)
- `src/cli/feed.py` - CLI commands (verified)
- `src/application/feed.py` - Business logic (verified)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Only uses existing project libraries
- Architecture: HIGH - Pattern clear from codebase
- Pitfalls: MEDIUM - Some details (e.g., weight usage in ranking) not fully traced

**Research date:** 2026/04/07
**Valid until:** 90 days (SQLite/Pydantic patterns stable)
