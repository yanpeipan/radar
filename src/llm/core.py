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
    num_retries=0,
    timeout=_timeout_seconds,
)

# ---------------------------------------------------------------------------
# LLM wrapper for LCEL chains
# ---------------------------------------------------------------------------


class LLMWrapper:
    """LCEL Runnable wrapper with retry and optional structured output.

    Retry on RateLimitError, APIConnectionError, Timeout, and
    JSONSchemaValidationError so all chains benefit uniformly.
    """

    _RETRY_TYPES = (
        RateLimitError,
        APIConnectionError,
        Timeout,
        JSONSchemaValidationError,
    )

    def __init__(
        self,
        response_format: dict | None = None,
        thinking: dict | None = None,
        structured_output: type[BaseModel] | None = None,
    ):
        self.response_format = response_format
        self.thinking = thinking
        self.structured_output = structured_output

    def __call__(self) -> Runnable:
        from langchain_litellm import ChatLiteLLMRouter

        wrapper = ChatLiteLLMRouter(router=llm_router)
        if self.response_format:
            wrapper = wrapper.bind(response_format=self.response_format)
        if self.thinking:
            wrapper = wrapper.bind(thinking=self.thinking)
        if self.structured_output:
            wrapper = wrapper.with_structured_output(self.structured_output)
        return wrapper.with_retry(
            stop_after_attempt=2,
            retry_if_exception_type=self._RETRY_TYPES,
        )


def get_llm_wrapper(
    response_format: dict | None = None,
    thinking: dict | None = None,
    structured_output: type[BaseModel] | None = None,
) -> Runnable:
    """Get a ChatLiteLLMRouter wrapper with optional configuration and retry."""
    return LLMWrapper(
        response_format=response_format,
        thinking=thinking,
        structured_output=structured_output,
    )()
