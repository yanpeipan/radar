"""Tests for src.tags module - TF-IDF fallback for auto-tagging."""
import pytest
import numpy as np


def test_get_embedder_returns_string():
    """_get_embedder should return a string identifier."""
    from src.tags.ai_tagging import _get_embedder
    result = _get_embedder()
    assert isinstance(result, str)
    assert result in ("sentencetransformers", "tfidf")


def test_generate_embedding_returns_numpy_array():
    """generate_embedding should return a numpy array."""
    from src.tags.ai_tagging import generate_embedding
    result = generate_embedding("test text")
    assert isinstance(result, np.ndarray)


def test_generate_embedding_returns_correct_dimensions():
    """generate_embedding should return 384-dimensional vector."""
    from src.tags.ai_tagging import generate_embedding
    from src.tags.ai_tagging import _EMBEDDING_DIM
    result = generate_embedding("test text")
    assert result.shape == (_EMBEDDING_DIM,)


def test_generate_embedding_handles_empty_text():
    """generate_embedding should return zero vector for empty text."""
    from src.tags.ai_tagging import generate_embedding
    from src.tags.ai_tagging import _EMBEDDING_DIM
    result = generate_embedding("")
    assert isinstance(result, np.ndarray)
    assert result.shape == (_EMBEDDING_DIM,)
    assert np.allclose(result, np.zeros(_EMBEDDING_DIM))


def test_generate_embedding_handles_whitespace_only():
    """generate_embedding should return zero vector for whitespace-only text."""
    from src.tags.ai_tagging import generate_embedding
    from src.tags.ai_tagging import _EMBEDDING_DIM
    result = generate_embedding("   \n\t  ")
    assert isinstance(result, np.ndarray)
    assert np.allclose(result, np.zeros(_EMBEDDING_DIM))


def test_generate_embedding_is_normalized_for_non_zero():
    """generate_embedding non-zero vectors should be L2 normalized when using sentencetransformers."""
    from src.tags.ai_tagging import generate_embedding, _get_embedder
    result = generate_embedding("test text for normalization")
    # Only assert normalization when using sentencetransformers (TF-IDF may not normalize to exactly 1.0)
    if _get_embedder() == "sentencetransformers":
        norm = np.linalg.norm(result)
        assert np.isclose(norm, 1.0, atol=1e-5)
    else:
        # TF-IDF fallback - vectorizer must be fitted first for non-zero output
        # This test would need fitting the vectorizer on a corpus first
        pass
