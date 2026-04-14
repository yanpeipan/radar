"""OPML import/export use cases for feed subscription portability."""

from __future__ import annotations

import datetime
import html
from dataclasses import dataclass
from xml.etree import ElementTree
from xml.sax.saxutils import escape as xml_escape

from src.models import Feed


@dataclass(frozen=True)
class FeedEntry:
    """Represents a single feed parsed from an OPML outline element.

    Attributes:
        name: Display name of the feed (outline text attribute).
        url: Feed URL (xmlUrl attribute).
        title: Optional title attribute of the outline.
        group: Group/category this feed belongs to (from parent outline text or category attr).
    """

    name: str
    url: str
    title: str | None = None
    group: str | None = None


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


def parse_opml_file(file_path: str) -> list[FeedEntry]:
    """Parse an OPML file and return feed entries with group information.

    Recursively traverses outline elements in the OPML body. Feeds are identified
    by the presence of an xmlUrl attribute. Parent outline elements that have no
    xmlUrl themselves define groups; their text attribute becomes the group name.
    The category attribute on individual feed outlines is also respected as a group.

    Args:
        file_path: Path to the OPML file to parse.

    Returns:
        List of FeedEntry objects for each feed found in the OPML.

    Raises:
        FileNotFoundError: If the OPML file does not exist.
        ValueError: If the file is not valid XML or not a valid OPML document.
    """
    try:
        tree = ElementTree.parse(file_path)
    except ElementTree.ParseError as e:
        raise ValueError(f"Invalid XML in OPML file: {e}") from e

    root = tree.getroot()
    if root.tag.lower() != "opml":
        raise ValueError("Not a valid OPML file: missing <opml> root element")

    # Find the <body> element
    body = root.find("body")
    if body is None:
        return []

    entries: list[FeedEntry] = []

    def _parse_outlines(
        outlines: list[ElementTree.Element], current_group: str | None
    ) -> None:
        for outline in outlines:
            xml_url = outline.get("xmlUrl")
            text = outline.get("text", "")
            title = outline.get("title")
            category = outline.get("category")

            if xml_url:
                # This outline is a feed entry
                # Group comes from category attr, else parent group
                group = category if category else current_group
                entries.append(
                    FeedEntry(
                        name=text,
                        url=xml_url,
                        title=title,
                        group=group,
                    )
                )

            # Recurse into children (for nested group outlines)
            children = list(outline)
            if children:
                # Determine the group for children:
                # If this outline has no xmlUrl, it's a group outline itself
                child_group = text if not xml_url else current_group
                _parse_outlines(children, child_group)

    _parse_outlines(list(body), current_group=None)
    return entries
