"""Tag management commands for RSS reader CLI."""

import sys
import logging
from typing import Optional

import click

from src.storage.sqlite import add_tag, list_tags, remove_tag, get_tag_article_counts

logger = logging.getLogger(__name__)


# Import cli from parent package
from src.cli import cli


@cli.group()
@click.pass_context
def tag(ctx: click.Context) -> None:
    """Manage article tags."""
    pass


@tag.command("add")
@click.argument("name")
@click.pass_context
def tag_add(ctx: click.Context, name: str) -> None:
    """Create a new tag."""
    try:
        t = add_tag(name)
        click.secho(f"Created tag: {t.name}", fg="green")
    except Exception as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)


@tag.command("list")
@click.pass_context
def tag_list(ctx: click.Context) -> None:
    """List all tags with article counts."""
    try:
        tags = list_tags()
        counts = get_tag_article_counts()
        if not tags:
            click.secho("No tags created yet. Use 'tag add <name>' to create one.")
            return
        click.secho("Tag | Articles")
        click.secho("-" * 30)
        for t in tags:
            count = counts.get(t.name, 0)
            click.secho(f"{t.name} | {count}")
    except Exception as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)


@tag.command("remove")
@click.argument("tag_name")
@click.pass_context
def tag_remove(ctx: click.Context, tag_name: str) -> None:
    """Remove a tag (unlinks from all articles)."""
    try:
        removed = remove_tag(tag_name)
        if removed:
            click.secho(f"Removed tag: {tag_name}", fg="green")
        else:
            click.secho(f"Tag not found: {tag_name}", fg="yellow")
            sys.exit(1)
    except Exception as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)


@tag.group()
@click.pass_context
def rule(ctx: click.Context) -> None:
    """Manage tag rules for automatic tagging."""
    pass


@rule.command("add")
@click.argument("tag_name")
@click.option("--keyword", "-k", multiple=True, help="Keyword to match (can specify multiple)")
@click.option("--regex", "-r", help="Regex pattern to match")
@click.pass_context
def tag_rule_add(ctx: click.Context, tag_name: str, keyword: tuple, regex: Optional[str]) -> None:
    """Add a rule for a tag.

    Examples:
        tag rule add AI --keyword "machine learning" --keyword "deep learning"
        tag rule add Security --regex "CVE-\\d+"
    """
    if not keyword and not regex:
        click.secho("Error: Must specify --keyword or --regex", fg="red")
        sys.exit(1)
    try:
        from src.tags.tag_rules import add_rule
        add_rule(tag_name, keywords=list(keyword) if keyword else None, regex=[regex] if regex else None)
        click.secho(f"Added rule(s) for tag '{tag_name}'", fg="green")
    except Exception as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)


@rule.command("remove")
@click.argument("tag_name")
@click.option("--keyword", "-k", help="Keyword to remove")
@click.option("--regex", "-r", help="Regex pattern to remove")
@click.pass_context
def tag_rule_remove(ctx: click.Context, tag_name: str, keyword: Optional[str], regex: Optional[str]) -> None:
    """Remove a rule from a tag."""
    if not keyword and not regex:
        click.secho("Error: Must specify --keyword or --regex", fg="red")
        sys.exit(1)
    try:
        from src.tags.tag_rules import remove_rule
        removed = remove_rule(tag_name, keyword=keyword, regex_pattern=regex)
        if removed:
            click.secho(f"Removed rule from '{tag_name}'", fg="green")
        else:
            click.secho(f"Rule not found for '{tag_name}'", fg="yellow")
    except Exception as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)


@rule.command("list")
@click.pass_context
def tag_rule_list(ctx: click.Context) -> None:
    """List all tag rules."""
    try:
        from src.tags.tag_rules import list_rules
        rules = list_rules()
        tags = rules.get("tags", {})
        if not tags:
            click.secho("No tag rules defined. Use 'tag rule add' to create one.")
            return
        click.secho("Tag Rules:")
        click.secho("=" * 50)
        for tag_name, rule in tags.items():
            click.secho(f"\n{tag_name}:")
            for kw in rule.get("keywords", []):
                click.secho(f"  [keyword] {kw}")
            for pattern in rule.get("regex", []):
                click.secho(f"  [regex] {pattern}")
    except Exception as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)


@rule.command("edit")
@click.argument("tag_name")
@click.option("--add-keyword", "-k", multiple=True, help="Keyword to add (can specify multiple)")
@click.option("--remove-keyword", "-K", multiple=True, help="Keyword to remove (can specify multiple)")
@click.option("--add-regex", "-r", multiple=True, help="Regex pattern to add (can specify multiple)")
@click.option("--remove-regex", "-R", multiple=True, help="Regex pattern to remove (can specify multiple)")
@click.pass_context
def tag_rule_edit(ctx: click.Context, tag_name: str, add_keyword: tuple, remove_keyword: tuple, add_regex: tuple, remove_regex: tuple) -> None:
    """Edit a tag rule by adding/removing keywords or regex patterns.

    Examples:
        tag rule edit AI --add-keyword "neural network"
        tag rule edit Security --remove-keyword "vulnerability" --add-regex "CVE-\\\\d+"
    """
    if not add_keyword and not remove_keyword and not add_regex and not remove_regex:
        click.secho("Error: Must specify at least one of --add-keyword, --remove-keyword, --add-regex, or --remove-regex", fg="red")
        sys.exit(1)

    try:
        from src.tags.tag_rules import edit_rule
        success = edit_rule(
            tag_name,
            add_keywords=list(add_keyword) if add_keyword else None,
            remove_keywords=list(remove_keyword) if remove_keyword else None,
            add_regex=list(add_regex) if add_regex else None,
            remove_regex=list(remove_regex) if remove_regex else None
        )
        if success:
            click.secho(f"Updated rule for tag '{tag_name}'", fg="green")
        else:
            click.secho(f"Rule not found for tag '{tag_name}'", fg="yellow")
            sys.exit(1)
    except Exception as e:
        click.secho(f"Error: {e}", err=True, fg="red")
        sys.exit(1)
