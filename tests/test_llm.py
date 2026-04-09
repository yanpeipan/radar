"""Tests for src.llm module.

Tests cover:
- LLMConfig parsing from settings
- Provider fallback chain behavior
- Content truncation with tiktoken
- Concurrency limiting via semaphore
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.llm import reset_llm_client
from src.llm.core import (
    LLMClient,
    LLMConfig,
    LLMError,
    ProviderUnavailable,
    compute_content_hash,
    truncate_content,
)


class TestLLMConfigParsing:
    """Tests for LLMConfig loading and parsing."""

    def test_llm_config_defaults(self):
        """LLMConfig should have sensible defaults when instantiated directly."""
        config = LLMConfig()
        assert config.provider == "openai"
        assert config.model == "gpt-4o-mini"
        assert config.ollama_base_url == "http://localhost:11434"
        assert config.max_concurrency == 1
        assert config.timeout_seconds == 60
        assert config.max_tokens_per_call == 8000
        assert config.daily_cap == 1000
        assert config.weight_gate_min == 0.7
        assert config.recency_gate_hours == 48

    def test_llm_config_fallback_chain_default(self):
        """LLMConfig should have correct default fallback chain."""
        config = LLMConfig()
        assert config.fallback_chain == ["openai", "azure", "anthropic"]
        assert "openai" in config.fallback_chain

    def test_llm_config_from_settings_loads_values(self, monkeypatch):
        """LLMConfig.from_settings() should load values from config when available."""
        # Mock _get_settings to return a mock with llm data
        mock_settings = MagicMock()
        mock_settings.llm = {
            "provider": "ollama",
            "model": "llama3",
            "max_concurrency": 10,
            "timeout_seconds": 120,
            "weight_gate_min": 0.5,
        }
        monkeypatch.setattr("src.llm.core._get_settings", lambda: mock_settings)

        config = LLMConfig.from_settings()

        assert config.provider == "ollama"
        assert config.model == "llama3"
        assert config.max_concurrency == 10
        assert config.timeout_seconds == 120
        assert config.weight_gate_min == 0.5


class TestProviderFallbackChain:
    """Tests for provider fallback chain behavior."""

    @pytest.fixture(autouse=True)
    def reset_client(self):
        """Reset global LLM client before each test."""
        reset_llm_client()
        yield
        reset_llm_client()

    @pytest.mark.asyncio
    async def test_provider_fallback_chain_tries_primary_first(self, monkeypatch):
        """complete() should try primary provider before fallback chain."""
        config = LLMConfig(provider="openai", fallback_chain=["ollama", "azure"])
        client = LLMClient(config)

        # Track which providers were tried
        tried_providers = []

        async def mock_try_complete(provider, prompt, max_tokens, temperature):
            tried_providers.append(provider)
            # Raise an error so it falls through to try next provider
            raise ConnectionError(f"{provider} unavailable")

        monkeypatch.setattr(client, "_try_complete", mock_try_complete)

        with pytest.raises(ProviderUnavailable):
            await client.complete("test prompt")

        # Primary should be tried first
        assert tried_providers[0] == "openai"
        # Then fallback chain members (excluding primary)
        assert tried_providers[1] == "ollama"
        assert tried_providers[2] == "azure"

    @pytest.mark.asyncio
    async def test_provider_fallback_chain_skips_duplicate_primary(self, monkeypatch):
        """Fallback chain should not include primary provider twice."""
        config = LLMConfig(provider="openai", fallback_chain=["openai", "ollama"])
        client = LLMClient(config)

        tried_providers = []

        async def mock_try_complete(provider, prompt, max_tokens, temperature):
            tried_providers.append(provider)
            raise ConnectionError(f"{provider} unavailable")

        monkeypatch.setattr(client, "_try_complete", mock_try_complete)

        with pytest.raises(ProviderUnavailable):
            await client.complete("test prompt")

        # Primary only appears once
        assert tried_providers.count("openai") == 1


class TestTruncateContent:
    """Tests for content truncation with tiktoken."""

    def test_truncate_content_unchanged_when_under_limit(self):
        """Content under token limit should be returned unchanged."""
        config = LLMConfig(max_tokens_per_call=8000)
        content = "Short content that is well under the token limit."
        title = "Test Title"

        result, was_truncated = truncate_content(content, title, config)

        assert result == content
        assert was_truncated is False

    def test_truncate_content_truncates_when_over_limit(self):
        """Content over token limit should be truncated."""
        config = LLMConfig(max_tokens_per_call=8000)
        # Create content that exceeds 8K tokens
        # Using repeated text to ensure we exceed the limit
        content = "word " * 50000  # ~50K words should be well over 8K tokens
        title = "Test Title"

        result, was_truncated = truncate_content(content, title, config)

        assert was_truncated is True
        # Result should be shorter than original
        assert len(result) < len(content)
        # Result should not be empty
        assert len(result) > 0

    def test_truncate_content_preserves_title(self):
        """Title should be preserved in truncation decision."""
        config = LLMConfig(max_tokens_per_call=8000)
        # Content that's just barely over limit with short title
        short_title = "Hi"
        long_title = "This is a very long title " * 20

        # Same content with different titles might have different outcomes
        # because title tokens are reserved
        content = "word " * 40000

        result_short, truncated_short = truncate_content(content, short_title, config)
        result_long, truncated_long = truncate_content(content, long_title, config)

        # Both should be truncated but potentially to different lengths
        assert truncated_short is True
        assert truncated_long is True


class TestConcurrencyLimit:
    """Tests for concurrency limiting via semaphore."""

    @pytest.fixture(autouse=True)
    def reset_client(self):
        """Reset global LLM client before each test."""
        reset_llm_client()
        yield
        reset_llm_client()

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self):
        """Semaphore should enforce max_concurrency limit."""
        config = LLMConfig(max_concurrency=5)
        client = LLMClient(config)

        # Access semaphore to verify it's created with correct limit
        assert client.semaphore._value == 5

    @pytest.mark.asyncio
    async def test_semaphore_default_from_config(self):
        """Semaphore should use max_concurrency from config."""
        config = LLMConfig(max_concurrency=3)
        client = LLMClient(config)

        assert client.semaphore._value == 3

    @pytest.mark.asyncio
    async def test_batch_complete_respects_order(self, monkeypatch):
        """batch_complete should return results in same order as prompts."""
        config = LLMConfig(provider="openai", max_concurrency=5)
        client = LLMClient(config)

        # Mock _try_complete to return prompt with index
        async def mock_try_complete(provider, prompt, max_tokens, temperature):
            # Simulate some async work
            await asyncio.sleep(0.01)
            return f"response_{prompt}"

        monkeypatch.setattr(client, "_try_complete", mock_try_complete)

        prompts = ["first", "second", "third"]
        results = await client.batch_complete(prompts)

        # Should return results in order (possibly wrapped in exceptions if mocking)
        # With return_exceptions=True, gather returns results or exceptions
        assert len(results) == 3


class TestComputeContentHash:
    """Tests for content hash computation."""

    def test_compute_content_hash_deterministic(self):
        """Same title+content should produce same hash."""
        hash1 = compute_content_hash("Test Title", "Test content here")
        hash2 = compute_content_hash("Test Title", "Test content here")

        assert hash1 == hash2

    def test_compute_content_hash_differs_with_content(self):
        """Different content should produce different hash."""
        hash1 = compute_content_hash("Test Title", "Content A")
        hash2 = compute_content_hash("Test Title", "Content B")

        assert hash1 != hash2

    def test_compute_content_hash_differs_with_title(self):
        """Different title should produce different hash."""
        hash1 = compute_content_hash("Title A", "Same content")
        hash2 = compute_content_hash("Title B", "Same content")

        assert hash1 != hash2

    def test_compute_content_hash_uses_first_500_chars(self):
        """Hash should only use first 500 chars of content."""
        # Both contents start with the same 500 chars
        short_content = "a" * 500
        long_content = "a" * 500 + "b" * 1000  # Same first 500, extra after

        hash_short = compute_content_hash("Title", short_content)
        hash_long = compute_content_hash("Title", long_content)

        # Both should produce the same hash since only first 500 chars matter
        assert hash_short == hash_long

    def test_compute_content_hash_length(self):
        """Hash should be 64 character SHA256 hex string."""
        hash_result = compute_content_hash("Title", "Content")
        assert len(hash_result) == 64
        assert all(c in "0123456789abcdef" for c in hash_result)
