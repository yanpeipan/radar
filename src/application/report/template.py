"""Layer 4: ReportTemplate — Jinja2 template environment encapsulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, Template, select_autoescape

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
    children: list["HeadingNode"] = field(default_factory=list)


def parse_markdown_headings(markdown: str) -> HeadingNode:
    """Parse rendered markdown into a heading tree.

    Uses a single-pass stack algorithm — O(n) in the number of lines.

    Returns:
        A synthetic root node (level=0, title="") whose children are the
        top-level headings found in *markdown*.

    Example::

        root = parse_markdown_headings(text)
        for section in root.children:          # H2 sections
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

    def __init__(self, template_dirs: list[Path] | None = None):
        """Initialize with optional custom template directories."""
        self._custom_dirs = template_dirs

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
        return self.environment.get_template(f"{template_name}.md")

    async def render(
        self, report_data: ReportData, template_name: str = "entity"
    ) -> str:
        """Render report using specified template. Async for consistency."""
        template = self.get_template(template_name)
        return template.render(report_data=report_data)

    def parse(self, rendered: str) -> HeadingNode:
        """Parse a rendered markdown string into a heading tree."""
        return parse_markdown_headings(rendered)
