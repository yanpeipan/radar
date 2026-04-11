import pytest

from src.application.entity_report.entity_cluster import EntityClusterer
from src.application.report.models import ReportArticle


def test_entity_clusterer_initialized():
    ec = EntityClusterer(large_event_threshold=50, top_n=50)
    assert ec.large_event_threshold == 50
    assert ec.top_n == 50


def test_entity_clusterer_default():
    ec = EntityClusterer()
    assert ec.top_n == 50
    assert ec.large_event_threshold == 50
