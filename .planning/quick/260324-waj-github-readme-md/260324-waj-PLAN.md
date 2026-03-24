---
phase: quick
plan: "260324-waj"
type: execute
wave: 1
depends_on: []
files_modified:
  - README.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "README clearly explains what the project does"
    - "README shows how to install and use the tool"
    - "README lists key features"
    - "README provides examples of commands"
  artifacts:
    - path: README.md
      provides: Project documentation
      min_lines: 100
  key_links: []
---

<objective>
Create a comprehensive README.md for the rss-reader project that follows GitHub best practices.
</objective>

<execution_context>
@/Users/y3/radar/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@/Users/y3/radar/pyproject.toml
@/Users/y3/radar/src/cli.py
@/Users/y3/radar/docs/feed.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create README.md with standard sections</name>
  <files>README.md</files>
  <action>
    Create README.md at project root with these sections:

    1. **Badges** - Python version, License (MIT)
    2. **Project Title + One-liner** - "rss-reader: A personal information system for collecting, subscribing to, and organizing information sources"
    3. **Features** (bullet points):
       - RSS/Atom feed subscription and parsing
       - GitHub releases tracking
       - Web article extraction with readability
       - SQLite local storage
       - CLI tool with intuitive commands
       - Tag-based organization with AI auto-tagging
       - Full-text search across articles
    4. **Tech Stack** - feedparser, httpx, BeautifulSoup4, lxml, click, PyGithub, etc.
    5. **Installation** - pip install or uv pip install, Python >=3.10
    6. **Quick Start** - Show basic commands:
       - `rss-reader feed add <url>` - Add a feed
       - `rss-reader feed list` - List feeds
       - `rss-reader refresh` - Fetch latest articles
       - `rss-reader article list` - Show articles
       - `rss-reader tag --auto` - Auto-tag articles
    7. **Configuration** - config.yaml location and options
    8. **Project Structure** - Brief overview of src/ directories
    9. **License** - MIT

    Use clear markdown formatting with code blocks for commands.
  </action>
  <verify>
    <automated>wc -l README.md && head -20 README.md</automated>
  </verify>
  <done>README.md exists with 100+ lines, includes all sections listed above</done>
</task>

</tasks>

<verification>
README.md renders correctly on GitHub and contains all essential sections
</verification>

<success_criteria>
README.md created at project root with:
- Clear project description
- Feature list
- Installation instructions
- Usage examples with CLI commands
- Tech stack overview
- Project structure
</success_criteria>

<output>
After completion, create `.planning/quick/260324-waj-github-readme-md/260324-waj-SUMMARY.md`
</output>
