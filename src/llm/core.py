"""LLM client module — unified interface via litellm Router.

Simplified after Router migration: all provider routing, retries, and
fallback handled by litellm Router. This module provides concurrency
control and daily call capping.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

import litellm
from litellm import Router

from src.application.config import _get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LLMError(Exception):
    """Base exception for LLM-related errors."""


class DailyCapExceeded(LLMError):
    """Raised when the daily LLM call cap has been exceeded."""


class ProviderUnavailable(LLMError):
    """Raised when no provider in the fallback chain is available."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class LLMConfig:
    """LLM configuration loaded from app settings."""

    model: str = "gpt-4o-mini"
    api_key: str | None = None
    max_concurrency: int = 1
    timeout_seconds: int = 60
    daily_cap: int = 1000

    @classmethod
    def from_settings(cls) -> LLMConfig:
        """Load LLM config from app settings."""
        settings = _get_settings()
        llm_data = getattr(settings, "llm", {}) or {}
        api_key = llm_data.get("api_key", "")
        if (
            isinstance(api_key, str)
            and api_key.startswith("${")
            and api_key.endswith("}")
        ):
            env_var = api_key[2:-1]
            api_key = os.environ.get(env_var)
        return cls(
            model=llm_data.get("model", "gpt-4o-mini"),
            api_key=api_key,
            max_concurrency=llm_data.get("max_concurrency", 5),
            timeout_seconds=llm_data.get("timeout_seconds", 60),
            daily_cap=llm_data.get("daily_cap", 1000),
        )


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------


class LLMClient:
    """LLM client with concurrency control and daily call cap."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig.from_settings()
        self._semaphore: asyncio.Semaphore | None = None
        self._daily_call_count: int = 0

    @property
    def semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.config.max_concurrency)
        return self._semaphore

    async def complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 300,
        temperature: float = 0.3,
        extra_body: dict | None = None,
    ) -> str:
        """Call LLM via Router.

        Args:
            prompt: The prompt to send
            max_tokens: Max response tokens
            temperature: Sampling temperature
            extra_body: Extra params passed to litellm acompletion (e.g. thinking config)

        Returns:
            LLM response text

        Raises:
            DailyCapExceeded: Daily call cap reached
            ProviderUnavailable: Router returned empty choices
        """
        if self._daily_call_count >= self.config.daily_cap:
            raise DailyCapExceeded(f"Daily cap {self.config.daily_cap} exceeded")

        async with self.semaphore:
            self._daily_call_count += 1
            try:
                kwargs: dict[str, Any] = {
                    "model": self.config.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
                if extra_body:
                    # Extract top-level params from extra_body
                    thinking = extra_body.pop("thinking", None)
                    if thinking:
                        kwargs["thinking"] = thinking
                    # response_format must be at top level (not in extra_body) for litellm
                    response_format = extra_body.pop("response_format", None)
                    if response_format:
                        kwargs["response_format"] = response_format
                    # Pass remaining fields in extra_body
                    if extra_body:
                        kwargs["extra_body"] = extra_body
                response = await llm_router.acompletion(**kwargs)
                choices = response.get("choices")
                if not choices:
                    raise ProviderUnavailable("Router returned empty choices")
                message = choices[0]["message"]
                # MiniMax/MiniMax-M2.7 returns text in reasoning_content when thinking is enabled
                content = message.get("content") or message.get("reasoning_content")
                if not content:
                    raise ProviderUnavailable("Router returned empty content")
                return content
            except litellm.Timeout:
                # Retry with extended timeout on TimeoutError
                for attempt in [2, 3]:  # 2nd and 3rd attempt with longer timeout
                    try:
                        response = await llm_router.acompletion(
                            **{
                                **kwargs,
                                "timeout": self.config.timeout_seconds * attempt,
                            }
                        )
                        choices = response.get("choices")
                        if choices:
                            message = choices[0]["message"]
                            content = message.get("content") or message.get(
                                "reasoning_content"
                            )
                            if content:
                                return content
                    except litellm.Timeout:
                        pass
                raise LLMError(
                    f"LLM call timed out after {self.config.timeout_seconds}s"
                ) from None

    async def batch_complete(
        self,
        prompts: list[str],
        *,
        max_tokens: int = 300,
        temperature: float = 0.3,
    ) -> list[str]:
        """Batch complete multiple prompts with concurrency control."""
        tasks = [
            self.complete(p, max_tokens=max_tokens, temperature=temperature)
            for p in prompts
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)  # type: ignore[return-value]

    async def batch_summarize(
        self,
        articles: list[dict],
        target_lang: str = "en",
        batch_size: int = 3,
    ) -> list[dict]:
        """Batch summarize multiple articles in one LLM call.

        Args:
            articles: list of dicts with 'content', 'title', 'id' keys
            target_lang: target language for summaries
            batch_size: number of articles per LLM call (default 3)

        Returns:
            list of dicts with 'id', 'summary', 'quality_score', 'keywords'
        """
        if not articles:
            return []

        results: list[dict] = []
        pending: list[dict] = []

        for i in range(0, len(articles), batch_size):
            batch = articles[i : i + batch_size]

            article_texts = []
            for idx, article in enumerate(batch, start=1):
                title = article.get("title", "Untitled")[:100]
                content = article.get("content") or article.get("description") or ""
                content_sample = " ".join(content.split()[:200]) if content else ""
                article_texts.append(
                    f"{idx}. [Title] {title}\n[Content] {content_sample[:500]}"
                )

            articles_block = "\n\n".join(article_texts)

            prompt = f"""You are a research article analyst. For each article, provide a summary, quality score (0-1), and keywords.

