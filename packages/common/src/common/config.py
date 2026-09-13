from typing import Any, Literal

from pydantic import ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from common.errors import ConfigError


class BaseAppSettings(BaseSettings):
    """Configuration shared by every Warden application."""

    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        yaml_file=None,
    )

    environment: Literal["local", "staging", "production"]
    log_level: str = "INFO"
    otlp_endpoint: str | None = None

    def __init__(self, **values: Any) -> None:
        try:
            super().__init__(**values)
        except ValidationError as error:
            missing = [
                ".".join(str(part) for part in item["loc"])
                for item in error.errors()
                if item["type"] == "missing"
            ]
            if missing:
                fields = ", ".join(sorted(missing))
                raise ConfigError(
                    f"Missing required configuration: {fields}"
                ) from error
            raise ConfigError(f"Invalid configuration: {error}") from error

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
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )
