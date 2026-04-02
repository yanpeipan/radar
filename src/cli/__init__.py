"""CLI package - defines cli() command group and registers subcommands."""

from __future__ import annotations

import warnings

import click

# Suppress requests version mismatch warning (urllib3 2.6.3 is functionally compatible)
warnings.filterwarnings("ignore", message="urllib3.*doesn't match a supported version")

# Dynamically read version from pyproject.toml via importlib.metadata
try:
    from importlib.metadata import version as get_version
except ImportError:
    from importlib_metadata import version as get_version  # Python < 3.8

FEEDSHIP_VERSION = get_version("feedship")


@click.group()
@click.version_option(version=FEEDSHIP_VERSION)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, debug: bool) -> None:
    """Feedship CLI - manage information feeds and articles."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["debug"] = debug

    # Configure logging
    import logging

    if debug:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s: %(message)s")
    elif verbose:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

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
