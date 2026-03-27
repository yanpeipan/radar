"""CLI package - defines cli() command group and registers subcommands."""

from __future__ import annotations

import logging
import warnings

import click

# Suppress requests version mismatch warning (urllib3 2.6.3 is functionally compatible)
warnings.filterwarnings("ignore", message="urllib3.*doesn't match a supported version")


@click.group()
@click.version_option(version="0.1.0")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """RSS reader CLI - manage feeds and read articles."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    # Initialize uvloop (graceful fallback on Windows)
    from src.utils.asyncio_utils import install_uvloop
    install_uvloop()

    # Initialize database on every command
    from src.storage.sqlite import init_db
    init_db()

# Import submodules to trigger @cli.command decorators
from src.cli import feed  # noqa: F401
from src.cli import article  # noqa: F401
from src.cli import discover  # noqa: F401


if __name__ == "__main__":
    cli()
