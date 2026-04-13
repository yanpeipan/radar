import pytest

from src.application.articles import ArticleListItem
from src.application.report.filter import SignalFilter


def _make_article(
    id: str, quality_score: float, feed_weight: float, **kwargs
) -> ArticleListItem:
    """Helper to create ArticleListItem for testing."""
    defaults = {
        "id": id,
        "feed_id": "feed1",
        "feed_name": "Test Feed",
        "title": "Test Title",
        "link": "https://example.com",
        "guid": f"guid-{id}",
        "published_at": "2026-04-01 00:00:00",
        "description": "Test description",
        "vec_sim": 0.0,
        "bm25_score": 0.0,
        "freshness": 0.0,
        "source_weight": 0.3,
        "ce_score": 0.0,
        "score": 0.0,
        "quality_score": quality_score,
        "content": None,
        "summary": None,
        "feed_weight": feed_weight,
        "feed_url": "https://example.com/feed",
        "content_hash": None,
        "minhash_signature": None,
        "tags": [],
        "translation": None,
    }
    defaults.update(kwargs)
    return ArticleListItem(**defaults)


def test_signal_filter_quality_threshold():
    articles = [
        _make_article("1", quality_score=0.8, feed_weight=0.7),
        _make_article("2", quality_score=0.5, feed_weight=0.7),
    ]
    sf = SignalFilter(quality_threshold=0.6)
    result = sf.filter(articles)
    assert len(result) == 1
    assert result[0].id == "1"


def test_signal_filter_feed_weight_threshold():
    articles = [
        _make_article("1", quality_score=0.8, feed_weight=0.7),
        _make_article("2", quality_score=0.8, feed_weight=0.4),
    ]
    sf = SignalFilter(feed_weight_threshold=0.5)
    result = sf.filter(articles)
    assert len(result) == 1
    assert result[0].id == "1"


def test_signal_filter_combined():
    articles = [
        _make_article(
            "1",
            quality_score=0.8,
            feed_weight=0.7,
            title="Article 1",
            content="Content 1",
        ),
        _make_article(
            "2",
            quality_score=0.5,
            feed_weight=0.4,
            title="Article 2",
            content="Content 2",
        ),
        _make_article(
            "3",
            quality_score=0.7,
            feed_weight=0.6,
            title="Article 3",
            content="Content 3",
        ),
    ]
    sf = SignalFilter(quality_threshold=0.6, feed_weight_threshold=0.5)
    result = sf.filter(articles)
    assert len(result) == 2
    ids = {r.id for r in result}
    assert ids == {"1", "3"}


def test_signal_filter_event_boost():
    articles = [
        _make_article(
            "1", quality_score=0.55, feed_weight=0.7, title="Google Gemma 4 Release"
        ),
        _make_article(
            "2", quality_score=0.55, feed_weight=0.7, title="Nothing special"
        ),
    ]
    sf = SignalFilter(quality_threshold=0.6, event_signal_boost=True)
    result = sf.filter(articles)
    # id=1 has "release" keyword so gets +0.1 boost -> 0.65 >= 0.6
    assert len(result) == 1
    assert result[0].id == "1"
