# Architecture Research: Article List Enhancements

**Domain:** CLI RSS Reader - Article Display Enhancements
**Researched:** 2026-03-23
**Confidence:** HIGH

## Executive Summary

Adding ID/tags display columns and a detail view to the existing CLI application requires minimal architectural changes. The existing data model already supports these features: `ArticleListItem` has an `id` field, and `get_article_tags()` already exists in `db.py`. The primary work involves modifying the CLI output formatting in `cli.py` and adding a new query function in `articles.py`.

## Integration with Existing Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer (click)                     │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ feed.*   │  │ article.*│  │   tag.*  │  │  repo.*  │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
├───────┴─────────────┴─────────────┴─────────────┴───────────┤
│                    Business Logic Layer                       │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ articles │  │  feeds   │  │   tags   │  │  github  │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
├───────┴─────────────┴─────────────┴─────────────┴───────────┤
│                      Data Layer (SQLite)                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  feeds | articles | github_repos | github_releases  │    │
│  │  tags  | article_tags                               │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Location | Change |
|-----------|----------------|----------|--------|
| `cli.py` | Click commands, output formatting | `src/cli.py` | MODIFY - add detail command, modify list display |
| `articles.py` | Article queries, returns `ArticleListItem` | `src/articles.py` | MODIFY - add `get_article_detail()` |
| `db.py` | Connection, schema, tag CRUD | `src/db.py` | NO CHANGE needed |
| `models.py` | Dataclass definitions | `src/models.py` | EXTEND - add `ArticleDetail` if needed |

## New vs Modified Components

| Component | Action | Reason |
|-----------|--------|--------|
| `article list` display | MODIFY | Add ID and tags columns to output format |
| `articles.py` | MODIFY | Add `get_article_detail()` function |
| `cli.py` | MODIFY | Add `article show` command |
| `models.py` | EXTEND | Add `ArticleDetail` dataclass (optional) |
| `db.py` | NO CHANGE | `get_article_tags()` already exists |

## Build Order

Given dependencies:

### Step 1: Add `get_article_detail()` to `articles.py`
- No CLI changes yet
- Can be tested independently via Python import
- Returns structured data including tags
- Handle both feed articles and GitHub releases (current `get_article()` only handles feed articles)

### Step 2: Add `article show` command to `cli.py`
- Depends on `get_article_detail()`
- Straightforward output formatting
- Show all fields: title, source, date, tags, link, description/content

### Step 3: Modify `article list` display columns
- Uses existing `get_article_tags()` per-article call (N+1 pattern - acceptable for MVP)
- Modify format string to include ID and tags
- New format: `ID | Tags | Title | Source | Date`

## Data Flow

### Article List with ID/Tags Column

```
cli.article_list()
    │
    ▼
articles.list_articles_with_tags(limit, feed_id, tag, tags)
    │  (returns list of ArticleListItem with id, title, source_type, etc.)
    ▼
for each article:
    │
    ▼
db.get_article_tags(article.id)   -- One query per article (N+1)
    │
    ▼
format: "[tag1][tag2] Title | Source | Date"
    │
    ▼
click.echo() output
```

### Article Detail View

```
User runs: article show <article-id>
    │
    ▼
cli.article_show(article_id)
    │
    ▼
articles.get_article_detail(article_id)
    │
    ├── articles.get_article(article_id)     # Get article from DB
    │       │
    │       ▼
    │       db.get_connection().execute()   # SELECT from articles + JOIN feeds
    │
    └── db.get_article_tags(article_id)    # Get tags for article
            │
            ▼
            db.get_connection().execute()    # SELECT from tags + article_tags
    │
    ▼
Return ArticleDetail(article=ArticleListItem, tags=list[str])
    │
    ▼
cli formats via click.secho():
    - Title (large)
    - Source: feed_name or repo@tag
    - Date: pub_date
    - Tags: [tag1] [tag2] [tag3]
    - Link: url (if exists)
    - Description: first 200 chars (if exists)
    - Content: full content or "No content stored" (optional)
```

## Performance Considerations

### N+1 Query Problem in List View

**Issue:** Current `article list` with tags calls `get_article_tags()` per article:
```python
for article in articles:
    article_tags = get_article_tags(article.id)  # One query per article
```

**Impact:** With 20 articles (default limit), this is 21 queries.

**Recommendation:** Accept N+1 for MVP. List view is bounded by `--limit` (default 20, user-controlled).

**If performance becomes an issue later:**
```python
def list_articles_with_tags_batch(article_ids: list[str]) -> dict[str, list[str]]:
    """Batch fetch tags for multiple articles in single query."""
    placeholders = ",".join("?" * len(article_ids))
    cursor.execute(f"""
        SELECT at.article_id, t.name
        FROM article_tags at
        JOIN tags t ON at.tag_id = t.id
        WHERE at.article_id IN ({placeholders})
        ORDER BY t.name
    """, article_ids)
    # Build dict: article_id -> [tag_names]
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: SQL Queries in CLI

**What:** Putting `SELECT` statements directly in click command handlers
**Why bad:** Scatters database logic, violates layered architecture
**Instead:** Add functions to `articles.py` and call from CLI

### Anti-Pattern 2: Over-Engineering Detail View

**What:** Building a full pager, markdown renderer, or content fetch
**Why bad:** Scope creep, complexity beyond CLI tool needs
**Instead:** Simple text output of stored fields. User opens link in browser for full content.

### Anti-Pattern 3: Duplicate Query Logic

**What:** Creating `get_article()` variant for detail view instead of extending existing function
**Why bad:** Code duplication, maintenance burden
**Instead:** Extend `get_article()` to handle both feed and GitHub sources, or create `get_article_detail()` that composes existing functions

## Integration Points

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| cli.py -> articles.py | Function call | `article_show()` calls `get_article_detail()` |
| cli.py -> db.py | Function call | `get_article_tags()` for per-article tag lookup |
| articles.py -> db.py | Function call + SQL | `get_article()` uses raw SQL via `get_connection()` |

## Suggested Implementation Details

### Option A: Extend `ArticleListItem` for Detail View

Reuse existing dataclass, add tags as a computed property or second return value:

```python
# In articles.py
def get_article_detail(article_id: str) -> Optional[tuple[ArticleListItem, list[str]]]:
    """Returns (article, tags) tuple or None if not found."""
    article = get_article(article_id)
    if not article:
        return None
    tags = get_article_tags(article_id)
    return (article, tags)
```

**Pros:** No new dataclass needed, flexible
**Cons:** Tuple return type less self-documenting

### Option B: New `ArticleDetail` Dataclass

```python
# In models.py
@dataclass
class ArticleDetail:
    """Full article with all related data for detail view."""
    article: ArticleListItem
    tags: list[str]
    feed_name: str  # from JOIN
    content: Optional[str]  # full content if stored
```

**Pros:** Self-documenting, IDE autocomplete works
**Cons:** Another dataclass to maintain

### Recommendation

Use Option A (tuple return) for MVP to minimize changes. Promote to Option B if detail view gains more fields.

---

*Architecture research for: Article List Enhancements*
*Researched: 2026-03-23*
