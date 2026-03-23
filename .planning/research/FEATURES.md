# Feature Research: Article List Enhancements

**Domain:** CLI tool - article list display and detail view enhancements
**Researched:** 2026-03-23
**Confidence:** HIGH (based on established CLI conventions and existing codebase patterns)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Article ID in list view | Needed to reference specific articles for tagging/untagging | LOW | Show truncated ID (first 8 chars) like `feed list` does |
| Explicit tags column | Tags currently shown as `[tag]` in title, hard to scan | LOW | Add separate column or `--verbose` already shows tags |
| Detail view command | Want to see full article without opening browser | LOW | Reuse `get_article()` already exists in `articles.py` |
| Open article link | Quick action to open article in browser | LOW | Use `open` command on macOS, `xdg-open` on Linux |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Compact tag display in list | Visual scanning of topics without `--verbose` | LOW | Show tags inline after title or as separate column |
| Full content display in detail | View article content without leaving CLI | MEDIUM | Content stored in DB, just need formatting |
| Tag filtering in detail view | "Show me all articles with tag X" is natural | LOW | Already implemented in `article list --tag` |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Pretty-printed HTML rendering | "Make it look like a webpage" | Terminal limitations, markdown is better for CLI | Show markdown-formatted content |
| Pager/less integration | Long articles scroll too fast | Adds complexity, users can pipe to less | Support `article view --id X \| less` |
| Color-coded tags by category | Visual organization | Arbitrary color assignment, no categories exist | Keep simple string tags |
| Inline article content preview | See more without detail command | List becomes too long, defeats purpose | Detail view command |

## Feature Dependencies

```
[Detail View Command]
    └──requires──> [get_article() function] (already exists in articles.py)
    └──requires──> [Article ID display in list] (to know what ID to view)

[Tags in List View]
    └──requires──> [get_article_tags() function] (already exists in db.py)
    └──enhances──> [Article List Command]

[Open Link in Browser]
    └──requires──> [Platform-specific open command]
```

### Dependency Notes

- **Detail view requires article ID:** Users need to know article IDs to use detail view - list must show IDs first
- **Tags already available:** `get_article_tags()` exists and is already called in verbose mode - just need to expose in non-verbose
- **No new database queries needed:** All required functions already exist

## MVP Definition

### Launch With

Minimum viable product for list enhancements.

- [ ] **Article ID column in list** — Show truncated ID (8 chars) like `feed list` does, enabling reference for tagging
- [ ] **Tags column in list view** — Show tags as comma-separated string in dedicated column (non-verbose)
- [ ] **Article detail command** — `article view <id>` showing full title, source, date, tags, link, full description/content

### Add After Validation

Features to add once core is working.

- [ ] **Open in browser** — `article open <id>` to open article link in default browser
- [ ] **Content column in detail view** — Show full `content` field if stored (vs just description)
- [ ] **Markdown rendering** — Format content with basic markdown (headers, lists, code) in detail view

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] **JSON output option** — `article list --format json` for scripting
- [ ] **Export article** — Save article to file (markdown, HTML)
- [ ] **Share article** — Copy link to clipboard

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Article ID in list | HIGH | LOW | P1 |
| Tags column in list | HIGH | LOW | P1 |
| Detail view command | HIGH | LOW | P1 |
| Open in browser | MEDIUM | LOW | P2 |
| Full content in detail | MEDIUM | LOW | P2 |
| Markdown rendering | MEDIUM | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Existing System Integration Points

Based on reading the existing codebase:

| Existing Component | How Enhancements Extend It |
|--------------------|---------------------------|
| `src/articles.py` `get_article()` | Already exists, returns ArticleListItem - use for detail view |
| `src/db.py` `get_article_tags()` | Already called in verbose mode - expose in non-verbose list |
| `src/cli.py` `article_list` | Modify to show ID column and tags column in non-verbose mode |
| `src/cli.py` `feed list` | Reuse ID truncation pattern: `{id[:8]}...` |

### Changes Required

**`src/cli.py` - `article_list` command:**
- Non-verbose output: Change from `{tag_str}{title[:50-len(tag_str)]}` to include ID and separate tags column
- Current format: `{tag_str}{title[:50-len(tag_str)]} | {source[:25]} | {pub_date[:10]}`
- New format: `{id[:8]} | {title[:40]} | {tags_str} | {source[:20]} | {pub_date[:10]}`

**`src/cli.py` - New `article_view` command:**
- Use `get_article(article_id)` to fetch single article
- Display full details: title, all tags, source, date, link, description, content
- Show content if available, fallback to description

**`src/cli.py` - New `article_open` command (optional P2):**
- Use `get_article(article_id)` to get link
- Call `open` (macOS) or `xdg-open` (Linux) via `subprocess`

## CLI Convention Reference

Based on existing `feed list` and `repo list` patterns:

| Pattern | Example | Usage |
|---------|---------|-------|
| Truncated ID | `{id[:8]}...` | Feed list, repo list - show enough to identify |
| Verbose flag | `--verbose, -v` | Show expanded information |
| Column separator | ` \| ` | Pipe with spaces between columns |
| Header row | `click.secho("ID \| Name \| ...")` | Column headers |
| Separator line | `click.secho("-" * 60)` | Visual divider |

## Sources

- Existing codebase: `src/cli.py` (article_list, feed_list, repo_list commands)
- Existing codebase: `src/articles.py` (get_article function)
- Existing codebase: `src/db.py` (get_article_tags function)
- Click documentation: Column formatting in CLI (HIGH confidence)

---

*Feature research for: Article List Enhancements*
*Researched: 2026-03-23*
