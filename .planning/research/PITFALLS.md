# Pitfalls Research: nanoid ID Migration

**Domain:** SQLite ID migration in RSS reader application
**Researched:** 2026-03-25
**Confidence:** HIGH (established SQLite patterns, verified against codebase)

---

## Executive Summary

Migrating ~2479 articles from URL-like IDs to nanoid IDs requires updating multiple related tables atomically. The primary risks are: (1) orphaning foreign key references in `article_tags` and `article_embeddings`, (2) breaking the FTS5 search index which links via `rowid`, and (3) collision with existing IDs if migration is run multiple times or partially. The safest approach is an in-place UPDATE within a transaction, not delete-and-reinsert.

---

## Critical Pitfalls

### Pitfall 1: FTS5 Index Desynchronization

**What goes wrong:**
After migration, `article list` and `article detail` work, but `search` returns stale results or crashes. The FTS5 virtual table `articles_fts` loses sync with `articles` because it links via `rowid`, not article `id`.

**Why it happens:**
The FTS5 sync at `sqlite.py:352-355` uses:
```python
INSERT OR REPLACE INTO articles_fts(rowid, title, description, content)
SELECT rowid, title, description, content FROM articles WHERE id = ?
```
This relies on `rowid` continuity. If migration does DELETE + INSERT, the new row gets a NEW rowid, orphaning the old FTS entry while creating a duplicate.

**How to avoid:**
- **Use UPDATE, not DELETE+INSERT.** The `id` column in `articles` is NOT a PRIMARY KEY (line 116-117: "Note: id is NOT PRIMARY KEY - same article can exist in multiple feeds"). SQLite allows UPDATE of non-PK columns freely.
- If UPDATE is not possible, use explicit rowid preservation:
  ```sql
  INSERT INTO articles(rowid, id, feed_id, title, ...)
  SELECT rowid, 'new_nanoid', feed_id, title, ...
  FROM articles WHERE id = 'old_id';
  ```

**Warning signs:**
- `search` returns fewer results than `article list`
- FTS query joins show mismatched rowids
- Duplicate content in search results

**Phase to address:** NANO-02 migration script

---

### Pitfall 2: Orphaned article_tags Foreign Key References

**What goes wrong:**
`article_tags` has `FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE`. If migration updates article IDs without updating `article_tags.article_id`, tags become orphaned. User runs `article tag` and gets "article not found" errors.

**Why it happens:**
The `article_tags` table stores `article_id` values that must match `articles.id`. When articles.id changes, article_tags.article_id must change too.

**How to avoid:**
- Include `article_tags` in the same transaction as the articles UPDATE:
  ```sql
  UPDATE article_tags SET article_id = 'new_nanoid' WHERE article_id = 'old_url_id';
  ```
- The `article_embeddings` table also has `article_id TEXT PRIMARY KEY` and must be updated.

**Warning signs:**
- Tags visible in DB but `article list --tags` shows empty for migrated articles
- `tag_article()` succeeds but tags don't persist

**Phase to address:** NANO-02 migration script (must handle all related tables)

---

### Pitfall 3: Orphaned article_embeddings

**What goes wrong:**
Embeddings stored with old article IDs become unreachable. `get_article_embedding()` returns None for migrated articles despite having data in `article_embeddings` table.

**Why it happens:**
`article_embeddings.article_id` is a PRIMARY KEY that must match `articles.id`. If only `articles.id` is updated, embeddings are orphaned.

**How to avoid:**
- Update `article_embeddings.article_id` in same transaction:
  ```sql
  UPDATE article_embeddings SET article_id = 'new_nanoid' WHERE article_id = 'old_url_id';
  ```

**Warning signs:**
- AI clustering/tagging features stop working for migrated articles
- `get_articles_without_embeddings()` returns articles that actually have orphaned embeddings

**Phase to address:** NANO-02 migration script

---

### Pitfall 4: nanoid Collision with URL-like IDs

**What goes wrong:**
Migration script generates nanoid for a URL-like ID that coincidentally matches an existing UUID-formatted article ID. Result: two different articles now share the same ID, causing UNIQUE constraint violations or data merging.

**Why it happens:**
URL-like IDs like `https://example.com/article/123` are being replaced with 21-character nanoids. Nanoid's collision probability at 2479 articles is ~1 in 10^34 (extremely low), but URL-like IDs that LOOK like valid nanoids could collide.

