# Phase 7: Tagging System - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Add article tagging system for organizing, categorizing, and filtering content. Includes:
- Tag CRUD CLI commands
- Manual article tagging via CLI
- Automatic tagging via keyword matching rules
- AI-powered automatic tag generation via embedding clustering
- Tag-based article filtering
- Tag display in article list

</domain>

<decisions>
## Implementation Decisions

### Tag Management CLI
- **D-01:** `tag add <name>` — Create a new tag
- **D-02:** `tag list` — List all tags with article counts
- **D-03:** `tag remove <tag>` — Remove a tag (unlinks from all articles)

### Article Tagging
- **D-04:** Manual tagging via `article tag <article-id> <tag>`
- **D-05:** Auto tagging via keyword matching + AI clustering

### Automatic Tagging: Keyword Matching
- **D-06:** Rule configuration file: `~/.radar/tag-rules.yaml`
- **D-07:** CLI management: `tag rule add/remove/list/edit`
- **D-08:** Rule format: keywords (plain text) + regex patterns
- **D-09:** Rule conflict: apply ALL matching tags (not first-match-only)

### Automatic Tagging: AI Clustering
- **D-10:** Embedding model: `sentence-transformers` (all-MiniLM-L6-v2)
- **D-11:** Vector storage: `sqlite-vec` (SQLite extension)
- **D-12:** Clustering: DBSCAN or k-means for automatic topic discovery
- **D-13:** Auto-generate tags directly, user can delete unwanted ones

### Tag-Based Filtering
- **D-14:** `--tag` — Single tag filter (must have)
- **D-15:** `--tags a,b` — Multiple tags with OR logic (has a OR has b)
- **D-16:** No AND logic needed

### Tag Display
- **D-17:** Inline brackets format: `[AI][News] Article Title`

### Claude's Discretion
- Exact clustering hyperparameters (DBSCAN eps, min_samples)
- `tag rule edit` interaction style (interactive vs batch)
- Article clustering trigger timing (on fetch, on demand, scheduled)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### CLI Patterns
- `src/cli.py` — Existing CLI structure, command group patterns
- `src/models.py` — Data models (Feed, Article, GitHubRepo)

### Database
- `src/db.py` — SQLite schema, existing tables

No external specs — requirements fully captured in decisions above

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Click CLI framework already used (follow existing command patterns)
- Existing `list_articles()`, `search_articles()` in `src/articles.py`
- SQLite connection with WAL mode already configured

### Established Patterns
- Dataclass models in `models.py`
- Error handling via custom exceptions (FeedNotFoundError, RepoNotFoundError)
- Verbose flag pattern in CLI commands

### Integration Points
- New `tags` and `article_tags` tables in SQLite
- New `tag_rules` table for keyword/regex rules
- Vector storage via sqlite-vec extension
- Article tagging in `articles.py` queries

</code_context>

<specifics>
## Specific Ideas

- Rule file: `~/.radar/tag-rules.yaml` with structure:
  ```yaml
  tags:
    ai:
      keywords:
        - "machine learning"
        - "deep learning"
      regex:
        - "LLM|GPT|Claude"
  ```
- CLI commands for rule management:
  - `tag rule add <tag> <keyword1> [keyword2...]`
  - `tag rule add <tag> --regex <pattern>`
  - `tag rule list`
  - `tag rule remove <tag> [--keyword <kw>|--regex <pattern>]`

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-tagging-system*
*Context gathered: 2026-03-23*
