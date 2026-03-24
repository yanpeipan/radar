# Architecture Research: nanoid ID Migration

**Domain:** RSS Reader - SQLite-based article ID migration
**Researched:** 2026-03-25
**Confidence:** HIGH

## Executive Summary

The v1.6 milestone replaces `uuid.uuid4()` with `nanoid.generate()` for article ID generation, producing shorter (21 chars vs 36 chars) URL-safe identifiers. This document maps affected components, data flow changes, and migration order of operations.

## Current Schema Analysis

### Existing Tables (from src/storage/sqlite.py)

```
articles table:
  - id TEXT NOT NULL          <-- TARGET: change from UUID to nanoid
  - feed_id TEXT NOT NULL REFERENCES feeds(id)
  - title, link, guid, pub_date, description, content, created_at
  - UNIQUE(feed_id, id)       <-- constraint uses id

article_tags table:
  - article_id TEXT NOT NULL   <-- FK to articles.id
  - tag_id TEXT NOT NULL
  - PRIMARY KEY(article_id, tag_id)
  - FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE

articles_fts FTS5 virtual table:
  - References articles.rowid (internal), NOT article id
  - Content: title, description, content
  - FTS sync (line 351-355): INSERT OR REPLACE uses rowid

tags table:
  - id TEXT PRIMARY KEY       <-- also uses UUID (secondary target)
  - name, created_at
```

## Affected Components

### Components Requiring Modification

| File | Function | Line | Change | Priority |
|------|----------|------|--------|----------|
| `src/storage/sqlite.py` | `store_article()` | 334 | Replace `uuid.uuid4()` with `nanoid.generate()` | CRITICAL |
| `src/storage/sqlite.py` | `store_article_async()` | 361-384 | Delegates to `store_article`, no change needed | N/A |
| `src/storage/sqlite.py` | `add_tag()` | 181 | Replace `uuid.uuid4()` with `nanoid.generate()` | MODERATE |
| `src/storage/sqlite.py` | `tag_article()` | 244 | Replace `uuid.uuid4()` with `nanoid.generate()` | MODERATE |
| Migration script (new) | - | - | Regenerate IDs for ~2479 articles | CRITICAL |

### Components NOT Requiring Modification

| Component | Why Unaffected |
|-----------|----------------|
| `articles_fts` | Uses `rowid` internally, not article `id`. FTS sync at line 351-355 uses rowid. |
| `article_tags` | FK cascades on delete. Tag associations preserved via article_id update. |
| `feeds` table | Uses feed_id from external sources, not article IDs |
| CLI modules | Display article IDs but read-only, will work with new format |
| Search functions | Query by `id` which remains TEXT type |

## Data Flow

### Normal Operation (Post-Migration)

```
New article arrives via fetch
    ↓
store_article(guid, title, content, link, feed_id, pub_date)
    ↓
article_id = nanoid.generate()  ← 21 chars vs UUID 36 chars
    ↓
INSERT INTO articles (id, feed_id, ...) VALUES (article_id, ...)
    ↓
INSERT OR REPLACE INTO articles_fts(rowid, title, description, content)
    SELECT rowid, title, description, content FROM articles WHERE id = article_id
    ↓
Returns article_id (nanoid format)
```

### Migration Script Operation

```
For each existing article with URL-like ID:
    1. Generate new nanoid
    2. UPDATE article_tags SET article_id = new_id WHERE article_id = old_id
    3. UPDATE articles SET id = new_id WHERE id = old_id
    (FTS rowid remains unchanged, content updates automatically)
```

## Key Insight: FTS rowid Behavior

The FTS5 virtual table uses SQLite's internal `rowid` to track articles, NOT the article `id` column:

```python
# Line 351-355 in store_article()
cursor.execute(
    """INSERT OR REPLACE INTO articles_fts(rowid, title, description, content)
       SELECT rowid, title, description, content FROM articles WHERE id = ?""",
    (article_id,),
)
```

**Implications:**
- FTS rows are tied to the article's rowid (auto-incrementing internal value)
- Changing `articles.id` does NOT require FTS migration
- The `INSERT OR REPLACE` updates content in-place based on rowid
- Do NOT reindex FTS after migration

## ID Format Comparison

