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

from src.application.dedup import deduplicate_articles
from src.application.report import LAYER_KEYS
from src.cli import cli


# =============================================================================
# Dedup unit tests
# =============================================================================


class TestDedupArticles:
    """Tests for deduplicate_articles() three-level pipeline."""

    def test_dedup_articles_level1_exact_dedup(self):
        """Level 1 removes articles with identical content_hash."""
        articles = [
            {
                "id": "art-1",
                "title": "Original Article",
                "content": "Article content here",
                "content_hash": "abc123",
                "minhash_signature": None,
            },
            {
                "id": "art-2",
                "title": "Exact Duplicate Title",
                "content": "Different title but same content hash",
                "content_hash": "abc123",  # Same hash → Level 1 duplicate
                "minhash_signature": None,
            },
            {
                "id": "art-3",
                "title": "Different Article",
                "content": "Different content",
                "content_hash": "def456",
                "minhash_signature": None,
            },
        ]
        # Level 2 MinHash is skipped (no minhash_signature)
        # Level 3 Embedding is skipped (no embeddings)
        result = deduplicate_articles(articles)
        assert len(result) == 2
        ids = [a["id"] for a in result]
        assert "art-1" in ids  # First occurrence preserved
        assert "art-2" not in ids  # Duplicate removed
        assert "art-3" in ids

    def test_dedup_articles_preserves_first_occurrence(self):
        """Level 1 always keeps the first occurrence, removes later ones."""
        articles = [
            {
                "id": "first",
                "title": "Title A",
                "content": "Content A",
                "content_hash": "same-hash",
                "minhash_signature": None,
            },
            {
                "id": "second",
                "title": "Title B",
                "content": "Content B",
                "content_hash": "same-hash",
                "minhash_signature": None,
            },
            {
                "id": "third",
                "title": "Title C",
                "content": "Content C",
                "content_hash": "same-hash",
                "minhash_signature": None,
            },
        ]
        result = deduplicate_articles(articles)
        assert len(result) == 1
        assert result[0]["id"] == "first"

    def test_dedup_articles_empty_list(self):
        """Empty input returns empty list (no crash)."""
        result = deduplicate_articles([])
        assert result == []

    def test_dedup_articles_no_duplicates(self):
        """Articles with unique content_hash are all preserved."""
        articles = [
            {
                "id": "unique-1",
                "title": "Unique Article 1",
                "content": "Content 1",
                "content_hash": "hash-001",
                "minhash_signature": None,
            },
            {
                "id": "unique-2",
                "title": "Unique Article 2",
                "content": "Content 2",
                "content_hash": "hash-002",
                "minhash_signature": None,
            },
        ]
        result = deduplicate_articles(articles)
        assert len(result) == 2
        ids = [a["id"] for a in result]
        assert "unique-1" in ids
        assert "unique-2" in ids

    def test_dedup_articles_no_hash_preserved(self):
        """Articles without content_hash are kept (legacy data)."""
        articles = [
            {
                "id": "legacy-1",
                "title": "Legacy Article",
                "content": "No hash stored",
                "content_hash": None,  # No hash
                "minhash_signature": None,
            },
            {
                "id": "legacy-2",
                "title": "Another Legacy",
                "content": "Also no hash",
                "content_hash": None,  # No hash
                "minhash_signature": None,
            },
        ]
        result = deduplicate_articles(articles)
        # Both should be preserved (no hash → not a duplicate source)
        assert len(result) == 2


# =============================================================================
# LLM chain unit tests
# =============================================================================


class TestLLMChains:
    """Tests for LLM chain functions: get_classify_chain, get_evaluate_chain."""

    def test_llm_chain_classify_returns_valid_layer(self):
        """Classification chain returns one of the 5 valid layer keys."""
        from src.llm.chains import get_classify_chain

        chain = get_classify_chain()

        # chain.steps[-2] is AsyncLLMWrapper (chain: prompt | wrapper | parser)
        wrapper = chain.steps[-2]
        # Patch complete on the underlying client
        with patch.object(wrapper.client, "complete", new=AsyncMock(return_value="AI模型")):
            result = chain.invoke(
                {"title": "OpenAI releases GPT-5", "content": "Big model release"}
            )
            assert result in LAYER_KEYS

    def test_llm_chain_evaluate_returns_valid_json(self):
        """Evaluation chain uses JsonOutputParser (not StrOutputParser).

        Verifies the chain ends with JsonOutputParser by inspecting chain steps.
        Also directly tests JsonOutputParser.parse() with a sample JSON string
        to confirm it returns a dict with the expected structure.
        """
        from src.llm.chains import get_evaluate_chain
        from langchain_core.output_parsers import JsonOutputParser

        chain = get_evaluate_chain()
        # Verify the last step of the chain is JsonOutputParser (not StrOutputParser)
        assert isinstance(chain.steps[-1], JsonOutputParser), (
            "evaluate chain should end with JsonOutputParser"
        )

        # Verify the parser itself correctly parses a JSON string to dict
        parser = chain.steps[-1]
        result = parser.invoke('{"coherence": 0.8, "relevance": 0.9, "depth": 0.7, "structure": 0.85}')
        assert isinstance(result, dict)
        assert "coherence" in result
        assert "relevance" in result
        assert "depth" in result
        assert "structure" in result
        assert 0.0 <= result["coherence"] <= 1.0
        assert 0.0 <= result["relevance"] <= 1.0


