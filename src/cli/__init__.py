"""CLI package - defines cli() command group and registers subcommands."""

from __future__ import annotations

import warnings

import click

# Suppress requests version mismatch warning (urllib3 2.6.3 is functionally compatible)
warnings.filterwarnings("ignore", message="urllib3.*doesn't match a supported version")


@click.group()
@click.version_option(version="1.0.2")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Feedship CLI - manage information feeds and articles."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    # Initialize uvloop (graceful fallback on Windows)
    from src.utils.asyncio_utils import install_uvloop

    install_uvloop()

    # Initialize database on every command
    from src.storage.sqlite import init_db

    init_db()


# Import submodules to trigger @cli.command decorators
from src.cli import (
    article,  # noqa: F401, E402
    discover,  # noqa: F401, E402
    feed,  # noqa: F401, E402
)

if __name__ == "__main__":
    cli()
