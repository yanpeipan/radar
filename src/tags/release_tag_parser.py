"""Release tag parser for extracting release-specific tags from GitHub releases.

Extracts:
- owner tag from URL via parse_github_url()
- release tag (always added for release articles)
- version tags: v1, v1.2, v1.2.3 from tag_name
- release type tag: major-release, minor-release, or bugfix-release
"""
from __future__ import annotations

import re
from typing import List

from src.providers.base import Article, TagParser


class ReleaseTagParser:
    """Tag parser for GitHub release articles.

    Extracts release-specific tags including version numbers and release type.
    """

    # Regex to match version numbers with optional 'v' prefix
    VERSION_PATTERN = re.compile(r'v?(\d+)\.(\d+)\.(\d+)')

    def parse_tags(self, article: Article) -> List[str]:
        """Parse tags for a GitHub release article.

        Args:
            article: Article dict with title (tag_name), link (html_url),
                     description (body), etc.

        Returns:
            List of tag strings: owner, release, version tags, release type.
        """
        tags: List[str] = []
        seen: set = set()

        # Always add "release" tag for release articles
        self._add_tag(tags, seen, "release")

        # Extract owner tag from URL
        link = article.get("link", "")
        if link:
            try:
                from src.github_utils import parse_github_url
                owner, _ = parse_github_url(link)
                self._add_tag(tags, seen, owner)
            except (ValueError, Exception):
                pass

        # Extract version tags from title (tag_name)
        title = article.get("title", "")
        if title:
            version_match = self.VERSION_PATTERN.search(title)
            if version_match:
                major, minor, patch = version_match.groups()

                # Add version tags: v1, v1.2, v1.2.3
                self._add_tag(tags, seen, f"v{major}")
                self._add_tag(tags, seen, f"v{major}.{minor}")
                self._add_tag(tags, seen, f"v{major}.{minor}.{patch}")

                # Determine release type (semantic versioning)
                # v1.0.0 -> major-release, v1.2.0 -> minor-release, v1.2.3 -> bugfix-release
                if patch == "0" and minor == "0":
                    self._add_tag(tags, seen, "major-release")
                elif patch == "0":
                    self._add_tag(tags, seen, "minor-release")
                else:
                    self._add_tag(tags, seen, "bugfix-release")

        return tags

    def _add_tag(self, tags: List[str], seen: set, tag: str) -> None:
        """Add tag if not already seen (case-sensitive).

        Args:
            tags: List to append to.
            seen: Set of already-seen tags.
            tag: Tag to add.
        """
        if tag not in seen:
            seen.add(tag)
            tags.append(tag)


# Singleton instance for dynamic loading
TAG_PARSER_INSTANCE = ReleaseTagParser()
