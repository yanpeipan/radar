# Pitfalls Research: Article List Enhancements and Detail View

**Domain:** CLI article management with SQLite backend
**Researched:** 2026-03-23
**Confidence:** HIGH

## Executive Summary

Adding ID display, tags column, and article detail view to an existing CLI RSS reader. The existing codebase has a critical N+1 query pattern in the article list command, missing content fetch in the detail function, and a schema limitation where GitHub releases cannot be tagged.

## Critical Pitfalls

### Pitfall 1: N+1 Query Problem in Tag Display

**What goes wrong:**
Article list takes 20+ database queries to display 20 articles with tags (1 initial query + 1 query per article for tags). Performance degrades linearly with article count.

**Why it happens:**
The existing code at `cli.py:210` calls `get_article_tags(article.id)` inside the article loop:

```python
for article in articles:
    article_tags = get_article_tags(article.id) if hasattr(article, 'id') else []
```

This executes a new SQL query for each iteration. For 20 articles, this is 21 database round-trips.

**Consequences:**
- List command becomes slow as article count grows (100 articles = 101 queries)
- Database lock contention under concurrent access
- Poor user experience with noticeable delay on each list command

**Prevention:**
Fetch tags in a single JOIN query or batch query:

```python
# Option 1: JOIN in main query (recommended)
cursor.execute("""
    SELECT a.*, GROUP_CONCAT(t.name) as tags
    FROM articles a
    LEFT JOIN article_tags at ON a.id = at.article_id
    LEFT JOIN tags t ON at.tag_id = t.id
    GROUP BY a.id
    LIMIT ?
""", (limit,))

# Option 2: Batch fetch after main query
article_ids = [a.id for a in articles]
cursor.execute("""
    SELECT at.article_id, t.name
    FROM article_tags at
    JOIN tags t ON at.tag_id = t.id
    WHERE at.article_id IN ({})
""".format(','.join('?' * len(article_ids))), article_ids)
# Build tag map: {article_id: [tag1, tag2]}
```

**Warning signs:**
- `len(articles) + 1` queries logged per list command
- Article list takes >100ms for 20 articles
- sqlite3.OperationalError: "database is locked" during list

**Phase to address:**
Phase implementing article list enhancements (should be fixed as part of this feature, not deferred)

---

### Pitfall 2: Missing Content Field in Article Detail

**What goes wrong:**
`articles.py:get_article()` returns only: id, feed_id, feed_name, title, link, guid, pub_date, description. The `content` field (full article body) is never fetched, even though it exists in the database.

**Why it happens:**
The SQL query in `get_article()` at line 138-147 does not include the `content` column:

```python
cursor.execute("""
    SELECT a.id, a.feed_id, f.name as feed_name, a.title, a.link,
           a.guid, a.pub_date, a.description
    FROM articles a
    ...
""")
```

**Consequences:**
- Article detail view shows only description/excerpt, not full content
- Users cannot read full article text stored in database
- Content field exists but is inaccessible

**Prevention:**
Add `content` to the SELECT clause:

```python
cursor.execute("""
    SELECT a.id, a.feed_id, f.name as feed_name, a.title, a.link,
           a.guid, a.pub_date, a.description, a.content
    FROM articles a
    ...
""")
```

**Warning signs:**
- `article detail` output shows empty content section
- Users report "content not found" despite content existing

**Phase to address:**
Phase implementing article detail view (must include content fetch)

---

### Pitfall 3: GitHub Releases Cannot Be Tagged (Schema Limitation)

**What goes wrong:**
Tags only link to `articles.id`, but GitHub releases have separate IDs in `github_releases` table. Running `article tag <github-release-id> <tag>` silently fails or creates orphan links.

**Why it happens:**
The `article_tags` table has foreign key to `articles.id`:

```sql
FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
```

GitHub releases are stored in `github_releases` table with their own `id` primary key. There is no `github_release_tags` table.

**Consequences:**
- Users cannot tag GitHub releases
- `article tag` command succeeds but tag association is silently lost for GitHub items
- Tag filtering may show unexpected results when mixing feed articles and GitHub releases

**Prevention:**
1. **Option A (Correct):** Add `github_release_tags` table parallel to `article_tags`
2. **Option B (Workaround):** Detect GitHub release ID format and show "Tags not supported for GitHub releases" error
3. **Option C (Design change):** Unify by storing GitHub releases as articles with `source_type='github'` and copy tags

**Warning signs:**
- `article tag <github-id> <tag>` succeeds with no error but `get_article_tags(<github-id>)` returns empty
- Tag count doesn't match when filtering by tag that should include GitHub releases

**Phase to address:**
Phase implementing tagging integration with GitHub releases (requires schema decision)

---

### Pitfall 4: ID Column Width and Truncation Inconsistency

**What goes wrong:**
Displaying full UUIDs (36 chars) in list view pushes other columns off-screen. But using truncated IDs (8 chars) means users cannot copy-paste full ID for commands like `article tag <id>`.

**Why it happens:**
- `feed list` truncates to 8 chars: `{f.id[:8]}...` (line 116)
- Article tag commands require full ID
- No `--verbose` flag for article list to show full IDs