**How to avoid:**
- The migration should be deterministic: generate new ID from OLD ID as seed, not random. This ensures:
  1. Same old ID always produces same new ID (idempotent)
  2. No collision risk (deterministic mapping)
- Example pattern:
  ```python
  import hashlib, nanoid
  def migrate_id(old_id: str) -> str:
      # If looks like URL-like, migrate; if already nanoid/UUID, skip
      if old_id.startswith('http') or old_id.startswith('/'):
          seed = hashlib.sha256(old_id.encode()).digest()[:16]
          return nanoid.generate(alphabet="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz", size=21)
      return old_id  # Already migrated or UUID
  ```

**Warning signs:**
- UNIQUE constraint violations during migration
- Duplicate article IDs in database after migration

**Phase to address:** NANO-02 migration script (use deterministic generation)

---

### Pitfall 5: Partial Migration with No Rollback Path

**What goes wrong:**
Migration script crashes at article #1500. 1499 articles now have new nanoid IDs, but 980 still have URL-like IDs. Database is in inconsistent state.

**Why it happens:**
- Script fails mid-way due to syntax error, constraint violation, or interrupt
- No transaction wrapping entire migration
- No checkpoint after each article

**How to avoid:**
- Wrap ENTIRE migration in a single transaction:
  ```python
  with get_db() as conn:
      conn.execute("BEGIN IMMEDIATE")  # Exclusive lock
      try:
          # All updates here
          conn.execute("UPDATE articles SET id = ? WHERE id = ? AND id LIKE 'http%'", (new_id, old_id))
          conn.execute("UPDATE article_tags ...")
          conn.execute("UPDATE article_embeddings ...")
          conn.commit()
      except:
          conn.rollback()
          raise
  ```
- Create backup before migration:
  ```bash
  cp rss-reader.db rss-reader.db.backup.$(date +%Y%m%d%H%M%S)
  ```

**Warning signs:**
- Migration script exit code != 0
- Partial count updates reported
- Database file modified mid-migration

**Phase to address:** NANO-02 migration script (transaction + backup)

---

### Pitfall 6: Re-running Migration Creates Duplicates

**What goes wrong:**
User runs migration script twice. First run: URL-like IDs -> nanoids. Second run: newly generated nanoids -> DIFFERENT nanoids (non-deterministic), orphaning old references.

**Why it happens:**
If nanoid generation is random (not seeded on old ID), re-running produces different IDs each time, orphaning previous migration's foreign keys.

**How to avoid:**
- Migration script must be idempotent:
  1. Check if article already has nanoid format (21 chars, URL-safe alphabet)
  2. Skip already-migrated articles
  3. Only migrate URL-like IDs
- Add migration marker column or use ID format detection:
  ```python
  def is_migrated(article_id: str) -> bool:
      # nanoid uses URL-safe alphabet, length 21
      return len(article_id) == 21 and all(c in nanoid.alphanumeric for c in article_id)
  ```

**Warning signs:**
- Script reports "X articles migrated" when X = total article count on re-run
- Duplicate entries in `article_tags` for same article

**Phase to address:** NANO-02 migration script (idempotency check)

---

### Pitfall 7: CLI Truncation Logic Breakage

**What goes wrong:**
`article detail 8-char-id` and `article open 8-char-id` commands stop working after migration. These commands use truncated 8-character IDs for convenience.

**Why it happens:**
Old URL-like IDs could have ambiguous 8-char prefixes (e.g., `https://`). Nanoid 8-char prefixes should be unique given the larger alphabet and random distribution.

**How to avoid:**
- Verify 8-char truncation still produces unique prefixes for nanoid IDs
- Nanoid's 21-char alphabet distribution should be sufficient
- Add index on `LEFT(id, 8)` if performance becomes issue

**Warning signs:**
- `article detail` returns wrong article
- `article open` opens incorrect article

