"""Cross-Encoder reranking using BAAI/bge-reranker-base.

This module provides lazy-loaded Cross-Encoder reranking for search results.
torch and transformers are imported inside _load_reranker() to avoid blocking
imports when the module is not used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.articles import ArticleListItem

# Global cache for model and tokenizer (lazy loaded)
_model = None
_tokenizer = None
_torch = None


def _load_reranker():
    """Lazy load Cross-Encoder model and tokenizer.

    Returns:
        Tuple of (model, tokenizer)

    Raises:
        RuntimeError: If torch or transformers cannot be imported
    """
    global _model, _tokenizer, _torch
    if _model is None:
        import os

        # Auto-use hf-mirror.com if no HF endpoint is configured
        if not os.environ.get("HF_ENDPOINT"):
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            _torch = torch
        except ImportError as e:
            raise RuntimeError(
                "Cross-Encoder rerank requires torch and transformers. "
                "Install with: pip install torch transformers"
            ) from e

        model_name = "BAAI/bge-reranker-base"
        # nosec B615 - revision pinning handled by pip/uv install constraints in pyproject.toml
        _tokenizer = AutoTokenizer.from_pretrained(model_name)
        _model = AutoModelForSequenceClassification.from_pretrained(model_name)
        _model.eval()

    return _model, _tokenizer


def cross_encoder(
    query: str, candidates: list[ArticleListItem], top_k: int = 20
) -> list[ArticleListItem]:
    """Cross-Encoder reranking using BAAI/bge-reranker-base.

    Args:
        query: The search query string.
        candidates: List of ArticleListItem candidates to rerank.
        top_k: Maximum number of candidates to return after reranking.

    Returns:
        List of candidates reranked by ce_score descending, limited to top_k.
    """
    if not candidates:
        return candidates

    model, tokenizer = _load_reranker()

    # Build query-document pairs (query, title)
    texts = [(query, c.title or "") for c in candidates]
    inputs = tokenizer(
        texts, padding=True, truncation=True, return_tensors="pt", max_length=512
    )

    with _torch.no_grad():
        scores = model(**inputs).logits.squeeze(-1).numpy()

    # Populate ce_score and sort descending
    for i, c in enumerate(candidates):
        c.ce_score = float(scores[i])

    candidates.sort(key=lambda x: x.ce_score, reverse=True)
    return candidates[:top_k]
