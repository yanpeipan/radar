import pytest

from src.application.report.filter import SignalFilter


def test_signal_filter_quality_threshold():
    articles = [
        {"id": "1", "quality_score": 0.8, "feed_weight": 0.7},
        {"id": "2", "quality_score": 0.5, "feed_weight": 0.7},
    ]
    sf = SignalFilter(quality_threshold=0.6)
    result = sf.filter(articles)
    assert len(result) == 1
    assert result[0]["id"] == "1"


def test_signal_filter_feed_weight_threshold():
    articles = [
        {"id": "1", "quality_score": 0.8, "feed_weight": 0.7},
        {"id": "2", "quality_score": 0.8, "feed_weight": 0.4},
    ]
    sf = SignalFilter(feed_weight_threshold=0.5)
    result = sf.filter(articles)
    assert len(result) == 1
    assert result[0]["id"] == "1"


def test_signal_filter_combined():
    articles = [
        {
            "id": "1",
            "quality_score": 0.8,
            "feed_weight": 0.7,
            "title": "Article 1",
            "content": "Content 1",
        },
        {
            "id": "2",
            "quality_score": 0.5,
            "feed_weight": 0.4,
            "title": "Article 2",
            "content": "Content 2",
        },
        {
            "id": "3",
            "quality_score": 0.7,
            "feed_weight": 0.6,
            "title": "Article 3",
            "content": "Content 3",
        },
    ]
    sf = SignalFilter(quality_threshold=0.6, feed_weight_threshold=0.5)
    result = sf.filter(articles)
    assert len(result) == 2
    ids = {r["id"] for r in result}
    assert ids == {"1", "3"}


def test_signal_filter_event_boost():
    articles = [
        {
            "id": "1",
            "quality_score": 0.55,
            "feed_weight": 0.7,
            "title": "Google Gemma 4 Release",
        },
        {
            "id": "2",
            "quality_score": 0.55,
            "feed_weight": 0.7,
            "title": "Nothing special",
        },
    ]
    sf = SignalFilter(quality_threshold=0.6, event_signal_boost=True)
    result = sf.filter(articles)
    # id=1 has "release" keyword so gets +0.1 boost -> 0.65 >= 0.6
    assert len(result) == 1
    assert result[0]["id"] == "1"


def test_signal_filter_dedup():
    articles = [
        {
            "id": "1",
            "quality_score": 0.8,
            "feed_weight": 0.7,
            "title": "Same",
            "content": "Same content",
        },
        {
            "id": "2",
            "quality_score": 0.8,
            "feed_weight": 0.7,
            "title": "Same",
            "content": "Same content",
        },
    ]
    sf = SignalFilter(quality_threshold=0.6, feed_weight_threshold=0.5)
    result = sf.filter(articles)
    assert len(result) == 1
