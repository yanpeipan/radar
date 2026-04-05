"""Unit tests for src/application/article_view.py"""

from unittest.mock import MagicMock, patch

import pytest


class TestFetchUrlContent:
    """Tests for fetch_url_content function."""

    def test_fetch_url_content_success(self, initialized_db):
        """fetch_url_content() fetches URL and extracts content via Trafilatura."""
        from src.application.article_view import fetch_url_content

        # Mock fetch_with_fallback to return HTML (enough content to pass threshold)
        mock_response = MagicMock()
        mock_response.html_content = b"""
        <html>
        <head><title>Test Article</title></head>
        <body>
            <article>
                <h1>Main Title</h1>
                <p>This is the article content paragraph with enough text to pass the 100 char threshold.</p>
                <p>Another paragraph with more text that should be extracted by trafilatura.</p>
                <p>Yet more content here to ensure we have enough text for extraction.</p>
            </article>
        </body>
        </html>
        """

        with patch(
            "src.application.article_view.fetch_with_fallback",
            return_value=mock_response,
        ):
            result = fetch_url_content("https://example.com/article")

        assert "error" not in result
        assert result["url"] == "https://example.com/article"
        assert result["content"] is not None
        assert "extracted_at" in result

    def test_fetch_url_content_with_timeout(self, initialized_db):
        """fetch_url_content() accepts custom timeout parameter."""
        from src.application.article_view import fetch_url_content

        mock_response = MagicMock()
        mock_response.html_content = b"<html><body><p>Content with enough text here to pass threshold check</p></body></html>"

        with patch(
            "src.application.article_view.fetch_with_fallback",
            return_value=mock_response,
        ) as mock_fetch:
            fetch_url_content("https://example.com/article", timeout=60)
            mock_fetch.assert_called_once_with(
                "https://example.com/article", timeout=60
            )

    def test_fetch_url_content_network_error(self, initialized_db):
        """fetch_url_content() returns error dict when fetch fails."""
        from src.application.article_view import fetch_url_content

        with patch(
            "src.application.article_view.fetch_with_fallback",
            return_value=None,
        ):
            result = fetch_url_content("https://example.com/article")

        assert "error" in result
        assert "Failed to fetch" in result["error"]

    def test_fetch_url_content_empty_page(self, initialized_db):
        """fetch_url_content() returns error when page is too small."""
        from src.application.article_view import fetch_url_content

        mock_response = MagicMock()
        mock_response.html_content = (
            b"<html><body></body></html>"  # Too small (< 100 chars)
        )

        with patch(
            "src.application.article_view.fetch_with_fallback",
            return_value=mock_response,
        ):
            result = fetch_url_content("https://example.com/article")

        assert "error" in result
        assert "empty or blocked" in result["error"].lower()

    def test_fetch_url_content_trafilatura_failure(self, initialized_db):
        """fetch_url_content() returns error when Trafilatura extraction fails."""
        from src.application.article_view import fetch_url_content

        mock_response = MagicMock()
        # Large enough to pass threshold check
        mock_response.html_content = b"<html><body><p>Some content here with enough text to pass the 100 char threshold check for non-empty pages.</p></body></html>"

        with (
            patch(
                "src.application.article_view.fetch_with_fallback",
                return_value=mock_response,
            ),
            patch(
                "src.application.article_view.trafilatura.extract",
                return_value=None,
            ),
        ):
            result = fetch_url_content("https://example.com/article")

        assert "error" in result
        assert "Trafilatura extraction failed" in result["error"]


class TestFetchAndFillArticle:
    """Tests for fetch_and_fill_article function.

    Note: These tests verify behavior without deeply mocking storage layer
    due to import complexity with locally-imported functions.
    """

    def test_fetch_and_fill_article_not_found(self, initialized_db):
        """fetch_and_fill_article() returns error when article not in DB."""
        from src.application.article_view import fetch_and_fill_article

        result = fetch_and_fill_article("non-existent-id-xyz")

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_fetch_and_fill_article_no_link(self, initialized_db):
        """fetch_and_fill_article() returns error when article has no link."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, store_article

        feed = Feed(
            id="nolink-feed",
            name="No Link Feed",
            url="https://example.com/nolink.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        article_id = store_article(
            guid="nolink-guid",
            title="No Link Article",
            content="<p>Content</p>",
            link="",  # Empty link
            feed_id="nolink-feed",
            published_at="2024-01-15T10:00:00+00:00",
        )

        from src.application.article_view import fetch_and_fill_article

        result = fetch_and_fill_article(article_id)

        assert "error" in result
        assert "no link" in result["error"].lower()

    def test_fetch_url_content_integration(self, initialized_db):
        """Integration test: fetch_url_content can extract from real HTML with Trafilatura."""
        from src.application.article_view import fetch_url_content

        # Use a real-ish HTML sample that Trafilatura can parse
        mock_response = MagicMock()
        mock_response.html_content = b"""<!DOCTYPE html>
<html>
<head><title>Real Test Article</title></head>
<body>
<article>
<h1>Main Title</h1>
<p>This is a real paragraph with actual content. Trafilatura should be able to extract this.</p>
<p>Another paragraph of content that provides more text for extraction.</p>
<p>Third paragraph to ensure sufficient content length for extraction algorithms.</p>
</article>
</body>
</html>"""

        with patch(
            "src.application.article_view.fetch_with_fallback",
            return_value=mock_response,
        ):
            result = fetch_url_content("https://example.com/test")

        # Should succeed (Trafilatura extracts from this HTML)
        assert "error" not in result
        assert result["url"] == "https://example.com/test"