{articles_block}

Return JSON array (one object per article in order):
[
  {{"id": "article_id", "summary": "...", "quality_score": 0.75, "keywords": ["AI", "transformer"]}}
]

Return ONLY the JSON array, no markdown code blocks or other text."""

            try:
                response = await self.complete(prompt, max_tokens=2000, temperature=0.3)
                clean_response = response.strip()
                if clean_response.startswith("```"):
                    lines = clean_response.split("\n")
                    clean_response = "\n".join(
                        lines[1:-1] if lines[-1].startswith("```") else lines[1:]
                    )
                parsed = json.loads(clean_response)
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and "id" in item:
                            results.append(
                                {
                                    "id": item["id"],
                                    "summary": item.get("summary", ""),
                                    "quality_score": float(
                                        item.get("quality_score", 0.5)
                                    ),
                                    "keywords": item.get("keywords", []),
                                }
                            )
                else:
                    raise LLMError(f"Expected JSON array, got {type(parsed)}")
            except Exception as e:
                logger.warning(
                    "Batch summarize failed for batch %d: %s", i // batch_size, e
                )
                for article in batch:
                    pending.append(article)

        if pending:
            from src.application.summarize import summarize_article_content

            for article in pending:
                try:
                    content = article.get("content") or article.get("description") or ""
                    summary, _, quality, keywords = await summarize_article_content(
                        article.get("url", article.get("id", "")),
                        article.get("title", ""),
                        content,
                        target_lang,
                    )
                    results.append(
                        {
                            "id": article.get("id", ""),
                            "summary": summary,
                            "quality_score": quality,
                            "keywords": keywords,
                        }
                    )
                except Exception as e:
                    logger.warning(
                        "Individual summarize failed for %s: %s",
                        article.get("id", ""),
                        e,
                    )
                    results.append(
                        {
                            "id": article.get("id", ""),
                            "summary": "",
                            "quality_score": 0.0,
                            "keywords": [],
                        }
                    )

        return results


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_llm_client: LLMClient | None = None

# LiteLLM Router singleton — configured from settings
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
    num_retries=0,  # Disable litellm internal retries; we handle them in complete()
    timeout=_timeout_seconds,
)


def get_llm_client() -> LLMClient:
    """Return the global LLMClient singleton."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def reset_llm_client() -> None:
    """Reset the global LLMClient (for testing)."""
    global _llm_client
    _llm_client = None


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


async def llm_complete(
    prompt: str,
    *,
    max_tokens: int = 300,
    temperature: float = 0.3,
) -> str:
    """Short-hand for get_llm_client().complete()."""
    return await get_llm_client().complete(
        prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )


async def batch_summarize_articles(
    articles: list[dict],
    target_lang: str = "en",
    batch_size: int = 3,
) -> list[dict]:
    """Batch summarize articles. Delegates to LLMClient.batch_summarize()."""
    return await get_llm_client().batch_summarize(articles, target_lang, batch_size)
