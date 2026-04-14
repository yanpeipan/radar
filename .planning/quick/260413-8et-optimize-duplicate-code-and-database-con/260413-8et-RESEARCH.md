# Quick Task 260413-8et: Optimize Duplicate Code and Database Connection Handling

**Task:** Optimize duplicate code and database connection handling in feedship

## Research Findings

### 1. Connection Pooling for SQLite

**Options:**
- `sqlite3.connect()` per call (current) - high overhead
- Module-level connection caching with `threading.local()`
- Third-party pool library (e.g., `persistence`, `sqlamp`)

**Best Practice for SQLite:**
- SQLite has limited concurrent write support
- WAL mode + single connection with proper locking is often sufficient
- Consider: module-level cached connection with checks for有效性

```python
# Recommended pattern
_connection = None

def get_connection():
    global _connection
    if _connection is None:
        _connection = sqlite3.connect(...)
        _connection.execute("PRAGMA journal_mode=WAL")
    return _connection
```

### 2. Duplicate Function Deduplication

**Issue:** `_normalize_published_at` and date utilities defined in both:
- `src/storage/sqlite/conn.py:98-177`
- `src/storage/sqlite/articles.py:24-110`

**Solution:** Move to shared module `src/storage/sqlite/utils.py`

### 3. UPSERT Pattern for store_article

**Current:** SELECT then INSERT/UPDATE (2 round trips)

**Better:** Use `INSERT ... ON CONFLICT DO UPDATE` (single transaction)

```sql
INSERT INTO articles (id, feed_id, title, ...)
VALUES (?, ?, ?, ...)
ON CONFLICT(guid) DO UPDATE SET
    title = excluded.title,
    ...
```

### 4. Code Structure Issues

**Duplicate imports:** `json` imported multiple times in `fetch.py:161,260,263,403,406`
- Move to module top-level import

**Duplicate metadata parsing logic in fetch.py**
- Extract to `parse_feed_metadata()` helper

### Implementation Priority

1. **High**: Deduplicate utility functions (low risk, high maintainability)
2. **High**: Refactor store_article to UPSERT (performance)
3. **Medium**: Connection caching (performance)
4. **Low**: Move imports to top-level (code quality)

## Integration Points

- `src/storage/sqlite/conn.py` - connection management
- `src/storage/sqlite/articles.py` - article CRUD
- `src/storage/sqlite/feeds.py` - feed CRUD
- `src/application/fetch.py` - async fetching

## Risks

- Connection caching: ensure proper close() on shutdown
- UPSERT: test with existing articles to verify update behavior
- Moving functions: update all import references