**Consequences:**
- Users must use truncated ID which doesn't work in commands
- "Feed not found" errors when truncated ID doesn't match
- Inconsistent UX between list commands

**Prevention:**
1. Add `--verbose` / `-v` flag to article list showing full IDs
2. Use consistent ID column width: 8 chars truncated with `...` suffix
3. In verbose mode, show ID on separate line or in header
4. Ensure error messages suggest using `--verbose` for full ID

**Warning signs:**
- User reports "article tag fails with truncated ID"
- Inconsistent ID display between `feed list` and `article list`

**Phase to address:**
Phase implementing article list ID column display

---

### Pitfall 5: Tags Column Truncation Breaks Alignment

**What goes wrong:**
With many tags, the tag string makes the title column extremely narrow or breaks line alignment entirely.

**Why it happens:**
Current code (line 211, 224):
```python
tag_str = "".join(f"[{t}]" for t in article_tags)
click.secho(f"{tag_str}{title[:50-len(tag_str)]} | {source[:25]} | {pub_date[:10]}")
```

If an article has tags `[python][machine-learning][ai]`, the tag string is 31 chars, leaving only 19 chars for title in a 50-char budget.

**Consequences:**
- Long titles get severely truncated
- Tag-heavy articles show almost no title
- Output alignment breaks when truncation varies

**Prevention:**
1. Move tags to their own column or end of line
2. Limit tag display to first N tags with `+N` indicator: `[python][machine-learning]+3`
3. In verbose mode, show all tags on separate line
4. Use consistent column widths with horizontal scrolling for wide terminals

**Warning signs:**
- Titles truncated to 5-10 characters for tagged articles
- Tag display varies wildly between articles

**Phase to address:**
Phase implementing article list tags column

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Per-article tag query in loop | Simpler code, no query changes needed | N+1 performance problem | Never - must batch |
| Skip content in detail view | Fewer fields to handle | Feature incomplete | Never |
| Ignore GitHub release tagging | No schema changes needed | Tags don't work for 50% of sources | MVP only, must address before release |
| Truncate IDs without verbose full-ID option | Cleaner display | Cannot use IDs in commands | Never |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| SQLite | N+1 queries in loops | Use JOIN or batch WHERE IN |
| CLI display | Hardcoded column widths | Calculate based on terminal width or use separate lines |
| Tags + GitHub | Assuming unified article ID space | Detect source type, handle separately or error clearly |
| Detail view | Forgetting content field | Explicitly include all needed columns in SELECT |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| N+1 tag queries | Query count = O(articles) | Single JOIN query | At >10 articles |
| No index on article_tags.article_id | Slow tag lookups | idx_article_tags_tag_id exists, need composite | At >1000 articles |
| Full content in list query | Memory bloat | Only fetch content in detail view | At >100 articles |

Note: `idx_article_tags_tag_id` exists per `db.py:173`, but queries typically filter by `article_id` which needs its own index. Current index is on `tag_id` only.

---

## "Looks Done But Isn't" Checklist

- [ ] **Tags in list:** Verified with 20+ articles, each having 3+ tags - not just single article test
- [ ] **Tags in list:** Verified N+1 is fixed - check query count in logs
- [ ] **Article detail:** Shows full content field - verify with article that has content
- [ ] **Article detail:** Works for both feed articles AND GitHub releases
- [ ] **ID column:** Full ID shown in verbose mode, usable in commands
- [ ] **ID column:** Truncated in normal mode doesn't break alignment
- [ ] **Tag filtering:** Combined with ID display doesn't cause truncation issues

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| N+1 queries deployed | LOW | Add JOIN, redeploy; performance immediately improves |
| Missing content field | LOW | Add to SELECT, redeploy; no data migration needed |
| GitHub release tags broken | MEDIUM | Add migration for github_release_tags table, backfill existing releases |
| ID truncation user confusion | LOW | Add verbose flag showing full ID, update error messages |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| N+1 query problem | Phase implementing list with tags | Log query count, verify single query with EXPLAIN |
| Missing content field | Phase implementing detail view | Manual test: view article known to have content |
| GitHub release tagging | Phase integrating tags with GitHub source | Tag a GitHub release, verify persistence |
| ID column width | Phase implementing ID display | Test truncated display and verbose full-ID |
| Tags truncation | Phase implementing tags column | Test with articles having 5+ tags |

---

## Sources

- [SQLite Query Planning: Avoid N+1](https://www.sqlite.org/queryplanner.html) (HIGH confidence - official docs)
- [CLI Design Best Practices](https://clig.dev/) (HIGH confidence - industry guidelines)
- Existing codebase: `cli.py:210` shows N+1 pattern, `articles.py:get_article()` missing content

---

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| N+1 query pitfalls | HIGH | Clear pattern in existing code, well-known SQLite issue |
| Missing content field | HIGH | Obvious from code inspection, SELECT clause explicitly omits column |
| GitHub tagging limitation | HIGH | Schema FK constraint prevents cross-table tagging |
| CLI display issues | MEDIUM | General UX patterns, specific thresholds may need user testing |
| Performance impact | MEDIUM | Depends on article count scale, but N+1 is clear issue |

---

*Pitfalls research for: Article list ID/tags columns and detail view in Python CLI RSS reader*
*Researched: 2026-03-23*
