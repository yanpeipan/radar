# Feature Research: nanoid ID Migration

**Domain:** Database ID migration for Python RSS reader
**Researched:** 2026-03-25
**Confidence:** HIGH (verified via code analysis and database inspection)

## Problem Statement

All 5,594 articles in the database have URL-like IDs (or SHA256 hash IDs) instead of proper UUID/nanoid IDs:

| ID Pattern | Length | Count | Example |
|-----------|--------|-------|---------|
| SHA256 hash | 26 | 2,710 | `3a4b5c6d7e8f9012345678...` |
| URL-like | 32-78+ | 2,884 | `https://openai.com/blog/...` |

The `articles.id` column should contain short, URL-safe identifiers, not full URLs or long hashes.

---

## Migration Behavior

### Detection Strategy

URL-like IDs are identifiable by these characteristics:

| Pattern | Detection | Example |
|---------|-----------|---------|
| URL | Contains `://` or starts with `http` | `https://openai.com/index/...` |
| Hash | 64 hex chars (SHA256) or truncated version | `3a4b5c6d7e8f90123456789...` |
| UUID | Matches `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` | (none currently in DB) |
| nanoid | Alphanumeric, 21 chars default | (none currently in DB) |

**Detection query:**
```sql
SELECT id, length(id) as len FROM articles
WHERE id LIKE '%://%'      -- URL-like
   OR length(id) = 64     -- Full SHA256
   OR (id GLOB '*[!a-z0-9_-]*' AND length(id) > 21)  -- Contains invalid nanoid chars
```

**nanoid format:**
- Characters: `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_-`
- Default length: 21 characters
- No special characters (unlike URLs)

### Regeneration Approach

1. **Generate new ID per article:**
   ```python
   import nanoid
   new_id = nanoid.generate()  # 21 char URL-safe ID
   ```

2. **Update articles table:**
   ```python
   UPDATE articles SET id = ? WHERE id = ?
   ```

3. **Cascade to foreign keys:**
   - `article_tags.article_id` (3,737 entries)
   - `article_embeddings.article_id`

### Expected Behavior During Migration

| Phase | Action | Duration | Risk |
|-------|--------|----------|------|
| 1. Detect | Find all non-nanoid IDs | <1s | LOW |
| 2. Backup | Create DB backup | varies | LOW |
| 3. Generate | Create ID mapping table | <1s | LOW |
| 4. Update tags | UPDATE article_tags | ~1s | MEDIUM (data loss if interrupted) |
| 5. Update embeddings | UPDATE article_embeddings | ~1s | MEDIUM (data loss if interrupted) |
| 6. Update articles | UPDATE articles | ~1s | MEDIUM (data loss if interrupted) |
| 7. Verify | Count matches, spot-check | <1s | LOW |
| 8. Vacuum | VACUUM to reclaim space | varies | LOW |

**Critical: All updates must be in a single transaction or use temporary mapping table.**

### Post-Migration Behavior

| Metric | Before | After |
|--------|--------|-------|
| ID length | 26-78+ chars | 21 chars |
| ID type | URL or SHA256 | nanoid |
| URL-safe | No (URLs have `://?&=`) | Yes |
| Foreign keys | 3,737 article_tags | Preserved |
| Embeddings | Preserved | Preserved |

---

## Migration Pattern: Temporary Mapping Table

Recommended approach to avoid foreign key issues:

