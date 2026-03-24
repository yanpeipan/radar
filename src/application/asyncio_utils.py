"""Async utilities for uvloop integration and executor management.

Provides install_uvloop() for event loop setup and run_in_executor_crawl()
as the default crawl_async() implementation that wraps sync crawl() in a thread pool.
"""
from __future__ import annotations

import asyncio
import logging
import platform
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from src.providers.base import ContentProvider, Raw

logger = logging.getLogger(__name__)

# Thread pool for default crawl_async() implementation
_default_executor: ThreadPoolExecutor | None = None

# Cached event loop reference
_main_loop: asyncio.AbstractEventLoop | None = None


def _get_default_executor() -> ThreadPoolExecutor:
    """Get or create the default thread pool executor.

    Returns:
        ThreadPoolExecutor with max_workers=10.
    """
    global _default_executor
    if _default_executor is None:
        _default_executor = ThreadPoolExecutor(max_workers=10)
    return _default_executor


def install_uvloop() -> bool:
    """Install uvloop as the event loop policy on supported platforms.

    Call this at application startup before using any async features.
    Linux and macOS get uvloop (2-4x faster I/O). Windows falls back to asyncio.

    Returns:
        True if uvloop was installed, False if skipped or failed.
    """
    global _main_loop

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
        _main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_main_loop)
        logger.info("uvloop installed successfully")
        return True
    except Exception as e:
        # Handle non-main thread or other uvloop failures gracefully
        logger.warning("Failed to install uvloop: %s - using asyncio", e)
        return False


async def run_in_executor_crawl(
    provider: "ContentProvider", url: str
) -> List["Raw"]:
    """Default crawl_async() implementation that wraps sync crawl() in executor.

    Use this as the default crawl_async() implementation for providers that
    implement sync crawl().

    Args:
        provider: ContentProvider instance with a crawl() method.
        url: URL to crawl.

    Returns:
        List of Raw dicts from the provider's crawl() method.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _get_default_executor(),
        provider.crawl,
        url
    )
