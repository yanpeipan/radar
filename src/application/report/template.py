"""Layer 4: ReportTemplate — Jinja2 template environment encapsulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, Template, select_autoescape

if TYPE_CHECKING:
    from .models import ReportData


@dataclass
class HeadingNode:
    """A node in the markdown heading tree.

    Attributes:
        level: Heading depth — 0 = root, 1 = H1, 2 = H2, 3 = H3, …
        title: Heading text with ``#`` prefix stripped.
        body: Raw content lines between this heading and the next sibling/child.
        children: Child headings nested under this one.
    """

    level: int
    title: str
    body: str = ""
    children: list[HeadingNode] = field(default_factory=list)

    @property
    def titles(self) -> list[str]:
        """Recursively collect all non-empty heading titles in this subtree."""
        result = [self.title] if self.title else []
        for child in self.children:
            result.extend(child.titles)
        return [t for t in result if t]


def parse_markdown_headings(markdown: str) -> HeadingNode:
    """Parse rendered markdown into a heading tree.

    Uses a single-pass stack algorithm — O(n) in the number of lines.

    Returns:
        A synthetic root node (level=0, title="") whose children are the
        top-level headings found in *markdown*.

    Example::

        root = parse_markdown_headings(text)
        for section in root.children:  # H2 sections
            print(section.title, section.body)
    """
    root = HeadingNode(level=0, title="")
    stack: list[HeadingNode] = [root]

    for line in markdown.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            # Count leading '#' characters
            level = len(stripped) - len(stripped.lstrip("#"))
            title = stripped[level:].strip()

            # Pop nodes whose level >= this heading (they are closed)
            while stack[-1].level >= level:
                stack.pop()

            node = HeadingNode(level=level, title=title)
            stack[-1].children.append(node)
            stack.append(node)
        else:
            # Accumulate content into the deepest open node
            stack[-1].body += line

    return root


class ReportTemplate:
    """Encapsulates Jinja2 template environment for report rendering."""

    def __init__(
        self,
        template_dirs: list[Path] | None = None,
        template_name: str = "entity",
    ):
        """Initialize with optional custom template directories and template name."""
        self._custom_dirs = template_dirs
        self._template_name = template_name

    @property
    def _template_dirs(self) -> list[Path]:
        """Return list of template directories to search."""
        if self._custom_dirs is not None:
            return self._custom_dirs
        return [
            Path.home() / ".local" / "share" / "feedship" / "templates",
            Path(__file__).parent.parent.parent.parent / "templates",
        ]

    @cached_property
    def environment(self) -> Environment:
        """The underlying Jinja2 Environment (lazy init, cached)."""
        return Environment(
            loader=FileSystemLoader([str(d) for d in self._template_dirs]),
            autoescape=select_autoescape(),
        )

    def get_template(self, template_name: str) -> Template:
        """Get template by name from the environment."""
        return self.environment.get_template(f"{template_name}.md.j2")

    async def render(self, report_data: ReportData) -> str:
        """Render report using the bound template name."""
        template = self.get_template(self._template_name)
        return template.render(report_data=report_data)

    def parse(self) -> HeadingNode:
        """Parse the bound template source into a heading tree (meta-analysis).

        Extracts the static heading structure from the template file itself —
        useful for understanding report schema without needing to render first.
        Body text will contain Jinja2 syntax rather than real content.
        """
        source, _, _ = self.environment.loader.get_source(
            self.environment, f"{self._template_name}.md.j2"
        )
        return parse_markdown_headings(source)
