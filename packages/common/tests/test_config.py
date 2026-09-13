from pathlib import Path

import pytest
from common.config import BaseAppSettings
from common.errors import ConfigError
from pydantic_settings import SettingsConfigDict


class ServiceSettings(BaseAppSettings):
    api_key: str


@pytest.mark.unit
def test_missing_fields_raise_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)

    with pytest.raises(ConfigError) as captured:
        ServiceSettings()

    assert "api_key" in str(captured.value)
    assert "environment" in str(captured.value)


@pytest.mark.unit
def test_settings_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("UNRELATED_VARIABLE", "ignored")

    settings = ServiceSettings()

    assert settings.environment == "staging"
    assert settings.api_key == "secret"


@pytest.mark.unit
def test_settings_load_from_dotenv(tmp_path: Path) -> None:
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text("ENVIRONMENT=local\nAPI_KEY=from-dotenv\n")

    settings = ServiceSettings(_env_file=dotenv_file)

    assert settings.environment == "local"
    assert settings.api_key == "from-dotenv"


@pytest.mark.unit
def test_settings_load_from_yaml(tmp_path: Path) -> None:
    yaml_file = tmp_path / "settings.yaml"
    yaml_file.write_text("environment: production\napi_key: from-yaml\n")

    class YamlServiceSettings(ServiceSettings):
        model_config = SettingsConfigDict(yaml_file=yaml_file, extra="ignore")

    settings = YamlServiceSettings()

    assert settings.environment == "production"
    assert settings.api_key == "from-yaml"
