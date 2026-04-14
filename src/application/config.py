"""Application configuration using Pydantic BaseSettings."""

import os
from pathlib import Path
from zoneinfo import ZoneInfo

import platformdirs
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_settings: "FeedshipSettings | None" = None
_cached_timezone: "ZoneInfo | None" = None


def _resolve_env_vars(value: str) -> str:
    """Resolve ${VAR} environment variable references in config strings."""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        return os.environ.get(value[2:-1], value)
    return value


def _resolve_dict_env_vars(data: dict) -> dict:
    """Recursively resolve ${VAR} references in dict values."""
    result = {}
    for k, v in data.items():
        if isinstance(v, str):
            result[k] = _resolve_env_vars(v)
        elif isinstance(v, dict):
            result[k] = _resolve_dict_env_vars(v)
        elif isinstance(v, list):
            result[k] = [
                _resolve_dict_env_vars(item)
                if isinstance(item, dict)
                else _resolve_env_vars(item)
                if isinstance(item, str)
                else item
                for item in v
            ]
        else:
            result[k] = v
    return result


class FeedshipSettings(BaseSettings):
    """Application settings with Pydantic validation.

    Loaded from config.yaml and environment variables.
    Environment variables use the FEEDSHIP_ prefix.
    """

    model_config = SettingsConfigDict(
        env_prefix="FEEDSHIP_",
        extra="allow",
    )

    timezone: str = Field(default="Asia/Shanghai")
    bm25_factor: float = Field(default=0.5)
    feed_default_weight: float = Field(default=0.3)
    feed_default_refresh_interval: int = Field(default=3600)
    reports_dir: str | None = Field(default=None)

    # Complex nested config stored as dict (rate limiting, tavily, nitter, webpage_sites, llm)
    rate_limit: dict = Field(default_factory=dict)
    tavily: dict = Field(default_factory=dict)
    nitter: dict = Field(default_factory=dict)
    webpage_sites: dict = Field(default_factory=dict)
    llm: dict = Field(default_factory=dict)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Ensure timezone is a valid ZoneInfo key."""
        try:
            ZoneInfo(v)
        except Exception:
            raise ValueError(f"Invalid timezone: {v!r}") from None
        return v

    @field_validator("bm25_factor", "feed_default_weight")
    @classmethod
    def validate_0_to_1(cls, v: float) -> float:
        """Ensure float is between 0.0 and 1.0."""
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"Value {v} must be between 0.0 and 1.0")
        return v

    @classmethod
    def from_yaml(cls, config_path: Path | str) -> "FeedshipSettings":
        """Load settings from a YAML config file."""
        import yaml

        if isinstance(config_path, str):
            config_path = Path(config_path)

        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

        return cls.model_validate(data)


def _get_settings() -> FeedshipSettings:
    """Return cached FeedshipSettings instance.

    Loads from config.yaml on first call. Subsequent calls return cached instance.
    For test isolation, settings are NOT cached across test runs.
    Uses platformdirs to find the user config directory.
    """
    global _settings

    # Check for test isolation: if running in pytest, skip cache
    import sys

    if "pytest" in sys.modules or _settings is None:
        config_dir = platformdirs.user_config_dir("feedship", appauthor=False)
        config_path = Path(config_dir) / "config.yaml"

        # Create config directory and default config if it doesn't exist
        if not config_path.exists():
            Path(config_dir).mkdir(parents=True, exist_ok=True)
            _create_default_config(config_path)

        _settings = FeedshipSettings.from_yaml(config_path)
        # Resolve ${VAR} env var references in loaded config
        raw = _settings.model_dump()
        resolved = _resolve_dict_env_vars(raw)
        _settings = FeedshipSettings.model_validate(resolved)

    return _settings


def _create_default_config(config_path: Path) -> None:
    """Create a default config.yaml file."""
    import yaml

    default_config = {
        "timezone": "Asia/Shanghai",
        "bm25_factor": 0.5,
        "feed_default_weight": 0.3,
        "feed_default_refresh_interval": 3600,
        "rate_limit": {},
        "tavily": {},
        "nitter": {},
        "webpage_sites": {},
        "llm": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "ollama_base_url": "http://localhost:11434",
            "fallback_chain": ["openai", "azure", "anthropic"],
            "max_concurrency": 2,
            "timeout_seconds": 120,  # Increased from 60 for batch classification under concurrent load
            "max_tokens_per_call": 8000,
            "daily_cap": 1000,
            "weight_gate_min": 0.7,
            "recency_gate_hours": 48,
        },
    }
    with open(config_path, "w") as f:
        yaml.safe_dump(default_config, f, default_flow_style=False)


def get_timezone() -> ZoneInfo:
    """Return the configured timezone as a ZoneInfo object (cached)."""
    global _cached_timezone

    if _cached_timezone is None:
        tz_name = _get_settings().timezone
        _cached_timezone = ZoneInfo(tz_name)

    return _cached_timezone


def get_default_feed_weight() -> float:
    """Return the default feed weight for semantic search ranking."""
    return _get_settings().feed_default_weight


def get_default_refresh_interval() -> int:
    """Return the default refresh interval for feed updates in seconds."""
    return _get_settings().feed_default_refresh_interval


def get_bm25_factor() -> float:
    """Return the BM25 sigmoid normalization factor (default 0.5)."""
    return _get_settings().bm25_factor


def get_reports_dir() -> Path:
    """Return the reports directory from config, or a sensible default."""
    reports_dir = _get_settings().reports_dir
    if reports_dir:
        return Path(reports_dir)
    return Path(platformdirs.user_data_dir("feedship", appauthor=False)) / "reports"
