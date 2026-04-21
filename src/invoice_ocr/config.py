from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

# Paths resolved relative to project root (3 levels up from this file)
_ROOT = Path(__file__).resolve().parent.parent.parent
_YAML_PATH = _ROOT / "config" / "settings.yaml"
_ENV_PATH = _ROOT / ".env"


class GeminiSettings(BaseSettings):
    """
    Settings for the Gemini API provider.

    Load priority (highest to lowest):
    1. OS environment variables (prefix: GEMINI__)
    2. .env file at project root
    3. config/settings.yaml
    """

    api_key: SecretStr = Field(..., min_length=1)
    model_name: str
    timeout_seconds: float = Field(gt=0)

    model_config = SettingsConfigDict(
        env_prefix="GEMINI__",
        env_nested_delimiter="__",
        extra="forbid",
        str_strip_whitespace=True,
        env_file=str(_ENV_PATH),
        env_file_encoding="utf-8",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls, yaml_file=_YAML_PATH),
            init_settings,
        )