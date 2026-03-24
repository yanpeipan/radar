"""GitHub utilities."""
from __future__ import annotations

import os

from github import Github

# Module-level PyGithub client
_github_client: Github | None = None


def _get_github_client() -> Github:
    """Get or create module-level Github client."""
    global _github_client
    if _github_client is None:
        _github_client = Github(os.environ.get("GITHUB_TOKEN"))
    return _github_client