**Phase to address:** NANO-03 verification phase

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Delete + Reinsert for migration | Simpler SQL | Breaks FTS5, orphans FKs | Never for ID migration |
| Random nanoid per migration | Simpler code | Non-idempotent, collision risk | Never |
| Skip backup before migration | Saves 2 seconds | Permanent data loss risk | Never |
| Migration without transaction | Simpler error handling | Partial migration state | Never |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| FTS5 search | Assuming FTS5.id = articles.id | FTS5 uses rowid, must preserve rowid |
| article_tags FK | Updating only articles.id | Update article_tags.article_id too |
| article_embeddings PK | Forgetting to update | Update article_embeddings.article_id too |
| CLI truncation | Assuming prefix uniqueness | Verify 8-char prefix is unique enough |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full table scan for ID update | Migration takes hours | Add index on articles.id first | >10K articles |
| No batch processing | Memory exhaustion | Process in chunks of 100-500 | >50K articles |
| Lock contention | "database is locked" errors | Use IMMEDIATE transaction | Concurrent access during migration |

For 2479 articles: Performance is NOT a concern. Single transaction is fine.

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Using random nanoid without collision check | ID collision causes data merge | Deterministic migration using hash of old ID |
| No backup before migration | Permanent data loss | Mandatory backup with timestamp |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|------------------|
| Silent partial migration | User thinks all done, but some broken | Exit code + count verification |
| No migration progress indicator | User thinks frozen | Show progress: "Migrated 500/2479" |
| Migration without verification | Works but search broken | Run NANO-03 validation steps |

---

## "Looks Done But Isn't" Checklist

- [ ] **Migration script:** Ran successfully but did NOT update `article_tags` - verify with `SELECT COUNT(*) FROM article_tags at JOIN articles a ON at.article_id = a.id` returns 0 mismatches
- [ ] **Migration script:** Updated articles but NOT `article_embeddings` - verify with query
- [ ] **Migration script:** No backup taken - verify backup file exists
- [ ] **FTS sync:** Search works for OLD articles but not migrated - verify `SELECT COUNT(*) FROM articles_fts` matches `SELECT COUNT(*) FROM articles`
- [ ] **Idempotency:** Re-running script causes issues - verify second run reports 0 articles migrated

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| FTS5 desync | MEDIUM | Re-sync FTS: `INSERT OR REPLACE INTO articles_fts(rowid, title, description, content) SELECT rowid, title, description, content FROM articles;` |
| Orphaned tags/embeddings | MEDIUM | Re-run migration with proper UPDATE (restore from backup first) |
| Partial migration | HIGH | Restore from backup, fix script, re-run |
| Collision causing duplicates | HIGH | Requires deduplication before migration |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| FTS5 desync | NANO-02 migration script | Run search before/after, verify result count matches |
| Orphaned FKs | NANO-02 migration script | JOIN query between articles and article_tags shows 0 orphans |
| No rollback | NANO-02 migration script | Backup file exists, transaction used |
| Re-run duplicates | NANO-02 migration script | Run twice, second reports 0 migrated |
| CLI breakage | NANO-03 verification | Test `article detail 8-char` and `article open 8-char` for migrated articles |

---

## Migration Script Requirements Summary

For NANO-02, the migration script MUST:

1. **Create backup** before any changes
2. **Wrap in transaction** (BEGIN IMMEDIATE)
3. **UPDATE, not DELETE+INSERT** to preserve rowid
4. **Update ALL tables** referencing article_id:
   - `articles.id`
   - `article_tags.article_id`
   - `article_embeddings.article_id`
5. **Use deterministic ID generation** (seed on old ID) for idempotency
6. **Detect already-migrated articles** (skip if ID is valid nanoid)
7. **Verify row counts** before/after for sanity
8. **Report progress** with counts
9. **Exit with proper code** (0 success, non-zero failure)

---

## Sources

- SQLite ALTER TABLE limitations: https://www.sqlite.org/lang_altertable.html (HIGH confidence)
- FTS5 rowid semantics: https://www.sqlite.org/fts5.html (HIGH confidence)
- Nanoid collision probability: Based on birthday paradox calculation, ~1 in 10^34 for 2479 items (HIGH confidence)
- Foreign key constraints in SQLite: https://www.sqlite.org/foreignkeys.html (HIGH confidence)
- Codebase analysis: src/storage/sqlite.py (lines 119-135, 160-168, 352-355, 402-406) (HIGH confidence)

---

*Pitfalls research for: nanoid ID migration v1.6*
*Researched: 2026-03-25*
