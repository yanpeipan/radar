"""Async utilities for uvloop integration.

Provides install_uvloop() for event loop setup following uvloop best practices.
"""
from __future__ import annotations

import logging
import platform

logger = logging.getLogger(__name__)


def install_uvloop() -> bool:
    """Install uvloop as the event loop policy on supported platforms.

    Call this at application startup before using any async features.
    Linux and macOS get uvloop (2-4x faster I/O). Windows falls back to asyncio.

    This follows uvloop's recommended pattern: uvloop.install() is called once
    at startup. uvloop.run() creates its own event loop, so we don't create
    or store one here.

    Returns:
        True if uvloop was installed, False if skipped or failed.
    """
    # uvloop only works on Linux and macOS
    if platform.system() == "Windows":
        logger.debug("uvloop skipped on Windows - using asyncio")
        return False

    try:
        import uvloop  # noqa: F401
    except ImportError:
        logger.warning("uvloop not installed - using asyncio")
        return False

    try:
        uvloop.install()
        logger.info("uvloop installed successfully")
        return True
    except Exception as e:
        # Handle non-main thread or other uvloop failures gracefully
        logger.warning("Failed to install uvloop: %s - using asyncio", e)
        return False
