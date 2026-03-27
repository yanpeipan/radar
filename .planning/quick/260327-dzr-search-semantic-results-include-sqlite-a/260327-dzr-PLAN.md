---
quick_id: 260327-dzr
type: quick
slug: search-semantic-results-include-sqlite-a
must_haves:
  truths:
    - "search --semantic shows article ID in results"
    - "article related works with ID from search --semantic"
  artifacts:
    - path: "src/storage/vector.py"
      contains:
        - "sqlite_id"
        - "get_article_id_by_url"
    - path: "src/storage/sqlite.py"
      contains:
        - "get_article_id_by_url"
    - path: "src/cli/article.py"
      contains:
        - "result.get(\"sqlite_id\")"
---

<objective>
Add SQLite article nanoid to semantic search results so users can copy IDs to use with `article related` and other commands.
</objective>

<context>
@src/storage/vector.py
@src/storage/sqlite.py
@src/cli/article.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add get_article_id_by_url to sqlite.py</name>
  <read_first>
    src/storage/sqlite.py
  </read_first>
  <action>
    Add a new function to src/storage/sqlite.py:

    ```python
    def get_article_id_by_url(url: str) -> Optional[str]:
        """Get article nanoid by URL (guid).

        Args:
            url: The article URL (stored as guid in SQLite)

        Returns:
            The SQLite article nanoid (id), or None if not found.
        """
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM articles WHERE guid = ?", (url,))
            row = cursor.fetchone()
            return row["id"] if row else None
    ```

    Also add the export in src/storage/__init__.py.
  </action>
  <verify>
    grep -r "get_article_id_by_url" src/storage/sqlite.py
    grep -r "get_article_id_by_url" src/storage/__init__.py
  </verify>
  <done>
    get_article_id_by_url() exists and is exported.
  </done>
</task>

<task type="auto">
  <name>Task 2: Include sqlite_id in search_articles_semantic results</name>
  <read_first>
    src/storage/vector.py
  </read_first>
  <action>
    Modify `search_articles_semantic()` in src/storage/vector.py to look up and include the SQLite nanoid:

    In the for loop (around line 179), after getting the article_id (ChromaDB URL), look up the SQLite nanoid:

    ```python
    for i, article_id in enumerate(ids):
        # Look up SQLite article nanoid from URL (guid)
        from src.storage.sqlite import get_article_id_by_url
        sqlite_id = get_article_id_by_url(article_id) if article_id else None

        articles.append({
            "article_id": article_id,
            "sqlite_id": sqlite_id,
            "title": metadatas[i].get("title") if metadatas[i] else None,
            "url": metadatas[i].get("url") if metadatas[i] else None,
            "distance": distances[i] if i < len(distances) else None,
            "document": documents[i] if i < len(documents) else None,
        })
    ```

    Also update the docstring to mention sqlite_id in the return value.
  </action>
  <verify>
    grep -r "sqlite_id" src/storage/vector.py
  </verify>
  <done>
    search_articles_semantic() returns dicts with sqlite_id key.
  </done>
</task>

<task type="auto">
  <name>Task 3: Display article ID in search --semantic CLI output</name>
  <read_first>
    src/cli/article.py
  </read_first>
  <action>
    Modify `article_search()` in src/cli/article.py to show article ID in semantic search results.

    In the verbose block (line 324-331), add after displaying title:
    ```python
    sqlite_id = result.get("sqlite_id")
    if sqlite_id:
        id_display = sqlite_id[:8]  # truncate to 8 chars for display
        click.secho(f"ID: {id_display}")
    ```

    In the non-verbose block (line 333), add the ID to the display:
    ```python
    # Current:
    click.secho(f"{title[:50]} | Similarity: {similarity}")
    # Change to include short ID:
    sqlite_id = result.get("sqlite_id")
    if sqlite_id:
        id_display = sqlite_id[:8]
        click.secho(f"{id_display} | {title[:40]} | Similarity: {similarity}")
    else:
        click.secho(f"{title[:50]} | Similarity: {similarity}")
    ```
  </action>
  <verify>
    grep -r "sqlite_id" src/cli/article.py
    grep -r "result.get..sqlite_id" src/cli/article.py
  </verify>
  <done>
    search --semantic shows article ID (8-char truncated) in both normal and verbose output.
  </done>
</task>

</tasks>

<verification>
1. Run `python -m src.cli search --semantic "machine learning"` - should show IDs in results
2. Verify IDs start appearing in search results
3. Use an ID from search results with `article related <id>` - should work
</verification>

<success_criteria>
1. `grep -r "sqlite_id" src/storage/vector.py` finds the new field
2. `grep -r "get_article_id_by_url" src/storage/sqlite.py` finds the helper function
3. `grep -r "result.get..sqlite_id" src/cli/article.py` finds the CLI display code
4. Semantic search results show article ID (8-char truncated)
</success_criteria>

<output>
After completion, create `.planning/quick/260327-dzr-search-semantic-results-include-sqlite-a/260327-dzr-SUMMARY.md`
</output>
