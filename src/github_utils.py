"""GitHub URL parsing utilities.

Pure URL parsing functions with no external API dependencies.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse


def parse_github_url(url: str) -> tuple[str, str]:
    """Parse owner and repo from GitHub URL.

    Supports:
    - https://github.com/owner/repo
    - https://github.com/owner/repo.git
    - https://github.com/owner/repo/releases
    - git@github.com:owner/repo.git

    Args:
        url: GitHub repository URL.

    Returns:
        Tuple of (owner, repo).

    Raises:
        ValueError: If URL is not a valid GitHub repo URL.
    """
    # SSH format
    if url.startswith("git@"):
        match = re.match(r"git@github\.com:([^/]+)/(.+?)(?:\.git)?$", url)
        if match:
            return match.group(1), match.group(2)

    # HTTPS format
    parsed = urlparse(url)
    if parsed.netloc == "github.com":
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 2:
            return parts[0], parts[1].replace(".git", "")

    raise ValueError(f"Invalid GitHub URL: {url}")