# =============================================================================
# AsyncLLMWrapper unit tests
# =============================================================================


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
            result = wrapper.invoke(
                {"title": "Test Title", "content": "Test content"}
            )
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
            result = wrapper.invoke("test prompt", config={"max_tokens": 50})
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

    def test_report_cli_template_error(self, cli_runner, initialized_db, monkeypatch):
        """CLI catches and reports template rendering errors cleanly."""
        # Return non-empty layer data so CLI reaches the render step (total_articles > 0)
        monkeypatch.setattr(
            "src.cli.report.cluster_articles_for_report",
            lambda **kwargs: {
                "articles_by_layer": {
                    "AI应用": [
                        {
                            "id": "fake-art",
                            "title": "Fake Article",
                            "link": "https://example.com/fake",
                            "summary": "Fake summary.",
                            "quality_score": 0.8,
                        }
                    ],
                    "AI模型": [],
                    "AI基础设施": [],
                    "芯片": [],
                    "能源": [],
                },
                "layer_summaries": {"AI应用": "Summary of AI applications."},
                "date_range": {"since": "2099-01-01", "until": "2099-01-02"},
                "summarized_on_demand": 0,
            },
        )
        monkeypatch.setattr(
            "src.cli.report.cluster_articles_for_report_v2",
            lambda **kwargs: {
                "layers": [],
                "signals": {},
                "date_range": {"since": "2099-01-01", "until": "2099-01-02"},
                "summarized_on_demand": 0,
            },
        )

        # Patch render_report at the location where cli.report uses it
        # (not at src.application.report where it is defined).
        # cli.report imports render_report as a local reference.
        def fake_render(*args, **kwargs):
            raise RuntimeError("Template error: unexpected '{{' in expression")

        monkeypatch.setattr(
            "src.cli.report.render_report",
            fake_render,
        )

        async def fake_render_v2(*args, **kwargs):
            raise RuntimeError("Template error: unexpected '{{' in expression")

        monkeypatch.setattr(
            "src.cli.report.render_report_v2",
            fake_render_v2,
        )

        result = cli_runner.invoke(
            cli,
            ["report", "--since", "2099-01-01", "--until", "2099-01-02"],
        )
        # Should exit with error (template failed)
        assert result.exit_code == 1
        assert "error" in result.output.lower() or "template" in result.output.lower()

    def test_report_cli_v2_template(self, cli_runner, initialized_db, monkeypatch):
        """CLI --template v2 uses cluster_articles_for_report_v2."""
        # Track which function was called
        v2_called = False

        def track_v2(**kwargs):
            nonlocal v2_called
            v2_called = True
            return {
                "layers": [],
                "signals": {},
                "date_range": {"since": "2099-01-01", "until": "2099-01-02"},
                "summarized_on_demand": 0,
            }

        monkeypatch.setattr(
            "src.cli.report.cluster_articles_for_report_v2",
            track_v2,
        )

        result = cli_runner.invoke(
            cli,
            [
                "report",
                "--template",
                "v2",
                "--since",
                "2099-01-01",
                "--until",
                "2099-01-02",
            ],
        )
        assert result.exit_code == 0


# =============================================================================
# CLI report integration tests
# =============================================================================


