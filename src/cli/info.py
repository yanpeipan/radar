"""Info command - diagnostics and introspection for feedship."""

from __future__ import annotations

import os
from pathlib import Path

import click

from src.application.config import _get_settings
from src.cli import cli  # noqa: E402, F401
from src.cli.ui import print_json
from src.storage.sqlite.impl import get_db, get_db_path


def _format_bytes(size: int) -> str:
    """Format bytes as human-readable string."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"


def _get_storage_stats() -> dict:
    """Get storage statistics from the database."""
    stats = {"articles": 0, "feeds": 0, "db_size_bytes": 0}
    try:
        db_path = get_db_path()
        if os.path.exists(db_path):
            stats["db_size_bytes"] = os.path.getsize(db_path)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM articles")
            stats["articles"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM feeds")
            stats["feeds"] = cursor.fetchone()[0]
    except Exception:
        pass
    return stats


def _get_config_info() -> dict:
    """Get configuration information."""
    config_dir = Path(Path(__file__).resolve().parents[2]) / "config"
    config_path = config_dir / "config.yaml"

    # Use platformdirs like config.py does
    import platformdirs

    config_path = (
        Path(platformdirs.user_config_dir("feedship", appauthor=False)) / "config.yaml"
    )

    settings = _get_settings()
    return {
        "config_path": str(config_path),
        "config": settings.model_dump(),
    }


@cli.command("info")
@click.option("--version", is_flag=True, help="Show version only")
@click.option("--config", is_flag=True, help="Show config path and values")
@click.option("--storage", is_flag=True, help="Show storage path and stats")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def info(
    ctx: click.Context, version: bool, config: bool, storage: bool, json_output: bool
) -> None:
    """Display feedship diagnostics: version, config, and storage information."""
    # Filter logic: when no filters set, show all; when any filter set, show only those
    show_version = not (config or storage)
    show_config = not (version or storage)
    show_storage = not (version or config)

    if version or config or storage:
        show_version = version
        show_config = config
        show_storage = storage

    result: dict = {}

    if json_output:
        # JSON mode - build structured output
        if show_version:
            result["version"] = FEEDSHIP_VERSION
        if show_config:
            config_info = _get_config_info()
            result["config_path"] = config_info["config_path"]
            result["config"] = config_info["config"]
        if show_storage:
            result["storage_path"] = get_db_path()
            result["storage"] = _get_storage_stats()
        print_json(result)
    else:
        # Text mode
        if show_version:
            click.echo(f"feedship v{FEEDSHIP_VERSION}")
        if show_config:
            config_info = _get_config_info()
            click.echo(f"Config: {config_info['config_path']}")
            config_data = config_info["config"]
            # Pretty-print config values
            click.echo("Config values:")
            for key, value in config_data.items():
                if isinstance(value, dict):
                    click.echo(f"  {key}:")
                    for sub_key, sub_value in value.items():
                        click.echo(f"    {sub_key}: {sub_value}")
                else:
                    click.echo(f"  {key}: {value}")
        if show_storage:
            db_path = get_db_path()
            click.echo(f"Storage: {db_path}")
            stats = _get_storage_stats()
            click.echo(f"Articles: {stats['articles']}")
            click.echo(f"Feeds: {stats['feeds']}")
            if stats["db_size_bytes"] > 0:
                click.echo(f"DB Size: {_format_bytes(stats['db_size_bytes'])}")
            else:
                click.echo("DB Size: N/A")


from src.cli import FEEDSHIP_VERSION  # noqa: E402, F401
