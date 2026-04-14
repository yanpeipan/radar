"""Unit and integration tests for report generation module.

Test Conventions:
1. NO PRIVATE FUNCTION TESTING - test only public interfaces
2. REAL DATABASE VIA tmp_path - use initialized_db fixture for database tests
3. LLM MOCKING - patch LLMClient.complete to avoid real API calls
4. CLI TESTING WITH CliRunner - use click.testing.CliRunner for CLI tests
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from src.application.articles import ArticleListItem
from src.application.dedup import deduplicate_articles
from src.cli import cli

# =============================================================================
# Dedup unit tests
# =============================================================================


class TestDedupArticles:
    """Tests for deduplicate_articles() three-level pipeline."""

    def test_dedup_articles_level1_exact_dedup(self):
        """Level 1 removes articles with identical content_hash."""
        articles = [
            ArticleListItem(
                id="art-1",
                feed_id="f1",
                feed_name="Feed 1",
                title="Original Article",
                content="Article content here",
                link="http://example.com/1",
                guid="art-1",
                published_at="2024-01-01",
                description="desc",
                content_hash="abc123",
                minhash_signature=None,
            ),
            ArticleListItem(
                id="art-2",
                feed_id="f1",
                feed_name="Feed 1",
                title="Exact Duplicate Title",
                content="Different title but same content hash",
                link="http://example.com/2",
                guid="art-2",
                published_at="2024-01-01",
                description="desc",
                content_hash="abc123",  # Same hash → Level 1 duplicate
                minhash_signature=None,
            ),
            ArticleListItem(
                id="art-3",
                feed_id="f1",
                feed_name="Feed 1",
                title="Different Article",
                content="Different content",
                link="http://example.com/3",
                guid="art-3",
                published_at="2024-01-01",
                description="desc",
                content_hash="def456",
                minhash_signature=None,
            ),
        ]
        # Level 2 MinHash is skipped (no minhash_signature)
        # Level 3 Embedding is skipped (no embeddings)
        result = deduplicate_articles(articles)
        assert len(result) == 2
        ids = [a.id for a in result]
        assert "art-1" in ids  # First occurrence preserved
        assert "art-2" not in ids  # Duplicate removed
        assert "art-3" in ids

    def test_dedup_articles_preserves_first_occurrence(self):
        """Level 1 always keeps the first occurrence, removes later ones."""
        articles = [
            ArticleListItem(
                id="first",
                feed_id="f1",
                feed_name="Feed 1",
                title="Title A",
                content="Content A",
                link="http://example.com/1",
                guid="first",
                published_at="2024-01-01",
                description="desc",
                content_hash="same-hash",
                minhash_signature=None,
            ),
            ArticleListItem(
                id="second",
                feed_id="f1",
                feed_name="Feed 1",
                title="Title B",
                content="Content B",
                link="http://example.com/2",
                guid="second",
                published_at="2024-01-01",
                description="desc",
                content_hash="same-hash",
                minhash_signature=None,
            ),
            ArticleListItem(
                id="third",
                feed_id="f1",
                feed_name="Feed 1",
                title="Title C",
                content="Content C",
                link="http://example.com/3",
                guid="third",
                published_at="2024-01-01",
                description="desc",
                content_hash="same-hash",
                minhash_signature=None,
            ),
        ]
        result = deduplicate_articles(articles)
        assert len(result) == 1
        assert result[0].id == "first"

    def test_dedup_articles_empty_list(self):
        """Empty input returns empty list (no crash)."""
        result = deduplicate_articles([])
        assert result == []

    def test_dedup_articles_no_duplicates(self):
        """Articles with unique content_hash are all preserved."""
        articles = [
            ArticleListItem(
                id="unique-1",
                feed_id="f1",
                feed_name="Feed 1",
                title="Unique Article 1",
                content="Content 1",
                link="http://example.com/1",
                guid="unique-1",
                published_at="2024-01-01",
                description="desc",
                content_hash="hash-001",
                minhash_signature=None,
            ),
            ArticleListItem(
                id="unique-2",
                feed_id="f1",
                feed_name="Feed 1",
                title="Unique Article 2",
                content="Content 2",
                link="http://example.com/2",
                guid="unique-2",
                published_at="2024-01-01",
                description="desc",
                content_hash="hash-002",
                minhash_signature=None,
            ),
        ]
        result = deduplicate_articles(articles)
        assert len(result) == 2
        ids = [a.id for a in result]
        assert "unique-1" in ids
        assert "unique-2" in ids

    def test_dedup_articles_no_hash_preserved(self):
        """Articles without content_hash are kept (legacy data)."""
        articles = [
            ArticleListItem(
                id="legacy-1",
                feed_id="f1",
                feed_name="Feed 1",
                title="Legacy Article",
                content="No hash stored",
                link="http://example.com/1",
                guid="legacy-1",
                published_at="2024-01-01",
                description="desc",
                content_hash=None,  # No hash
                minhash_signature=None,
            ),
            ArticleListItem(
                id="legacy-2",
                feed_id="f1",
                feed_name="Feed 1",
                title="Another Legacy",
                content="Also no hash",
                link="http://example.com/2",
                guid="legacy-2",
                published_at="2024-01-01",
                description="desc",
                content_hash=None,  # No hash
                minhash_signature=None,
            ),
        ]
        result = deduplicate_articles(articles)
        # Both should be preserved (no hash → not a duplicate source)
        assert len(result) == 2


# =============================================================================
# LLM chain unit tests
# =============================================================================

# =============================================================================
# AsyncLLMWrapper unit tests
# =============================================================================


@pytest.mark.skip(reason="AsyncLLMWrapper not implemented")
class TestAsyncLLMWrapper:
    """Tests for AsyncLLMWrapper.invoke() handling dict and string inputs."""

    def test_async_wrapper_invoke_dict_input(self):
        """AsyncLLMWrapper.invoke() handles dict input correctly."""
        from src.llm.chains import AsyncLLMWrapper

        wrapper = AsyncLLMWrapper()

        # Mock the underlying _client directly (it's a private attribute)
        mock_client = MagicMock()
        mock_client.complete = AsyncMock(return_value="Mocked response")

        with patch.object(wrapper, "_client", mock_client):
            # Dict input (LCEL pass-through format)
            result = wrapper.invoke({"title": "Test Title", "content": "Test content"})
            assert result == "Mocked response"
            mock_client.complete.assert_called_once()

    def test_async_wrapper_invoke_string_input(self):
        """AsyncLLMWrapper.invoke() handles string input correctly."""
        from src.llm.chains import AsyncLLMWrapper

        wrapper = AsyncLLMWrapper()

        # Mock the underlying _client directly
        mock_client = MagicMock()
        mock_client.complete = AsyncMock(return_value="String response")

        with patch.object(wrapper, "_client", mock_client):
            # String input (direct format)
            result = wrapper.invoke("Direct string prompt")
            assert result == "String response"
            mock_client.complete.assert_called_once()

    def test_async_wrapper_invoke_max_tokens_from_config(self):
        """AsyncLLMWrapper.invoke() uses max_tokens from config dict."""
        from src.llm.chains import AsyncLLMWrapper

        wrapper = AsyncLLMWrapper(max_tokens=100)

        mock_client = MagicMock()
        mock_client.complete = AsyncMock(return_value="Response")

        with patch.object(wrapper, "_client", mock_client):
            wrapper.invoke("test prompt", config={"max_tokens": 50})
            # The wrapper should use max_tokens=50 from config, not instance default 100
            mock_client.complete.assert_called_once()
            call_kwargs = mock_client.complete.call_args[1]
            assert call_kwargs.get("max_tokens") == 50


# =============================================================================
# CLI report unit tests
# =============================================================================


class TestReportCLI:
    """Tests for 'feedship report' CLI command."""

    def test_report_cli_no_articles(self, cli_runner, initialized_db):
        """CLI exits gracefully with a message when no articles exist in date range."""
        # Use a date range far in the future — no articles will exist
        result = cli_runner.invoke(
            cli,
            ["report", "--since", "2099-01-01", "--until", "2099-01-02"],
        )
        # Should exit cleanly (not crash)
        assert result.exit_code == 0
        # Should show message about no articles or need to summarize
        assert (
            "No articles" in result.output
            or "summarize" in result.output
            or "summarized" in result.output
        )

    def test_report_cli_no_articles_json_output(self, cli_runner, initialized_db):
        """CLI --json exits 0 and outputs JSON when no articles exist."""
        result = cli_runner.invoke(
            cli,
            ["report", "--since", "2099-01-01", "--until", "2099-01-02", "--json"],
        )
        assert result.exit_code == 0
        import json

        # Parse JSON from output (may have ANSI codes)
        import re

        # Extract JSON-like content from output
        json_match = re.search(r"\{.*\}", result.output, re.DOTALL)
        assert json_match is not None
        data = json.loads(json_match.group())
        assert data.get("success") is True
        assert data.get("total_articles") == 0


class TestReportIntegration:
    """Integration tests for full report pipeline with mocked LLM and ChromaDB."""

    @pytest.mark.skip(reason="AsyncLLMWrapper not implemented")
    def test_report_end_to_end(self, cli_runner, initialized_db, monkeypatch):
        """Full pipeline: DB query → clustering → render produces output."""
        from src.models import Feed
        from src.storage.sqlite import add_feed, store_article

        # Setup: add feed and article
        feed = Feed(
            id="e2e-feed",
            name="E2E Feed",
            url="https://e2e.example/feed.xml",
            etag=None,
            modified_at=None,
            fetched_at=None,
            created_at="2024-01-01T00:00:00+00:00",
        )
        add_feed(feed)

        # Store a summarized article (so it shows in the report)
        article_id = store_article(
            guid="e2e-guid-1",
            title="OpenAI Releases GPT-5 Model",
            content="<p>Big AI model release</p>",
            link="https://e2e.example/article1",
            feed_id="e2e-feed",
            published_at="2024-01-15T10:00:00+00:00",
        )

        # Update article with summary and quality (simulating summarize step)
        from src.storage.sqlite import get_db

        with get_db() as conn:
            conn.execute(
                "UPDATE articles SET summary = ?, quality_score = ? WHERE id = ?",
                (
                    "OpenAI released GPT-5, a large language model with improved reasoning.",
                    0.85,
                    article_id,
                ),
            )

        # Mock ChromaDB to avoid real vector operations
        mock_collection = MagicMock()
        mock_collection.query.return_value = {"ids": [[]], "distances": [[]]}

        with (
            patch(
                "src.storage.vector.get_chroma_collection",
                return_value=mock_collection,
            ),
            patch(
                "src.llm.chains.AsyncLLMWrapper._ainvoke_raw",
                new=AsyncMock(return_value="AI模型"),
            ),
            patch(
                "src.application.summarize.summarize_article_content",
                new=AsyncMock(
                    return_value=(
                        "OpenAI released GPT-5, a large language model.",
                        0.85,
                    )
                ),
            ),
        ):
            result = cli_runner.invoke(
                cli,
                [
                    "report",
                    "--since",
                    "2024-01-01",
                    "--until",
                    "2024-01-31",
                    "--limit",
                    "10",
                ],
            )
            # Should not crash
            assert result.exit_code == 0
            # Output should contain something (either articles or no-articles message)
            assert len(result.output) > 0

    def test_v2_report_with_limit(self, cli_runner, initialized_db, monkeypatch):
        """V2 report respects --limit parameter and passes it to clustering."""
        from src.application.report.models import ReportCluster, ReportData

        limit_captured = None

        def capture_limit(**kwargs):
            nonlocal limit_captured
            limit_captured = kwargs.get("limit")
            return ReportData(
                cluster=ReportCluster(title=""),
                date_range={"since": "2024-01-01", "until": "2024-01-31"},
            )

        monkeypatch.setattr(
            "src.cli.report.cluster_articles_for_report",
            capture_limit,
        )

        result = cli_runner.invoke(
            cli,
            [
                "report",
                "--since",
                "2024-01-01",
                "--until",
                "2024-01-31",
                "--limit",
                "50",
            ],
        )
        assert result.exit_code == 0
        # v2 should be called with limit=50
        assert limit_captured == 50


# =============================================================================
# V2 clustering
# =============================================================================


class TestV2Clustering:
    """Tests for v2 topic clustering logic."""

    @pytest.mark.skip(reason="AsyncLLMWrapper not implemented")
    def test_report_v2_clustering_empty_returns_empty_layers(self, initialized_db):
        """cluster_articles_for_report returns empty ReportData when no articles."""
        from src.application.report.generator import cluster_articles_for_report
        from src.application.report.models import ReportCluster

        with (
            patch(
                "src.storage.vector.get_chroma_collection",
                return_value=MagicMock(),
            ),
            patch(
                "src.llm.chains.AsyncLLMWrapper._ainvoke_raw",
                new=AsyncMock(return_value="AI模型"),
            ),
        ):
            data = cluster_articles_for_report(
                since="2099-01-01",
                until="2099-01-02",
                limit=10,
                auto_summarize=False,
            )
            assert hasattr(data, "cluster")
            assert hasattr(data, "date_range")
            assert isinstance(data.cluster, ReportCluster)
            assert data.total_articles == 0
