"""LLM client module — unified interface via litellm Router.

Simplified after Router migration: all provider routing, retries, and
fallback handled by litellm Router. This module provides concurrency
control and daily call capping.
"""

from __future__ import annotations

import logging

import litellm
from langchain_core.runnables import Runnable
from litellm import Router

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


def _get_llm_wrapper(
    max_tokens: int | None = None,
    response_format: dict | None = None,
    thinking: dict | None = None,
) -> Runnable:
    """Get a ChatLiteLLMRouter wrapper with optional configuration and retry.

    Uses the module-level llm_router which handles all provider routing,
    retries, and fallback via litellm. Retries on RateLimitError and
    APIConnectionError at the wrapper level so all chains get retry behavior.
    """
    from langchain_litellm import ChatLiteLLMRouter
    from litellm import (
        APIConnectionError,
        APITimeoutError,
        JSONSchemaValidationError,
        RateLimitError,
    )

    wrapper = ChatLiteLLMRouter(
        router=llm_router,
        max_tokens=max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS,
    )
    if response_format:
        wrapper = wrapper.bind(response_format=response_format)
    if thinking:
        wrapper = wrapper.bind(thinking=thinking)
    return wrapper.with_retry(
        stop_after_attempt=2,
        retry_if_exception_type=(
            RateLimitError,
            APIConnectionError,
            APITimeoutError,
            JSONSchemaValidationError,
        ),
    )


# Default max tokens for LLM calls
DEFAULT_MAX_TOKENS = 300
