"""LLM client module — unified interface via litellm Router.

Simplified after Router migration: all provider routing, retries, and
fallback handled by litellm Router. This module provides concurrency
control and daily call capping.
"""

from __future__ import annotations

import logging

import litellm
from langchain_core.runnables import Runnable
from langchain_litellm import ChatLiteLLMRouter
from litellm import (
    APIConnectionError,
    InternalServerError,
    JSONSchemaValidationError,
    RateLimitError,
    Router,
    Timeout,
)
from pydantic import BaseModel

from src.application.config import _get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# LiteLLM Router singleton — configured from settings
# ---------------------------------------------------------------------------

_llm_settings = _get_settings()
_llm_config = _llm_settings.llm or {}
_model_list: list[dict] = _llm_config.get("model_list", [])
_routing_strategy = _llm_config.get("routing_strategy", "usage-based-routing")
_timeout_seconds: int = _llm_config.get("timeout_seconds", 60)

# Drop unsupported params per-model (e.g. thinking not supported by MiniMax-M2.7)
litellm.drop_params = True

llm_router: Router = Router(
    model_list=_model_list,
    routing_strategy=_routing_strategy,
    timeout=_timeout_seconds,
)

# ---------------------------------------------------------------------------
# LLM wrapper for LCEL chains
# ---------------------------------------------------------------------------


class LLMWrapper(Runnable):
    """LCEL Runnable wrapper with retry and optional structured output.

    Retry on RateLimitError, APIConnectionError, Timeout, and
    JSONSchemaValidationError so all chains benefit uniformly.
    """

    _RETRY_TYPES = (
        RateLimitError,
        APIConnectionError,
        Timeout,
        JSONSchemaValidationError,
        InternalServerError,
    )

    def __init__(
        self,
        response_format: dict | None = None,
        thinking: dict | None = None,
        structured_output: type[BaseModel] | None = None,
        _retry_config: dict | None = None,
        **bind_kwargs,
    ):
        self.response_format = response_format
        self.thinking = thinking
        self.structured_output = structured_output
        self._retry_config = _retry_config or {
            "stop_after_attempt": 2,
            "retry_if_exception_type": self._RETRY_TYPES,
        }
        self._bind_kwargs = bind_kwargs

    def invoke(self, input, config=None):
        router = self._build_router()
        return router.invoke(input, config)

    def ainvoke(self, input, config=None):
        router = self._build_router()
        return router.ainvoke(input, config)

    def _build_router(self) -> ChatLiteLLMRouter:
        router = ChatLiteLLMRouter(router=llm_router)
        if self.response_format:
            router = router.bind(response_format=self.response_format)
        if self.thinking:
            router = router.bind(thinking=self.thinking)
        for k, v in self._bind_kwargs.items():
            router = router.bind(**{k: v})
        if self.structured_output:
            router = router.with_structured_output(self.structured_output)
        return router.with_retry(**self._retry_config)

    def bind(self, **kwargs) -> LLMWrapper:
        """Return new LLMWrapper with kwargs merged."""
        new_kwargs = {**self._bind_kwargs, **kwargs}
        return LLMWrapper(
            response_format=self.response_format,
            thinking=self.thinking,
            structured_output=self.structured_output,
            _retry_config=self._retry_config,
            **new_kwargs,
        )

    def with_structured_output(self, schema, **kwargs) -> LLMWrapper:
        """Return new LLMWrapper with structured_output set."""
        return LLMWrapper(
            response_format=self.response_format,
            thinking=self.thinking,
            structured_output=schema,
            _retry_config=self._retry_config,
            **self._bind_kwargs,
        )

    def with_retry(self, **kwargs) -> LLMWrapper:
        """Return new LLMWrapper with merged retry config."""
        merged_retry = {**self._retry_config, **kwargs}
        return LLMWrapper(
            response_format=self.response_format,
            thinking=self.thinking,
            structured_output=self.structured_output,
            _retry_config=merged_retry,
            **self._bind_kwargs,
        )
