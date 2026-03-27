"""Tagging business logic for article auto-tagging, rule-based tagging, and manual tagging."""

from __future__ import annotations

from src.tags.ai_tagging import run_auto_tagging
from src.tags.tag_rules import apply_rules_to_article
from src.storage import get_untagged_articles, tag_article as storage_tag_article


def auto_tag_articles(eps: float = 0.3, min_samples: int = 3) -> dict[str, list[str]]:
    """Run AI clustering to auto-tag articles based on semantic similarity.

    Args:
        eps: DBSCAN eps parameter for clustering (default 0.3).
        min_samples: DBSCAN min_samples parameter (default 3).

    Returns:
        Dict of {tag_name: [article_ids]} for discovered clusters.
    """
    return run_auto_tagging(eps=eps, min_samples=min_samples)


def apply_rules_to_untagged(verbose: bool = False) -> int:
    """Apply keyword/regex tagging rules to all untagged articles.

    Args:
        verbose: If True, print each article's tagging results.

    Returns:
        Count of articles that were matched and tagged.
    """
    untagged = get_untagged_articles()
    if not untagged:
        return 0

    applied_count = 0
    for row in untagged:
        matched = apply_rules_to_article(row["id"], row["title"], row["description"])
        if matched:
            applied_count += 1
    return applied_count


def tag_article_manual(article_id: str, tag_name: str) -> bool:
    """Tag an article manually with a specific tag.

    Args:
        article_id: The article ID to tag.
        tag_name: The tag name to apply.

    Returns:
        True if tagging succeeded, False otherwise.
    """
    return storage_tag_article(article_id, tag_name)
