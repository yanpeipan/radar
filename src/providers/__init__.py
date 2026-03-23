"""Provider registry and dynamic loading for the plugin architecture.

Discovers and loads all *_provider.py modules from src/providers/ directory,
sorted by priority. Provides discover() and discover_or_default() functions
for provider lookup.
"""
from __future__ import annotations

import glob
import importlib
import logging
from pathlib import Path
from typing import List

from src.providers.base import ContentProvider

logger = logging.getLogger(__name__)

# Discovered providers, populated at import time
PROVIDERS: List[ContentProvider] = []


def load_providers() -> None:
    """Load all providers from src/providers/ directory.

    Discovers *_provider.py files, imports each module (which triggers
    self-registration via PROVIDERS.append()), then sorts providers
    by priority descending.

    Excludes __init__.py and base.py from loading.
    """
    providers_dir = Path(__file__).parent

    # Find all provider modules (exclude __init__ and base)
    provider_files = sorted(providers_dir.glob("*_provider.py"))
    logger.debug("Found provider files: %s", [f.stem for f in provider_files])

    for filepath in provider_files:
        module_name = filepath.stem
        if module_name in ("__init__", "base"):
            continue

        full_module = f"src.providers.{module_name}"
        try:
            importlib.import_module(full_module)
            logger.debug("Loaded provider module: %s", full_module)
        except Exception:
            logger.exception("Failed to load provider %s", full_module)

    # Sort by priority descending (higher priority first)
    PROVIDERS.sort(key=lambda p: p.priority(), reverse=True)
    logger.info("Loaded %d providers", len(PROVIDERS))


def discover(url: str) -> List[ContentProvider]:
    """Find providers matching a URL.

    Args:
        url: URL to match against providers.

    Returns:
        List of matching providers sorted by priority (descending).
        Empty list if no providers match.
    """
    matched = [p for p in PROVIDERS if p.match(url)]
    return matched


def discover_or_default(url: str) -> List[ContentProvider]:
    """Find providers matching a URL, or return RSS provider as fallback.

    This implements the fallback mechanism: if no provider matches,
    the RSS provider is returned as fallback since it can handle generic
    feed URLs (RSS/Atom) even if content-type validation failed.

    Args:
        url: URL to match against providers.

    Returns:
        List with matching providers sorted by priority (descending),
        or single RSSProvider if no matches found.
    """
    matched = discover(url)
    if not matched:
        # Fall back to RSSProvider which can attempt to fetch any URL as feed
        for p in PROVIDERS:
            if p.__class__.__name__ == "RSSProvider":
                matched = [p]
                break
    return matched


def get_all_providers() -> List[ContentProvider]:
    """Return all loaded providers sorted by priority.

    Returns:
        All providers in PROVIDERS list (already sorted by priority descending).
    """
    return PROVIDERS


# Load providers at module import time
load_providers()