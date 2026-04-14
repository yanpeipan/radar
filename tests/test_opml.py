"""Unit tests for OPML export and import functions."""

import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from src.application.opml import (
    FeedEntry,
    export_feeds_to_opml,
    parse_opml_file,
)
from src.cli import cli
from src.models import Feed
from src.storage.sqlite import add_feed, init_db, upsert_feed

# =============================================================================
# export_feeds_to_opml tests
# =============================================================================


class TestExportFeedsToOpml:
    """Tests for export_feeds_to_opml function."""

    def test_export_empty_list(self):
        """export_feeds_to_opml with empty list returns valid OPML with no outlines."""
        result = export_feeds_to_opml([])
        assert '<?xml version="1.0" encoding="UTF-8"?>' in result
        assert '<opml version="2.0">' in result
        assert "<head>" in result
        assert "<body>" in result
        assert "</body>" in result
        assert "</opml>" in result
        assert "outline" not in result.lower() or "<outline" not in result

    def test_export_single_feed(self):
        """export_feeds_to_opml serialises a single feed as an outline element."""
        feeds = [
            Feed(
                id="export-1",
                name="Example Blog",
                url="https://example.com/feed.xml",
                etag=None,
                modified_at=None,
                fetched_at=None,
                created_at="2024-01-01T00:00:00+00:00",
            )
        ]
        result = export_feeds_to_opml(feeds)
        assert 'xmlUrl="https://example.com/feed.xml"' in result
        assert 'text="Example Blog"' in result
        assert 'type="rss"' in result

    def test_export_multiple_feeds_ungrouped(self):
        """export_feeds_to_opml places all ungrouped feeds directly under body."""
        feeds = [
            Feed(
                id="export-2a",
                name="Feed A",
                url="https://example.com/a.xml",
                etag=None,
                modified_at=None,
                fetched_at=None,
                created_at="2024-01-01T00:00:00+00:00",
            ),
            Feed(
                id="export-2b",
                name="Feed B",
                url="https://example.com/b.xml",
                etag=None,
                modified_at=None,
                fetched_at=None,
                created_at="2024-01-02T00:00:00+00:00",
            ),
        ]
        result = export_feeds_to_opml(feeds)
        assert 'xmlUrl="https://example.com/a.xml"' in result
        assert 'xmlUrl="https://example.com/b.xml"' in result

    def test_export_feeds_with_groups(self):
        """export_feeds_to_opml groups feeds under nested outline elements."""
        feeds = [
            Feed(
                id="export-3a",
                name="AI News",
                url="https://example.com/ai.xml",
                etag=None,
                modified_at=None,
                fetched_at=None,
                created_at="2024-01-01T00:00:00+00:00",
                group="AI",
            ),
            Feed(
                id="export-3b",
                name="Tech News",
                url="https://example.com/tech.xml",
                etag=None,
                modified_at=None,
                fetched_at=None,
                created_at="2024-01-02T00:00:00+00:00",
                group="Tech",
            ),
        ]
        result = export_feeds_to_opml(feeds)
        # Groups appear as outline wrappers
        assert 'text="AI"' in result
        assert 'text="Tech"' in result
        # Feeds appear inside their respective groups
        assert 'xmlUrl="https://example.com/ai.xml"' in result
        assert 'xmlUrl="https://example.com/tech.xml"' in result

    def test_export_mixed_grouped_and_ungrouped(self):
        """export_feeds_to_opml handles a mix of grouped and ungrouped feeds."""
        feeds = [
            Feed(
                id="export-4a",
                name="Grouped Feed",
                url="https://example.com/grouped.xml",
                etag=None,
                modified_at=None,
                fetched_at=None,
                created_at="2024-01-01T00:00:00+00:00",
                group="AI",
            ),
            Feed(
                id="export-4b",
                name="Lone Feed",
                url="https://example.com/lone.xml",
                etag=None,
                modified_at=None,
                fetched_at=None,
                created_at="2024-01-02T00:00:00+00:00",
            ),
        ]
        result = export_feeds_to_opml(feeds)
        assert 'text="AI"' in result
        assert 'xmlUrl="https://example.com/grouped.xml"' in result
        assert 'xmlUrl="https://example.com/lone.xml"' in result

    def test_export_escapes_special_characters(self):
        """export_feeds_to_opml escapes XML special characters in feed names."""
        feeds = [
            Feed(
                id="export-5",
                name='Feed with <special> & "chars"',
                url="https://example.com/special.xml",
                etag=None,
                modified_at=None,
                fetched_at=None,
                created_at="2024-01-01T00:00:00+00:00",
            )
        ]
        result = export_feeds_to_opml(feeds)
        # & must be escaped as &amp; and < as &lt;
        assert "&amp;" in result or "&lt;" in result
        # Raw unescaped characters should not appear in XML attributes
        assert 'text="Feed with <special>' not in result


