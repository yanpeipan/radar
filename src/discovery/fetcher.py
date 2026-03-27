"""Feed URL validation via HTTP HEAD request (DISC-04)."""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from src.discovery.common_paths import FEED_CONTENT_TYPES

logger = logging.getLogger(__name__)

FEED_TYPE_MAP = {
    'rss': 'application/rss+xml',
    'atom': 'application/atom+xml',
    'rdf': 'application/rdf+xml',
}


async def validate_feed(url: str) -> tuple[bool, str | None]:
    """Validate a feed URL via HEAD request.

    Args:
        url: The feed URL to validate.

    Returns:
        Tuple of (is_valid, feed_type). is_valid is True if HTTP 200
        and Content-Type indicates a feed. feed_type is 'rss', 'atom', 'rdf'.
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            response = await client.head(url)

            if response.status_code != 200:
                return False, None

            content_type = response.headers.get('content-type', '').lower()

            # Check if Content-Type matches any feed type
            for feed_type, mime_type in FEED_TYPE_MAP.items():
                if mime_type in content_type or feed_type in content_type:
                    return True, feed_type

            # Also check against FEED_CONTENT_TYPES
            for ft in FEED_CONTENT_TYPES:
                if ft in content_type:
                    # Determine feed_type from content type or URL extension
                    if 'rss' in content_type:
                        return True, 'rss'
                    if 'atom' in content_type:
                        return True, 'atom'
                    if 'rdf' in content_type:
                        return True, 'rdf'
                    # For text/xml or application/xml, detect from URL path
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


