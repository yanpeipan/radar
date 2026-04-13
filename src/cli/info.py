"""Info command - diagnostics and introspection for feedship."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import click

from src.application.config import _get_settings, get_default_refresh_interval
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


def _get_schedule_info() -> dict:
    """Get schedule information for all feeds showing next scheduled fetch times."""
    feeds_data = []
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, name, url, fetched_at, refresh_interval
                FROM feeds
                ORDER BY name ASC
                """
            )
            rows = cursor.fetchall()
            for row in rows:
                feed_id = row["id"]
                name = row["name"]
                url = row["url"]
                fetched_at = row["fetched_at"]
                refresh_interval = row["refresh_interval"]

                # Determine effective refresh interval
                interval = (
                    refresh_interval
                    if refresh_interval is not None
                    else get_default_refresh_interval()
                )

                # Compute next scheduled fetch
                if fetched_at:
                    try:
                        fetched_dt = datetime.strptime(
                            fetched_at, "%Y-%m-%d %H:%M:%S"
                        ).replace(tzinfo=timezone.utc)
                        next_fetch_ts = fetched_dt.timestamp() + interval
                        next_fetch_dt = datetime.fromtimestamp(
                            next_fetch_ts, tz=timezone.utc
                        )
                        now_ts = time.time()
                        if next_fetch_ts <= now_ts:
                            status = "due now"
                            next_fetch_str = "due now"
                        else:
                            status = "scheduled"
                            next_fetch_str = next_fetch_dt.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        status = "unknown"
                        next_fetch_str = "unknown"
                else:
                    status = "never fetched"
                    next_fetch_str = "never fetched"

                feeds_data.append(
                    {
                        "id": feed_id,
                        "name": name,
                        "url": url,
                        "interval_seconds": interval,
                        "interval_display": _format_interval(interval),
                        "fetched_at": fetched_at,
                        "next_fetch": next_fetch_str,
                        "status": status,
                    }
                )
    except Exception:
        pass
    return {"feeds": feeds_data, "default_interval": get_default_refresh_interval()}


def _format_interval(seconds: int) -> str:
    """Format interval in seconds as human-readable string."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours}h"
    else:
        days = seconds // 86400
        return f"{days}d"


@cli.command("info")
@click.option("--version", is_flag=True, help="Show version only")
@click.option("--config", is_flag=True, help="Show config path and values")
@click.option("--storage", is_flag=True, help="Show storage path and stats")
@click.option(
    "--schedule", is_flag=True, help="Show feed schedule info (next fetch times)"
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def info(
    ctx: click.Context,
    version: bool,
    config: bool,
    storage: bool,
    schedule: bool,
    json_output: bool,
) -> None:
    """Display feedship diagnostics: version, config, storage, and schedule information."""
    # Filter logic: when no filters set, show all; when any filter set, show only those
    show_version = not (config or storage or schedule)
    show_config = not (version or storage or schedule)
    show_storage = not (version or config or schedule)
    show_schedule = not (
        version or config or storage
    )  # show schedule by default when no other filters set

    if version or config or storage or schedule:
        show_version = version
        show_config = config
        show_storage = storage
        show_schedule = schedule

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
        if show_schedule:
            result["schedule"] = _get_schedule_info()
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
        if show_schedule:
            schedule_info = _get_schedule_info()
            feeds = schedule_info["feeds"]
            if not feeds:
                click.echo("No feeds configured.")
            else:
                click.echo(
                    f"Default refresh interval: {_format_interval(schedule_info['default_interval'])}"
                )
                click.echo("")
                click.echo("Feed Schedule:")
                for feed in feeds:
                    interval_str = feed["interval_display"]
                    next_fetch = feed["next_fetch"]
                    click.echo(f"  {feed['name']}")
                    click.echo(f"    URL: {feed['url']}")
                    click.echo(f"    Interval: {interval_str}")
                    click.echo(f"    Next fetch: {next_fetch}")


from src.cli import FEEDSHIP_VERSION  # noqa: E402, F401
