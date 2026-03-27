---
phase: quick-260328-xxx
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/cli/article.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "print_articles uses Rich Table for output"
    - "Table has columns: ID, Title, Source, Date, Score"
    - "Verbose mode shows rich panel with full article details"
artifacts:
  - path: "src/cli/article.py"
    provides: "print_articles using Rich Table"
    contains: "Table("
---

<objective>
Refactor print_articles to use Rich Table with adaptive column sizing instead of click.secho formatted text output.
</objective>

<context>
@src/cli/article.py (current print_articles implementation)
</context>

<tasks>

<task type="auto">
  <name>Refactor print_articles to use Rich Table</name>
  <files>src/cli/article.py</files>
  <action>
Replace the current print_articles implementation with Rich Table:

```python
def print_articles(items: list[ArticleListItem], verbose: bool = False) -> None:
    """Print formatted articles to console using Rich Table.

    Args:
        items: List of ArticleListItem objects.
        verbose: If True, show detailed output with rich panel for each article
    """
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    console = Console()

    if not items:
        click.secho("No articles found.")
        return

    if verbose:
        for item in items:
            fields = []
            if item.title:
                fields.append(f"[bold]Title:[/bold] {item.title}")
            if item.id:
                fields.append(f"[bold]ID:[/bold] {item.id}")
            if item.feed_name:
                fields.append(f"[bold]Source:[/bold] {item.feed_name}")
            if item.pub_date:
                fields.append(f"[bold]Date:[/bold] {item.pub_date}")
            if item.score:
                fields.append(f"[bold]Score:[/bold] {item.score}")
            if item.link:
                fields.append(f"[bold]Link:[/bold] {item.link}")
            if item.description:
                preview = item.description[:200] + "..." if len(item.description) > 200 else item.description
                fields.append(f"[bold]Description:[/bold] {preview}")

            if fields:
                console.print(Panel("\n".join(fields), title=item.title or "Article"))
            else:
                console.print(Panel("[dim]No details available[/dim]", title=item.title or "Article"))
        return

    # Normal table view
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=8, no_wrap=True)
    table.add_column("Title", style="cyan", min_width=40)
    table.add_column("Source", style="green", width=15, no_wrap=True)
    table.add_column("Date", style="yellow", width=12, no_wrap=True)
    table.add_column("Score", justify="right", width=6, no_wrap=True)

    for item in items:
        table.add_row(
            (item.id[:8] if item.id else "-"),
            (item.title[:60] if item.title else "-"),
            (item.feed_name[:15] if item.feed_name else "-"),
            (item.pub_date[:10] if item.pub_date else "-"),
            (str(item.score)[:4] if item.score else "-"),
        )

    console.print(table)
```

Key changes:
1. Use Rich Table with proper column definitions and styles
2. Console.print for rich output
3. Verbose mode uses Panel for detailed per-article display
4. Remove click.secho for table output (use console.print instead)
  </action>
  <verify>
    <automated>grep -n "Table(" src/cli/article.py</automated>
  </verify>
  <done>
    print_articles uses Rich Table for normal mode and Panel for verbose mode
  </done>
</task>

</tasks>

<verification>
- `python -c "from src.cli.article import print_articles, ArticleListItem; print_articles([ArticleListItem(id='test12345678', feed_id='f1', feed_name='Test Feed', title='Test Article Title Here', link='https://example.com', guid='test123', pub_date='2026-03-28', description='A test description', score=0.85)])"` shows Rich Table
- `python -c "from src.cli.article import print_articles, ArticleListItem; print_articles([ArticleListItem(id='test12345678', feed_id='f1', feed_name='Test Feed', title='Test Article', link='https://example.com', guid='test123', pub_date='2026-03-28', description='A test description', score=0.85)], verbose=True)"` shows Panel
</verification>

<success_criteria>
- print_articles uses Rich Table for non-verbose output
- Table has proper column styling (ID=dim, Title=cyan, Source=green, Date=yellow, Score=right)
- Verbose mode uses Panel for each article
- Empty list shows "No articles found." message
</success_criteria>

<output>
After completion, create `.planning/quick/260328-xxx-refactor-print-articles-rich-table/260328-xxx-SUMMARY.md`
</output>
