"""LLM client module — unified interface for OpenAI/Ollama/Azure/Anthropic.

Features:
- Provider fallback chain (Ollama → OpenAI → Azure → Anthropic)
- Cost architecture: feed weight gating, recency gating, deduplication, daily cap
- Content truncation with tiktoken
- Async wrapper with timeout and concurrency control
- Rate limiting with exponential backoff
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import tiktoken

# LiteLLM — unified LLM client
from litellm import acompletion

from src.application.config import _get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LLMError(Exception):
    """Base exception for LLM-related errors."""


class DailyCapExceeded(LLMError):
    """Raised when the daily LLM call cap has been exceeded."""


class ContentTruncated(LLMError):
    """Raised when content is truncated due to token limit."""


class ProviderUnavailable(LLMError):
    """Raised when no provider in the fallback chain is available."""


class FeedWeightGated(LLMError):
    """Raised when feed weight is below the gating threshold."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class LLMConfig:
    """LLM configuration loaded from app settings."""

    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: str | None = None
    base_url: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    fallback_chain: list[str] = field(
        default_factory=lambda: ["openai", "azure", "anthropic"]
    )
    max_concurrency: int = 1
    timeout_seconds: int = 60
    max_tokens_per_call: int = 8000
    daily_cap: int = 1000
    weight_gate_min: float = 0.7
    recency_gate_hours: int = 48

    @classmethod
    def from_settings(cls) -> LLMConfig:
        """Load LLM config from app settings."""
        settings = _get_settings()
        llm_data = getattr(settings, "llm", {}) or {}
        # Get API key - handle ${ENV_VAR} template strings
        api_key = llm_data.get("api_key", "")
        if (
            isinstance(api_key, str)
            and api_key.startswith("${")
            and api_key.endswith("}")
        ):
            env_var = api_key[2:-1]
            api_key = os.environ.get(env_var) or os.environ.get("OPENAI_API_KEY")
        elif not api_key:
            api_key = os.environ.get("MINIMAX_API_KEY") or os.environ.get(
                "OPENAI_API_KEY"
            )
        return cls(
            provider=llm_data.get("provider", "openai"),
            model=llm_data.get("model", "gpt-4o-mini"),
            api_key=api_key,
            base_url=llm_data.get("base_url"),
            ollama_base_url=llm_data.get("ollama_base_url", "http://localhost:11434"),
            fallback_chain=llm_data.get(
                "fallback_chain", ["openai", "azure", "anthropic"]
            ),
            max_concurrency=llm_data.get("max_concurrency", 5),
            timeout_seconds=llm_data.get("timeout_seconds", 60),
            max_tokens_per_call=llm_data.get("max_tokens_per_call", 8000),
            daily_cap=llm_data.get("daily_cap", 1000),
            weight_gate_min=llm_data.get("weight_gate_min", 0.7),
            recency_gate_hours=llm_data.get("recency_gate_hours", 48),
        )


# ---------------------------------------------------------------------------
# LiteLLM model mapping
# ---------------------------------------------------------------------------

# Map our provider names to LiteLLM model prefixes
_PROVIDER_MODEL_MAP: dict[str, str] = {
    "openai": "openai/",
    "azure": "azure/",
    "anthropic": "anthropic/",
    "ollama": "ollama/",
    "together": "together/",
    "ai21": "ai21/",
}


def _resolve_model(config: LLMConfig, provider: str | None = None) -> str:
    """Resolve the full model string for LiteLLM.

    LiteLLM uses 'openai/gpt-4o-mini', 'anthropic/claude-3-haiku-20240307', etc.
    For Ollama, uses 'ollama/llama3' or just 'ollama/MODELNAME'.
    """
    p = provider or config.provider
    prefix = _PROVIDER_MODEL_MAP.get(p, f"{p}/")
    # If model already has a prefix, don't double-prefix
    if "/" in config.model:
        return config.model
    return f"{prefix}{config.model}"


# ---------------------------------------------------------------------------
# Token counting & truncation
# ---------------------------------------------------------------------------


def get_encoding_for_model(model: str) -> tiktoken.Encoding:
    """Get tiktoken encoding for a model name."""
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback to cl100k_base for unknown models
        return tiktoken.get_encoding("cl100k_base")