class TestReportIntegration:
    """Integration tests for full report pipeline with mocked LLM and ChromaDB."""

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
        from src.storage.sqlite.impl import get_db

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

        with patch(
            "src.storage.vector.get_chroma_collection",
            return_value=mock_collection,
        ):
            # Mock LLM chains to avoid real API calls
            with patch(
                "src.llm.chains.AsyncLLMWrapper._ainvoke_raw",
                new=AsyncMock(return_value="AI模型"),
            ):
                with patch(
                    "src.application.summarize.summarize_article_content",
                    new=AsyncMock(
                        return_value=(
                            "OpenAI released GPT-5, a large language model.",
                            0.85,
                        )
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
        limit_captured = None

        def capture_limit(**kwargs):
            nonlocal limit_captured
            limit_captured = kwargs.get("limit")
            return {
                "layers": [],
                "signals": {},
                "date_range": {"since": "2024-01-01", "until": "2024-01-31"},
                "summarized_on_demand": 0,
            }

        monkeypatch.setattr(
            "src.cli.report.cluster_articles_for_report_v2",
            capture_limit,
        )

        result = cli_runner.invoke(
            cli,
            [
                "report",
                "--template",
                "v2",
                "--since",
                "2024-01-01",
                "--until",
                "2024-01-31",
                "--limit",
                "50",
            ],
        )
        assert result.exit_code == 0
        # V2 should be called with limit=50
        assert limit_captured == 50

    def test_json_output_format(self, cli_runner, initialized_db, monkeypatch):
        """--json output matches expected schema: date_range, total_articles, template."""
        # Return non-empty layer data with articles so CLI reaches JSON output step
        def fake_cluster(**kwargs):
            return {
                "articles_by_layer": {
                    "AI应用": [
                        {
                            "id": "json-test-art",
                            "title": "Test Article",
                            "link": "https://example.com/test",
                            "summary": "Test summary.",
                            "quality_score": 0.85,
                        }
                    ],
                    "AI模型": [],
                    "AI基础设施": [],
                    "芯片": [],
                    "能源": [],
                },
                "layer_summaries": {"AI应用": "Summary of AI apps."},
                "date_range": {"since": "2024-01-01", "until": "2024-01-02"},
                "summarized_on_demand": 0,
            }

        monkeypatch.setattr(
            "src.cli.report.cluster_articles_for_report",
            fake_cluster,
        )

        import asyncio

        async def fake_render(*args, **kwargs):
            return "# AI Daily Report\n## AI应用\nTest news."

        monkeypatch.setattr(
            "src.application.report.render_report",
            fake_render,
        )

        result = cli_runner.invoke(
            cli,
            [
                "report",
                "--since",
                "2024-01-01",
                "--until",
                "2024-01-02",
                "--json",
            ],
        )
        assert result.exit_code == 0

        import json
        import re

        # Extract JSON from output (may contain ANSI codes)
        json_match = re.search(r"\{.*\}", result.output, re.DOTALL)
        assert json_match is not None
        data = json.loads(json_match.group())

        # Verify expected schema fields
        assert "date_range" in data
        assert data["date_range"]["since"] == "2024-01-01"
        assert data["date_range"]["until"] == "2024-01-02"
        assert "total_articles" in data
        assert "template" in data
        assert "layers" in data


# =============================================================================
# V1 clustering tests
# =============================================================================


class TestV1Clustering:
    """Tests for v1 per-layer clustering logic."""

    def test_report_v1_clustering_layer_keys_defined(self):
        """LAYER_KEYS contains exactly the 5 AI Five-Layer Cake categories."""
        assert len(LAYER_KEYS) == 5
        assert "AI应用" in LAYER_KEYS
        assert "AI模型" in LAYER_KEYS
        assert "AI基础设施" in LAYER_KEYS
        assert "芯片" in LAYER_KEYS
        assert "能源" in LAYER_KEYS

    def test_report_v1_clustering_empty_articles_returns_empty_layers(
        self, initialized_db
    ):
        """cluster_articles_for_report returns empty layer dicts when no articles."""
        from src.application.report import cluster_articles_for_report

        with patch(
            "src.storage.vector.get_chroma_collection",
            return_value=MagicMock(),
        ):
            with patch(
                "src.llm.chains.AsyncLLMWrapper._ainvoke_raw",
                new=AsyncMock(return_value="AI应用"),
            ):
                data = cluster_articles_for_report(
                    since="2099-01-01",
                    until="2099-01-02",
                    limit=10,
                    auto_summarize=False,
                )
                assert "articles_by_layer" in data
                assert isinstance(data["articles_by_layer"], dict)
                for layer in LAYER_KEYS:
                    assert layer in data["articles_by_layer"]
                    assert isinstance(data["articles_by_layer"][layer], list)


# =============================================================================
# V2 clustering tests
# =============================================================================


class TestV2Clustering:
    """Tests for v2 topic clustering logic."""

    def test_report_v2_clustering_empty_returns_empty_layers(
        self, initialized_db
    ):
        """cluster_articles_for_report_v2 returns empty layers when no articles."""
        from src.application.report import cluster_articles_for_report_v2

        with patch(
            "src.storage.vector.get_chroma_collection",
            return_value=MagicMock(),
        ):
            with patch(
                "src.llm.chains.AsyncLLMWrapper._ainvoke_raw",
                new=AsyncMock(return_value="AI模型"),
            ):
                data = cluster_articles_for_report_v2(
                    since="2099-01-01",
                    until="2099-01-02",
                    limit=10,
                    auto_summarize=False,
                )
                assert "layers" in data
                assert "signals" in data
                assert "date_range" in data
                assert isinstance(data["layers"], list)
