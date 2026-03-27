---
phase: quick
plan: 260327-ghv
type: execute
wave: 1
depends_on: []
files_modified:
  - src/cli/article.py
  - src/application/tags.py
  - src/application/related.py
autonomous: true
must_haves:
  truths:
    - "CLI article.py is under 200 lines"
    - "Business logic moved to application layer"
    - "article tag command works"
    - "article related command works"
  artifacts:
    - path: "src/cli/article.py"
      max_lines: 200
    - path: "src/application/tags.py"
      provides: "Tagging business logic (auto-tag, rules, manual)"
      exports: ["auto_tag_articles", "apply_rules_to_untagged", "tag_article_manual"]
    - path: "src/application/related.py"
      provides: "Related articles business logic"
      exports: ["get_related_articles_display"]
  key_links:
    - from: "src/cli/article.py"
      to: "src/application/tags.py"
      via: "import"
    - from: "src/cli/article.py"
      to: "src/application/related.py"
      via: "import"
---

<objective>
Keep src/cli/article.py under 200 lines by moving business logic to application layer. CLI layer should only handle: command definitions, option parsing, display formatting (Rich), error handling.
</objective>

<execution_context>
@/Users/y3/radar/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@src/cli/article.py (400 lines - needs refactoring)
@src/application/articles.py (existing application layer)
@src/storage/vector.py (get_related_articles, search_articles_semantic)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create src/application/tags.py</name>
  <files>src/application/tags.py</files>
  <action>
    Create new file `src/application/tags.py` with tagging business logic extracted from `src/cli/article.py` `article_tag` command.

    Extract and implement these three functions:

    1. `auto_tag_articles(eps: float = 0.3, min_samples: int = 3) -> dict[str, list[str]]`:
       - Import and call `run_auto_tagging(eps, min_samples)` from `src.tags.ai_tagging`
       - Return the tag_map directly

    2. `apply_rules_to_untagged(verbose: bool = False) -> int`:
       - Call `get_untagged_articles()` from `src.storage`
       - For each article, call `apply_rules_to_article(row["id"], row["title"], row["description"])` from `src.tags.tag_rules`
       - Return count of articles that were matched

    3. `tag_article_manual(article_id: str, tag_name: str) -> bool`:
       - Call `tag_article(article_id, tag_name)` from `src.storage.sqlite`
       - Return whether tagging succeeded

    Include proper docstrings explaining each function's purpose, args, and return values.
  </action>
  <verify>
    <automated>python -c "from src.application.tags import auto_tag_articles, apply_rules_to_untagged, tag_article_manual; print('OK')"</automated>
  </verify>
  <done>src/application/tags.py exists with 3 exported functions for tagging operations</done>
</task>

<task type="auto">
  <name>Task 2: Create src/application/related.py</name>
  <files>src/application/related.py</files>
  <action>
    Create new file `src/application/related.py` with related articles business logic extracted from `src/cli/article.py` `article_related` command.

    Implement:

    `get_related_articles_display(article_id: str, limit: int = 5, verbose: bool = False) -> list[dict[str, str]]`:
    - Call `get_related_articles(article_id=article_id, limit=limit)` from `src.storage`
    - For each result, calculate similarity: `max(0, round((1 - distance) * 100, 1))` if distance is not None
    - Format each result as dict with keys: title, url, similarity, document_preview (if verbose)
    - If no results and article exists but has no embedding, return special dict with key "no_embedding": True
    - Return list of formatted dicts

    Include proper docstrings.
  </action>
  <verify>
    <automated>python -c "from src.application.related import get_related_articles_display; print('OK')"</automated>
  </verify>
  <done>src/application/related.py exists with get_related_articles_display function</done>
</task>

<task type="auto">
  <name>Task 3: Refactor src/cli/article.py to under 200 lines</name>
  <files>src/cli/article.py</files>
  <action>
    Refactor `src/cli/article.py` to be under 200 lines by using application layer functions.

    **Remove these imports (now in application layer):**
    - Remove the dynamic import of `ai_tagging` module (lines 23-28)

    **Replace `article_tag` function body:**
    - Import `auto_tag_articles, apply_rules_to_untagged, tag_article_manual` from `src.application.tags`
    - Replace `run_auto_tagging(...)` call with `auto_tag_articles(...)`
    - Replace untagged articles loop with `apply_rules_to_untagged(verbose)`
    - Replace `tag_article(...)` with `tag_article_manual(article_id, tag_name)`

    **Replace `article_related` function body:**
    - Import `get_related_articles_display` from `src.application.related`
    - Replace inline logic with call to `get_related_articles_display(article_id, limit, verbose)`
    - Keep the display loop for Rich output

    **Keep these as-is (already thin CLI):**
    - `article_list` - calls application layer already
    - `article_view` - calls application layer already
    - `article_open` - calls application layer already
    - `article_search` - calls application layer already

    **Verify line count:**
    - Target: under 200 lines
    - If over, identify remaining business logic in CLI and move to application layer
  </action>
  <verify>
    <automated>wc -l src/cli/article.py | awk '{if($1 < 200) print "OK: " $1 " lines"; else print "FAIL: " $1 " lines (need < 200)"}'</automated>
  </verify>
  <done>src/cli/article.py is under 200 lines and all commands still function</done>
</task>

</tasks>

<verification>
- `src/application/tags.py` has 3 exported functions
- `src/application/related.py` has 1 exported function
- `src/cli/article.py` is under 200 lines
- All imports resolve without errors
</verification>

<success_criteria>
- `wc -l src/cli/article.py` shows less than 200 lines
- `python -c "from src.cli.article import article, article_list, article_view, article_open, article_tag, article_search, article_related; print('All OK')"` passes
- Manual verification: `python -m src.cli article --help` works
</success_criteria>

<output>
After completion, create `.planning/quick/260327-ghv-src-cli-article-py-200-cli-application/260327-ghv-SUMMARY.md`
</output>
