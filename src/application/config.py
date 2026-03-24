"""Application configuration loaded from config.yaml via dynaconf."""
from pathlib import Path

from dynaconf import Dynaconf
from zoneinfo import ZoneInfo

_settings: Dynaconf | None = None

def _get_settings() -> Dynaconf:
    global _settings
    if _settings is None:
        _settings = Dynaconf(
            envvar_prefix="RADAR",
            settings_files=[
                Path(__file__).parent.parent / "config.yaml",
            ],
        )
    return _settings


def get_timezone() -> ZoneInfo:
    """Return the configured timezone as a ZoneInfo object."""
    tz_name = _get_settings().get("timezone", "Asia/Shanghai")
    return ZoneInfo(tz_name)
