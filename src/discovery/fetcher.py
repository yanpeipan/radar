"""Feed URL validation via HTTP HEAD request (DISC-04)."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from scrapling import Fetcher
from trafilatura.feeds import FEED_TYPES

logger = logging.getLogger(__name__)

_FEED_TYPE_KEYWORDS = ('atom', 'rdf', 'rss', 'json')


async def validate_feed(url: str) -> tuple[bool, str | None]:
    """Validate a feed URL via HEAD request.

    Args:
        url: The feed URL to validate.

    Returns:
        Tuple of (is_valid, feed_type). is_valid is True if HTTP 200
        and Content-Type indicates a feed. feed_type is 'rss', 'atom', 'rdf'.
    """
    try:
        response = await asyncio.to_thread(Fetcher.get, url)

        if response.status != 200:
            return False, None

        content_type = response.headers.get('content-type', '').lower()

        # Check if Content-Type matches any known feed MIME type from trafilatura
        if any(ft in content_type for ft in FEED_TYPES):
            # Determine feed_type from MIME type keywords
            for keyword in _FEED_TYPE_KEYWORDS:
                if keyword in content_type:
                    return True, keyword if keyword != 'rdf' else 'rdf'
        # For generic xml types, detect from URL path
        if 'xml' in content_type:
            lower_url = url.lower()
            if '/rss' in lower_url or '.rss' in lower_url or '/feed' in lower_url:
                return True, 'rss'
            if '/atom' in lower_url:
                return True, 'atom'
            if '/rdf' in lower_url:
                return True, 'rdf'

        return False, None

    except Exception:
        return False, None