def truncate_content(
    content: str,
    title: str,
    config: LLMConfig,
) -> tuple[str, bool]:
    """Truncate content to max_tokens using tiktoken.

    Preserves title and truncates body. Returns (truncated_content, was_truncated).
    """
    encoding = get_encoding_for_model(config.model)
    title_tokens = len(encoding.encode(title))
    # Reserve tokens for title + prompt overhead (~100 tokens)
    available = config.max_tokens_per_call - title_tokens - 100
    if available < 500:
        available = 500  # minimum usable content

    content_tokens = len(encoding.encode(content))
    if content_tokens <= available:
        return content, False

    # Truncate: take first `available` tokens
    truncated = encoding.decode(encoding.encode(content)[:available])
    return truncated, True


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def compute_content_hash(title: str, content: str) -> str:
    """Compute a SHA256 hash of title + first 500 chars of content."""
    sample = content[:500]
    return hashlib.sha256(f"{title}|{sample}".encode()).hexdigest()


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------


class LLMClient:
    """Unified LLM client with provider fallback, rate limiting, and concurrency control."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig.from_settings()
        self._semaphore: asyncio.Semaphore | None = None
        self._daily_call_count: int = 0
        self._seen_hashes: set[str] = set()

    @property
    def semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.config.max_concurrency)
        return self._semaphore

    def _get_litellm_kwargs(self, provider: str | None = None) -> dict[str, Any]:
        """Build kwargs dict for LiteLLM completion call."""
        model = _resolve_model(self.config, provider)
        kwargs: dict[str, Any] = {
            "model": model,
            "timeout": self.config.timeout_seconds,
            "max_retries": 3,
        }
        p = provider or self.config.provider
        if self.config.base_url:
            kwargs["api_base"] = self.config.base_url
        elif p == "openai":
            if self.config.api_key:
                kwargs["api_key"] = self.config.api_key
        elif p == "ollama":
            kwargs["api_base"] = self.config.ollama_base_url
        elif p == "azure":
            if self.config.api_key:
                kwargs["api_key"] = self.config.api_key
            # Azure also needs api_base and api_version — use env or defaults
            azure_base = os.environ.get("AZURE_API_BASE", "")
            if azure_base:
                kwargs["api_base"] = azure_base
            kwargs["api_version"] = os.environ.get("AZURE_API_VERSION", "2024-02-01")
        return kwargs

    async def complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 300,
        temperature: float = 0.3,
        force_provider: str | None = None,
    ) -> str:
        """Call LLM with provider fallback chain.

        Args:
            prompt: The prompt to send
            max_tokens: Max response tokens
            temperature: Sampling temperature
            force_provider: Override provider selection

        Returns:
            LLM response text

        Raises:
            ProviderUnavailable: No provider in the chain succeeded
            DailyCapExceeded: Daily call cap reached
        """
        if self._daily_call_count >= self.config.daily_cap:
            raise DailyCapExceeded(f"Daily cap {self.config.daily_cap} exceeded")

        if force_provider:
            providers_to_try = [force_provider]
        else:
            # Try primary first, then fallback chain
            providers_to_try = [self.config.provider] + [
                p for p in self.config.fallback_chain if p != self.config.provider
            ]

        last_error: Exception | None = None
        for provider in providers_to_try:
            try:
                return await self._try_complete(
                    provider, prompt, max_tokens, temperature
                )
            except Exception as e:
                last_error = e
                logger.warning("LLM provider %s failed: %s", provider, e)
                continue

        raise ProviderUnavailable(
            f"All providers failed. Last error: {last_error}"
        ) from last_error

    async def _try_complete(
        self,
        provider: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Try a single provider with semaphore + timeout."""
        async with self.semaphore:
            self._daily_call_count += 1
            kwargs = self._get_litellm_kwargs(provider)
            kwargs["max_tokens"] = max_tokens
            kwargs["temperature"] = temperature
            kwargs["messages"] = [{"role": "user", "content": prompt}]

            try:
                response = await asyncio.wait_for(
                    acompletion(**kwargs),
                    timeout=self.config.timeout_seconds,
                )
                # Handle MiniMax overload returning choices: None
                if (
                    response.get("choices") is None
                    or len(response.get("choices", [])) == 0
                ):
                    raise LLMError(f"Provider {provider} returned empty choices")
                return response["choices"][0]["message"]["content"]
            except asyncio.TimeoutError:
                raise LLMError(
                    f"Provider {provider} timed out after {self.config.timeout_seconds}s"
                ) from None

    async def batch_complete(
        self,
        prompts: list[str],
        *,
        max_tokens: int = 300,
        temperature: float = 0.3,
    ) -> list[str]:
        """Batch complete multiple prompts with concurrency control.

        Results are returned in the same order as prompts.
        Failed prompts raise in the list (no silent drop).
        """
        tasks = [
            self.complete(p, max_tokens=max_tokens, temperature=temperature)
            for p in prompts
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_llm_client: LLMClient | None = None


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
    force_provider: str | None = None,
) -> str:
    """Short-hand for get_llm_client().complete()."""
    return await get_llm_client().complete(
        prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        force_provider=force_provider,
    )


