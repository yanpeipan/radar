"""Tests for src.llm module.

Tests cover:
- LLMConfig parsing from settings
- Concurrency limiting via semaphore
"""

import asyncio

import pytest

from src.llm import reset_llm_client
from src.llm.core import LLMClient, LLMConfig


class TestLLMConfigParsing:
    """Tests for LLMConfig loading and parsing."""

    def test_llm_config_defaults(self):
        """LLMConfig should have sensible defaults when instantiated directly."""
        config = LLMConfig()
        assert config.model == "gpt-4o-mini"
        assert config.max_concurrency == 1
        assert config.timeout_seconds == 60
        assert config.daily_cap == 1000

    def test_llm_config_from_settings_loads_values(self, monkeypatch):
        """LLMConfig.from_settings() should load values from config when available."""
        mock_settings = type(
            "MockSettings",
            (),
            {"llm": {"model": "gpt-4o", "max_concurrency": 10, "timeout_seconds": 120}},
        )()
        monkeypatch.setattr("src.llm.core._get_settings", lambda: mock_settings)

        config = LLMConfig.from_settings()

        assert config.model == "gpt-4o"
        assert config.max_concurrency == 10
        assert config.timeout_seconds == 120


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
        config = LLMConfig(max_concurrency=5)
        client = LLMClient(config)

        async def mock_complete(prompt, *, max_tokens, temperature):
            await asyncio.sleep(0.01)
            return f"response_{prompt}"

        monkeypatch.setattr(client, "complete", mock_complete)

        prompts = ["first", "second", "third"]
        results = await client.batch_complete(prompts)

        assert len(results) == 3