| Format | Example | Length | URL-safe |
|--------|---------|--------|----------|
| UUID v4 | `550e8400-e29b-41d4-a716-446655440000` | 36 chars | No (contains `-`) |
| nanoid | `V1StGXR8_Z5jdHi6B9LW11` | 21 chars | Yes (URL-safe alphabet) |

## Order of Operations (Migration Script)

```python
import nanoid

def migrate_article_ids():
    """Migrate ~2479 URL-like article IDs to nanoid format."""
    with get_db() as conn:
        cursor = conn.cursor()

        # 1. Find articles needing migration (URL-like IDs)
        cursor.execute("SELECT id FROM articles WHERE id LIKE 'http%'")
        articles_to_migrate = cursor.fetchall()

        migrated_count = 0
        for (old_id,) in articles_to_migrate:
            # 2. Generate new nanoid
            new_id = nanoid.generate()

            # 3. Update article_tags first (FK dependency order)
            cursor.execute(
                "UPDATE article_tags SET article_id = ? WHERE article_id = ?",
                (new_id, old_id)
            )

            # 4. Update articles table
            cursor.execute(
                "UPDATE articles SET id = ? WHERE id = ?",
                (new_id, old_id)
            )

            migrated_count += 1

        conn.commit()
        return migrated_count
```

## Code Changes

### store_article() Change

```python
# BEFORE (line 311-334)
import uuid
# ...
article_id = str(uuid.uuid4())

# AFTER
import nanoid
# ...
article_id = nanoid.generate()
```

### add_tag() Change

```python
# BEFORE (line 178-181)
import uuid
# ...
tag_id = str(uuid.uuid4())

# AFTER
import nanoid
# ...
tag_id = nanoid.generate()
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Reindexing FTS After Migration

**What:** Running `INSERT INTO articles_fts(...)` or recreating the FTS table
**Why bad:** Unnecessary, FTS follows rowid not `id`. Would rebuild entire index for no reason.
**Instead:** Trust the existing `INSERT OR REPLACE` sync mechanism.

### Anti-Pattern 2: Forgetting article_tags FK Update Order

**What:** Updating `articles.id` before `article_tags.article_id`
**Why bad:** FK constraint violation or orphaned tag associations
**Instead:** Always update `article_tags.article_id` BEFORE `articles.id`, in same transaction.

### Anti-Pattern 3: Reusing nanoid IDs

**What:** Checking if nanoid "exists" before inserting
**Why bad:** nanoid has collision-resistant generation (~36 bits entropy). Probability of collision in 10M IDs is ~10^-23.
**Instead:** Trust nanoid's collision resistance. Only check `UNIQUE(feed_id, id)` constraint.

### Anti-Pattern 4: Missing Transaction Boundary

**What:** Updating articles one at a time without batching in transaction
**Why bad:** Half-migrated state if script crashes mid-way
**Instead:** Wrap all updates in single transaction, or checkpoint periodically

## Quality Gate Criteria

- [ ] `store_article()` uses `nanoid.generate()` for new articles
- [ ] `add_tag()` uses `nanoid.generate()` for new tags
- [ ] `tag_article()` uses `nanoid.generate()` for new tags
- [ ] Migration script updates `article_tags` before `articles`
- [ ] Migration script uses single transaction (or checkpoint pattern)
- [ ] FTS index NOT rebuilt after migration
- [ ] Existing article CRUD operations verified
- [ ] Existing tagging operations verified
- [ ] Existing search operations verified

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Schema impact | HIGH | Clear from codebase analysis |
| FTS behavior | HIGH | rowid is SQLite internal, well-documented behavior |
| article_tags FK | HIGH | CASCADE and UPDATE behavior is standard SQL |
| Migration script | HIGH | Pattern is straightforward ID replacement |
| nanoid collision | HIGH | nanoid v3.16.0 collision resistance is mathematically sound |

## Sources

- [nanoid Python documentation](https://pypi.org/project/nanoid/) (HIGH confidence)
- [SQLite rowid documentation](https://www.sqlite.org/lang_createtable.html#rowid) (HIGH confidence)
- [FTS5 documentation](https://www.sqlite.org/fts5.html) (HIGH confidence)
- [SQLite Foreign Key documentation](https://www.sqlite.org/foreignkeys.html) (HIGH confidence)

---

*Architecture research for: nanoid ID migration*
*Researched: 2026-03-25*
