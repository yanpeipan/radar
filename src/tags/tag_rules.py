"""Tag rules for automatic article tagging.

Manages keyword and regex rules in ~/.radar/tag-rules.yaml.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yaml

RULES_PATH = Path.home() / ".radar" / "tag-rules.yaml"


class TagRule:
    """Represents a tag rule with keywords and/or regex patterns."""

    def __init__(self, name: str, keywords: Optional[list[str]] = None, regex: Optional[list[str]] = None):
        self.name = name
        self.keywords = keywords or []
        self.regex = regex or []

    def matches(self, text: str) -> bool:
        """Check if text matches any keyword or regex in this rule."""
        text_lower = text.lower()
        # Check keywords (case-insensitive substring match)
        for kw in self.keywords:
            if kw.lower() in text_lower:
                return True
        # Check regex patterns
        for pattern in self.regex:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False


def load_rules() -> dict:
    """Load rules from YAML file. Returns dict with 'tags' key."""
    if not RULES_PATH.exists():
        return {"tags": {}}
    with open(RULES_PATH) as f:
        return yaml.safe_load(f) or {"tags": {}}


def save_rules(rules: dict) -> None:
    """Save rules to YAML file. Creates directory if needed."""
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RULES_PATH, "w") as f:
        yaml.safe_dump(rules, f)


def add_rule(tag_name: str, keywords: Optional[list[str]] = None, regex: Optional[list[str]] = None) -> None:
    """Add or update a rule for a tag (D-07)."""
    rules = load_rules()
    if tag_name not in rules.get("tags", {}):
        rules.setdefault("tags", {})[tag_name] = {"keywords": [], "regex": []}
    tag_rule = rules["tags"][tag_name]
    if keywords:
        tag_rule.setdefault("keywords", []).extend(keywords)
    if regex:
        tag_rule.setdefault("regex", []).extend(regex)
    save_rules(rules)


def remove_rule(tag_name: str, keyword: Optional[str] = None, regex_pattern: Optional[str] = None) -> bool:
    """Remove a specific keyword or regex from a tag rule. Returns True if removed."""
    rules = load_rules()
    if tag_name not in rules.get("tags", {}):
        return False
    tag_rule = rules["tags"][tag_name]
    if keyword:
        if keyword in tag_rule.get("keywords", []):
            tag_rule["keywords"].remove(keyword)
    if regex_pattern:
        if regex_pattern in tag_rule.get("regex", []):
            tag_rule["regex"].remove(regex_pattern)
    # Remove tag if no rules left
    if not tag_rule.get("keywords") and not tag_rule.get("regex"):
        del rules["tags"][tag_name]
    save_rules(rules)
    return True


def edit_rule(
    tag_name: str,
    add_keywords: Optional[list[str]] = None,
    remove_keywords: Optional[list[str]] = None,
    add_regex: Optional[list[str]] = None,
    remove_regex: Optional[list[str]] = None
) -> bool:
    """Edit an existing tag rule by adding/removing keywords or regex patterns.

    Args:
        tag_name: Name of the tag rule to edit.
        add_keywords: Keywords to add to the rule.
        remove_keywords: Keywords to remove from the rule.
        add_regex: Regex patterns to add to the rule.
        remove_regex: Regex patterns to remove from the rule.

    Returns:
        True if the rule was edited, False if tag rule not found.
    """
    rules = load_rules()
    if tag_name not in rules.get("tags", {}):
        return False

    tag_rule = rules["tags"][tag_name]

    # Remove keywords
    if remove_keywords:
        for kw in remove_keywords:
            if kw in tag_rule.get("keywords", []):
                tag_rule["keywords"].remove(kw)

    # Remove regex patterns
    if remove_regex:
        for pattern in remove_regex:
            if pattern in tag_rule.get("regex", []):
                tag_rule["regex"].remove(pattern)

    # Add keywords
    if add_keywords:
        tag_rule.setdefault("keywords", []).extend(add_keywords)

    # Add regex patterns
    if add_regex:
        tag_rule.setdefault("regex", []).extend(add_regex)

    # Clean up empty rules
    if not tag_rule.get("keywords") and not tag_rule.get("regex"):
        del rules["tags"][tag_name]

    save_rules(rules)
    return True


def list_rules() -> dict:
    """Return all rules as dict."""
    return load_rules()


def match_article_to_tags(article_title: str, article_desc: str) -> list[str]:
    """Apply all matching rules to an article. Returns list of matching tag names (D-09: apply ALL matching)."""
    rules = load_rules()
    text = f"{article_title or ''} {article_desc or ''}"
    matched_tags = []

    for tag_name, rule in rules.get("tags", {}).items():
        tag_rule = TagRule(
            name=tag_name,
            keywords=rule.get("keywords", []),
            regex=rule.get("regex", [])
        )
        if tag_rule.matches(text):
            matched_tags.append(tag_name)

    return matched_tags


def apply_rules_to_article(article_id: str, article_title: str, article_desc: str) -> list[str]:
    """Match rules and tag an article. Returns list of applied tags."""
    matched = match_article_to_tags(article_title, article_desc)
    # Import at runtime to avoid circular import
    from src.storage.sqlite import tag_article
    for tag_name in matched:
        tag_article(article_id, tag_name)
    return matched