# =============================================================================
# parse_opml_file tests
# =============================================================================


class TestParseOpmlFile:
    """Tests for parse_opml_file function."""

    def test_parse_valid_opml_with_feeds(self, tmp_path):
        """parse_opml_file extracts feed entries from a valid OPML file."""
        opml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>Test Export</title></head>
  <body>
    <outline text="Example Blog" title="Example Blog" type="rss"
             xmlUrl="https://example.com/feed.xml"/>
    <outline text="Another Site" title="Another Site" type="rss"
             xmlUrl="https://example.com/feed2.xml"/>
  </body>
</opml>
"""
        opml_file = tmp_path / "feeds.opml"
        opml_file.write_text(opml_content, encoding="utf-8")

        entries = parse_opml_file(str(opml_file))

        assert len(entries) == 2
        assert entries[0].name == "Example Blog"
        assert entries[0].url == "https://example.com/feed.xml"
        assert entries[1].name == "Another Site"
        assert entries[1].url == "https://example.com/feed2.xml"

    def test_parse_opml_with_nested_groups(self, tmp_path):
        """parse_opml_file extracts group names from parent outline elements."""
        opml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>Grouped Feeds</title></head>
  <body>
    <outline text="AI" title="AI Feeds">
      <outline text="AI News" xmlUrl="https://example.com/ai.xml"/>
      <outline text="LLM News" xmlUrl="https://example.com/llm.xml"/>
    </outline>
    <outline text="Tech" title="Tech Feeds">
      <outline text="Tech Blog" xmlUrl="https://example.com/tech.xml"/>
    </outline>
  </body>
</opml>
"""
        opml_file = tmp_path / "grouped.opml"
        opml_file.write_text(opml_content, encoding="utf-8")

        entries = parse_opml_file(str(opml_file))

        assert len(entries) == 3
        ai_feeds = [e for e in entries if e.group == "AI"]
        tech_feeds = [e for e in entries if e.group == "Tech"]
        assert len(ai_feeds) == 2
        assert len(tech_feeds) == 1
        assert ai_feeds[0].url == "https://example.com/ai.xml"
        assert tech_feeds[0].url == "https://example.com/tech.xml"

    def test_parse_opml_with_category_attribute(self, tmp_path):
        """parse_opml_file uses category attribute on feed outline when present."""
        opml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head/>
  <body>
    <outline text="News" xmlUrl="https://example.com/news.xml"
             category="News"/>
  </body>
</opml>
"""
        opml_file = tmp_path / "category.opml"
        opml_file.write_text(opml_content, encoding="utf-8")

        entries = parse_opml_file(str(opml_file))

        assert len(entries) == 1
        assert entries[0].group == "News"

    def test_parse_opml_category_overrides_parent_group(self, tmp_path):
        """parse_opml_file prefers category attr over parent group outline."""
        opml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head/>
  <body>
    <outline text="ParentGroup">
      <outline text="Feed" xmlUrl="https://example.com/feed.xml"
               category="OverrideGroup"/>
    </outline>
  </body>
</opml>
"""
        opml_file = tmp_path / "override.opml"
        opml_file.write_text(opml_content, encoding="utf-8")

        entries = parse_opml_file(str(opml_file))

        assert len(entries) == 1
        # Category attr takes precedence over parent outline text
        assert entries[0].group == "OverrideGroup"

    def test_parse_opml_empty_body(self, tmp_path):
        """parse_opml_file returns empty list when body has no feed outlines."""
        opml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>Empty</title></head>
  <body>
    <outline text="Group without feeds">
      <outline text="Nested group">
      </outline>
    </outline>
  </body>
