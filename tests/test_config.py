"""Tests for src.config module."""

from zoneinfo import ZoneInfo

import pytest


def test_get_timezone_returns_zoneinfo():
    """get_timezone should return a ZoneInfo object."""
    from src.application.config import get_timezone

    result = get_timezone()
    assert isinstance(result, ZoneInfo)


def test_get_timezone_default_is_asia_shanghai():
    """get_timezone should default to Asia/Shanghai."""
    from src.application.config import get_timezone

    result = get_timezone()
    assert str(result) == "Asia/Shanghai"


def test_get_default_refresh_interval_returns_int():
    """get_default_refresh_interval should return an integer."""
    from src.application.config import get_default_refresh_interval

    result = get_default_refresh_interval()
    assert isinstance(result, int)


def test_get_default_refresh_interval_default_is_3600():
    """get_default_refresh_interval should default to 3600 seconds."""
    from src.application.config import get_default_refresh_interval

    result = get_default_refresh_interval()
    assert result == 3600
