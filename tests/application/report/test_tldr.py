import pytest

from src.application.report.models import EntityTopic
from src.application.report.tldr import TLDRGenerator


def test_tldr_generator_initialized():
    gen = TLDRGenerator()
    assert gen is not None
    assert gen.top_n == 10


def test_tldr_generator_custom_top_n():
    gen = TLDRGenerator(top_n=5)
    assert gen.top_n == 5


def test_tldr_generator_empty_list():
    import asyncio

    gen = TLDRGenerator()
    result = asyncio.get_event_loop().run_until_complete(gen.generate_top10([], "zh"))
    assert result == []
