"""Default tag parser that wraps tag_rules.match_article_to_tags().

Provides automatic article tagging based on keyword and regex rules
configured in ~/.radar/tag-rules.yaml.
"""
from __future__ import annotations

from typing import List

from src.providers.base import Article, TagParser
from src.tags.tag_rules import match_article_to_tags


class DefaultTagParser:
    """Tag parser that wraps tag_rules.match_article_to_tags()."""

    def parse_tags(self, article: Article) -> List[str]:
        """Parse tags for an article using tag rules.

        Args:
            article: Article dict with title and description fields.

        Returns:
            List of tag name strings from matching rules.
        """
        title = article.get("title", "")
        description = article.get("description", "") or ""
        return match_article_to_tags(title, description)


# Singleton instance for dynamic loading
TAG_PARSER_INSTANCE = DefaultTagParser()