```python
def migrate_article_ids():
    """Migrate article IDs from URL/hash to nanoid."""
    import nanoid

    with get_db() as conn:
        cursor = conn.cursor()

        # Step 1: Create temporary mapping table
        cursor.execute("""
            CREATE TEMP TABLE article_id_map (
                old_id TEXT,
                new_id TEXT,
                PRIMARY KEY (old_id)
            )
        """)

        # Step 2: Generate new IDs for all articles
        cursor.execute("SELECT DISTINCT id FROM articles")
        for row in cursor.fetchall():
            old_id = row["id"]
            new_id = nanoid.generate()
            cursor.execute(
                "INSERT INTO article_id_map (old_id, new_id) VALUES (?, ?)",
                (old_id, new_id)
            )

        # Step 3: Update foreign key tables first (preserves referential integrity)
        cursor.execute("""
            UPDATE article_tags
            SET article_id = (
                SELECT new_id FROM article_id_map WHERE old_id = article_tags.article_id
            )
            WHERE EXISTS (
                SELECT 1 FROM article_id_map WHERE old_id = article_tags.article_id
            )
        """)

        cursor.execute("""
            UPDATE article_embeddings
            SET article_id = (
                SELECT new_id FROM article_id_map WHERE old_id = article_embeddings.article_id
            )
            WHERE EXISTS (
                SELECT 1 FROM article_id_map WHERE old_id = article_embeddings.article_id
            )
        """)

        # Step 4: Update articles table
        cursor.execute("""
            UPDATE articles
            SET id = (
                SELECT new_id FROM article_id_map WHERE old_id = articles.id
            )
            WHERE EXISTS (
                SELECT 1 FROM article_id_map WHERE old_id = articles.id
            )
        """)

        conn.commit()

        # Step 5: Verify counts
        cursor.execute("SELECT COUNT(*) as total FROM article_tags")
        tags_count = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) as total FROM articles")
        articles_count = cursor.fetchone()["total"]

        return {"articles": articles_count, "tags": tags_count}
```

---

## Table Stakes (Required for Migration)

| Feature | Why Required | Complexity | Notes |
|---------|-------------|------------|-------|
| ID regeneration | All 5,594 articles have wrong ID type | LOW | Simple nanoid.generate() call |
| Foreign key updates | article_tags (3,737), article_embeddings depend on article.id | MEDIUM | Must update atomically |
| Verification | Ensure no orphaned tags/embeddings after migration | LOW | Count comparison |
| store_article() update | New articles should use nanoid, not uuid.uuid4() | LOW | Replace 1 function call |

## Differentiators (Quality Improvements)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Transactional migration | All-or-nothing update prevents partial state | MEDIUM | Single transaction or rollback |
| ID length display | CLI shows truncated 8-char IDs (already implemented) | LOW | No change needed |
| Backward compat lookup | Support looking up by old ID during transition | LOW | Optional: add old_id column |

## Anti-Features (Avoid)

| Feature | Why Problematic | Alternative |
|---------|-----------------|--------------|
| In-place ID swap without mapping | Foreign keys break immediately | Use temp mapping table |
| Deleting and re-inserting articles | Loses pub_date, created_at, FTS data | UPDATE in place |
| Concurrent migration + writes | Race condition corrupts data | Lock table or single-thread |
| Changing ID generation mid-migration | Creates mixed ID formats | Complete migration, then switch |

---

## Feature Dependencies

```
store_article() ID generation
    └──requires──> Migration of existing articles
                      └──requires──> Foreign key cleanup (article_tags, article_embeddings)

Verification
    └──requires──> Migration completion
```

---

## MVP Definition (v1.6)

### Launch With

- [x] nanoid installed (v3.16.0)
- [ ] Migration script that:
  - [ ] Detects URL-like and hash-based IDs
  - [ ] Generates new nanoid IDs
  - [ ] Updates article_tags.article_id
  - [ ] Updates article_embeddings.article_id
  - [ ] Updates articles.id
  - [ ] Runs in single transaction
- [ ] store_article() uses nanoid.generate() instead of uuid.uuid4()
- [ ] Verification that all article_tags and embeddings are preserved

### Add After Validation (v1.6.x)

- [ ] CLI command to run migration with `--dry-run` option
- [ ] Backup creation before migration
- [ ] Rollback capability

### Future Consideration (v2+)

- [ ] Old ID lookup table (for bookmarks/external references)

---

## Sources

- [nanoid Python library](https://pypi.org/project/nanoid/) (HIGH confidence)
- Code analysis: `src/storage/sqlite.py` store_article() (HIGH confidence)
- Code analysis: `src/utils/__init__.py` generate_article_id() (HIGH confidence)
- Database inspection: ~/Library/Application Support/rss-reader/rss-reader.db (HIGH confidence)

---

*Feature research for: nanoid ID migration*
*Researched: 2026-03-25*