async def summarize_text(text: str, title: str = "") -> tuple[str, bool]:
    """Summarize text using LLM.

    Returns (summary, was_truncated).
    """
    config = LLMConfig.from_settings()
    truncated_text, was_truncated = truncate_content(text, title, config)

    prompt = f"""You are a professional content summarizer.
Given the following article, write a concise summary of 3-5 sentences.

Requirements:
- Capture the main point and key takeaways
- Use clear, professional language
- Do not start with "This article..."
- Be informative without being verbose

Article Title: {title}
Article Content:
{truncated_text}

Summary:"""

    summary = await llm_complete(prompt, max_tokens=200, temperature=0.3)
    return summary.strip(), was_truncated


async def score_quality(text: str, title: str = "") -> float:
    """Score article quality 0.0-1.0 using LLM.

    Multi-factor evaluation: content depth, source authority, writing quality, uniqueness.
    """
    prompt = f"""Rate this article's quality on a scale of 0-100.
Consider four factors:
1. Content depth (0-25): Does it have substantive paragraphs with specific details, facts, and analysis?
2. Writing quality (0-25): Is it well-structured, clear, and professional?
3. Originality/uniqueness (0-25): Does it provide novel insights or is it generic?
4. Usefulness (0-25): Would a tech professional find this actionable or informative?

Article Title: {title}
Article Content (first 500 words):
{{content}}

First evaluate each factor, then provide your final score as a single number 0-100.
Return ONLY the number, nothing else."""

    # Use first 500 words for quality scoring
    sample = " ".join(text.split()[:500])
    score_prompt = prompt.format(content=sample)

    try:
        result = await llm_complete(score_prompt, max_tokens=10, temperature=0.1)
        # Parse numeric response
        import re

        numbers = re.findall(r"\d+", result)
        if numbers:
            score = int(numbers[0]) / 100.0
            return min(max(score, 0.0), 1.0)
    except Exception:
        pass
    return 0.5  # default


async def extract_keywords(text: str, max_keywords: int = 5) -> list[str]:
    """Extract keywords from article text using LLM.

    Returns list of 3-5 keywords.
    """
    prompt = f"""Extract {max_keywords} most important keywords or phrases from this article.
Return ONLY a JSON array of strings, nothing else.
Example: ["AI agents", "GPT-4", "automation", "productivity", "LLM"]

Article Content (first 300 words):
{{content}}

Keywords:"""

    sample = " ".join(text.split()[:300])
    keyword_prompt = prompt.format(content=sample)

    try:
        result = await llm_complete(keyword_prompt, max_tokens=50, temperature=0.1)
        # Parse JSON array
        keywords = json.loads(result.strip())
        if isinstance(keywords, list) and all(isinstance(k, str) for k in keywords):
            return keywords[:max_keywords]
    except Exception:
        pass
    return []


async def batch_summarize_articles(
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
    pending: list[dict] = []  # articles not yet successfully batched

    # Process in batches
    for i in range(0, len(articles), batch_size):
        batch = articles[i : i + batch_size]

        # Build prompt with N articles
        article_texts = []
        for idx, article in enumerate(batch, start=1):
            title = article.get("title", "Untitled")[:100]
            content = article.get("content") or article.get("description") or ""
            # Truncate content to avoid token overflow
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
            response = await llm_complete(prompt, max_tokens=2000, temperature=0.3)
            # Strip markdown code blocks if present
            clean_response = response.strip()
            if clean_response.startswith("```"):
                lines = clean_response.split("\n")
                clean_response = "\n".join(
                    lines[1:-1] if lines[-1].startswith("```") else lines[1:]
                )
            # Parse JSON
            parsed = json.loads(clean_response)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and "id" in item:
                        results.append(
                            {
                                "id": item["id"],
                                "summary": item.get("summary", ""),
                                "quality_score": float(item.get("quality_score", 0.5)),
                                "keywords": item.get("keywords", []),
                            }
                        )
            else:
                raise LLMError(f"Expected JSON array, got {type(parsed)}")
        except Exception as e:
            logger.warning(
                "Batch summarize failed for batch %d: %s", i // batch_size, e
            )
            # Fall back to individual processing for failed items
            for article in batch:
                pending.append(article)

    # Process pending articles individually
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
                    "Individual summarize failed for %s: %s", article.get("id", ""), e
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