</opml>
"""
        opml_file = tmp_path / "empty.opml"
        opml_file.write_text(opml_content, encoding="utf-8")

        entries = parse_opml_file(str(opml_file))

        assert entries == []

    def test_parse_opml_missing_body(self, tmp_path):
        """parse_opml_file returns empty list when no body element exists."""
        opml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>No Body</title></head>
</opml>
"""
        opml_file = tmp_path / "nobody.opml"
        opml_file.write_text(opml_content, encoding="utf-8")

        entries = parse_opml_file(str(opml_file))

        assert entries == []

    def test_parse_invalid_xml_raises_value_error(self, tmp_path):
        """parse_opml_file raises ValueError when file is not valid XML."""
        opml_file = tmp_path / "bad.opml"
        opml_file.write_text("this is not xml <><><", encoding="utf-8")

        with pytest.raises(ValueError, match="Invalid XML"):
            parse_opml_file(str(opml_file))

    def test_parse_non_opml_raises_value_error(self, tmp_path):
        """parse_opml_file raises ValueError when root element is not <opml>."""
        opml_file = tmp_path / "notopml.xml"
        opml_file.write_text(
            '<?xml version="1.0"?><rss version="2.0"><channel/></rss>',
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="Not a valid OPML file"):
            parse_opml_file(str(opml_file))

    def test_parse_nonexistent_file_raises_file_not_found(self):
        """parse_opml_file raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            parse_opml_file("/nonexistent/path/feeds.opml")


# =============================================================================
# CLI feed export --opml tests
# =============================================================================


class TestFeedExportCommand:
    """Tests for CLI feed export --opml command."""

    def test_feed_export_opml_empty(self, cli_runner, initialized_db):
        """feed export --opml with no feeds outputs 'No feeds to export.'."""
        result = cli_runner.invoke(cli, ["feed", "export", "--opml"])
        assert result.exit_code == 0
        assert "No feeds to export" in result.output

    def test_feed_export_opml_with_feeds(self, cli_runner, initialized_db):
        """feed export --opml shows feeds in OPML XML output."""
        # Add a feed directly to the database
        feed = Feed(
            id="export-cli-1",
            name="CLI Export Feed",
            url="https://example.com/export.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        result = cli_runner.invoke(cli, ["feed", "export", "--opml"])
        assert result.exit_code == 0
        assert "CLI Export Feed" in result.output
        assert "https://example.com/export.xml" in result.output

    def test_feed_export_opml_to_file(self, cli_runner, initialized_db, tmp_path):
        """feed export --opml -o writes OPML to the specified file."""
        feed = Feed(
            id="export-file-1",
            name="File Export Feed",
            url="https://example.com/file.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        output_file = tmp_path / "export.opml"
        result = cli_runner.invoke(
            cli, ["feed", "export", "--opml", "-o", str(output_file)]
        )
        assert result.exit_code == 0
        assert output_file.read_text(encoding="utf-8").count("File Export Feed") > 0


# =============================================================================
# CLI feed import tests
# =============================================================================


class TestFeedImportCommand:
    """Tests for CLI feed import command."""

    def test_feed_import_nonexistent_file(self, cli_runner, initialized_db):
        """feed import with non-existent file exits with error.

        Exit code 2 comes from Click's built-in Path(exists=True) validator,
        which fires before the command handler even runs.
        """
        result = cli_runner.invoke(cli, ["feed", "import", "/nonexistent/file.opml"])
        # Click raises error (exit code 2) when Path(exists=True) validation fails
        assert result.exit_code == 2
        assert (
            "not found" in result.output.lower()
            or "nonexistent" in result.output.lower()
        )

    def test_feed_import_empty_opml(self, cli_runner, initialized_db, tmp_path):
        """feed import with no feeds outputs 'No feeds found'."""
        opml_file = tmp_path / "empty.opml"
        opml_file.write_text(
            '<?xml version="1.0"?><opml version="2.0"><head/><body/></opml>',
            encoding="utf-8",
        )

        result = cli_runner.invoke(cli, ["feed", "import", str(opml_file)], input="n\n")
        assert result.exit_code == 0
        assert "No feeds found" in result.output

    def test_feed_import_invalid_xml(self, cli_runner, initialized_db, tmp_path):
        """feed import with invalid XML exits with error."""
        opml_file = tmp_path / "bad.opml"
        opml_file.write_text("not valid xml", encoding="utf-8")

        result = cli_runner.invoke(cli, ["feed", "import", str(opml_file)])
        assert result.exit_code == 1
        assert "Invalid" in result.output

    def test_feed_import_automatic_adds_feeds(
        self, cli_runner, initialized_db, tmp_path
    ):
        """feed import --automatic on adds feeds without confirmation prompt."""
        opml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head/>
  <body>
    <outline text="Test Feed" xmlUrl="https://example.com/test.xml"/>
  </body>
</opml>
"""
        opml_file = tmp_path / "single.opml"
        opml_file.write_text(opml_content, encoding="utf-8")

        result = cli_runner.invoke(
            cli, ["feed", "import", str(opml_file), "--automatic", "on"]
        )
        assert result.exit_code == 0
        assert "Imported" in result.output or "Added" in result.output

    def test_feed_import_skips_duplicates(self, cli_runner, initialized_db, tmp_path):
        """feed import skips feeds that already exist in database."""
        # Pre-add the feed
        existing = Feed(
            id="import-dup-1",
            name="Existing Feed",
            url="https://example.com/existing.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(existing)

        opml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head/>
  <body>
    <outline text="Existing Feed" xmlUrl="https://example.com/existing.xml"/>
  </body>
</opml>
"""
        opml_file = tmp_path / "dup.opml"
        opml_file.write_text(opml_content, encoding="utf-8")

        result = cli_runner.invoke(
            cli, ["feed", "import", str(opml_file), "--automatic", "on"]
        )
        assert result.exit_code == 0
        assert (
            "skipped" in result.output.lower() or "duplicate" in result.output.lower()
        )
