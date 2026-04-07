#!/usr/bin/env python3
"""
Auto-format AI Daily sections.
Usage: python3 format_sections.py <date> [a|b|c|d|e|f]
       python3 format_sections.py <date>          # format all sections
"""

import re
import sys


def format_section(lines, section_name):
    items = []
    for line in lines:
        line = line.strip()
        if not line or "|" not in line:
            continue
        parts = line.split("|")
        if len(parts) >= 2:
            title = parts[0].strip()
            link = parts[1].strip()
            if title and link and link != "null":
                items.append((title, link))

    output_lines = [f"## {section_name}\n"]
    for i, (title, link) in enumerate(items, 1):
        safe_title = re.sub(r"[#*`]", "", title)
        output_lines.append(f"{i}. {safe_title}\n")
        output_lines.append(f"   来源：[**链接**]({link})\n\n")

    return "".join(output_lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: format_sections.py <date> [a|b|c|d|e|f]")
        sys.exit(1)

    date = sys.argv[1]
    base = f"/tmp/ai-daily-{date}"

    section_map = {
        "a": ("A", "links_a"),
        "b": ("B", "links_b"),
        "c": ("C", "links_c"),
        "d": ("D", "links_d"),
        "e": ("E", "links_e"),
        "f": ("F", "links_f"),
    }

    sections = sys.argv[2:] if len(sys.argv) > 2 else list("abcdef")

    for s in sections:
        if s not in section_map:
            continue
        section_name, filename = section_map[s]
        try:
            with open(f"{base}/{filename}.txt") as f:
                content = format_section(f.readlines(), section_name)
            with open(f"{base}/section_{section_name.lower()}.md", "w") as f:
                f.write(content)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
