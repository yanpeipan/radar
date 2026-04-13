"""OPML import/export use cases for feed subscription portability."""

from __future__ import annotations

import datetime
import html
from xml.sax.saxutils import escape as xml_escape

from src.models import Feed


def _xml_attr(value: str | None) -> str:
    """Escape and return an XML attribute value, or empty string if None."""
    if value is None:
        return ""
    # html.escape handles & < > " for attribute context
    return html.escape(value, quote=True)


def _xml_text(value: str | None) -> str:
    """Escape text content for XML."""
    if value is None:
        return ""
    return xml_escape(value)


def export_feeds_to_opml(feeds: list[Feed]) -> str:
    """Serialize feeds to OPML 2.0 XML.

    Args:
        feeds: List of Feed objects to export.

    Returns:
        OPML 2.0 XML string with all feeds as outline elements.
    """
    # Build a dict of group -> list[feeds] for grouped output
    groups: dict[str, list[Feed]] = {}
    ungrouped: list[Feed] = []
    for feed in feeds:
        if feed.group:
            groups.setdefault(feed.group, []).append(feed)
        else:
            ungrouped.append(feed)

    now = datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")

    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<opml version="2.0">',
        "  <head>",
        f"    <title>{_xml_text('Feedship Feed Export')}</title>",
        f"    <dateCreated>{_xml_text(now)}</dateCreated>",
        "  </head>",
        "  <body>",
    ]

    def _feed_outlines(feed_list: list[Feed], indent: str = "    ") -> None:
        for feed in feed_list:
            category = _xml_attr(feed.group)
            category_attr = f' category="{category}"' if category else ""
            lines.append(
                f'{indent}<outline text="{_xml_attr(feed.name)}" '
                f'title="{_xml_attr(feed.name)}" type="rss" '
                f'xmlUrl="{_xml_attr(feed.url)}"{category_attr}/>'
            )

    # Grouped outlines
    for group_name in sorted(groups.keys()):
        group_feeds = groups[group_name]
        lines.append(
            f'    <outline text="{_xml_attr(group_name)}" '
            f'title="{_xml_attr(group_name)}">'
        )
        _feed_outlines(group_feeds, indent="      ")
        lines.append("    </outline>")

    # Ungrouped outlines
    _feed_outlines(ungrouped)

    lines.append("  </body>")
    lines.append("</opml>")

    return "\n".join(lines) + "\n"
