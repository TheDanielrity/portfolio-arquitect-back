from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_load_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "Test Portfolio")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("CORS_ORIGINS", '["https://portfolio.example"]')
    settings = Settings(_env_file=None)
    assert settings.app_name == "Test Portfolio"
    assert settings.app_env == "test"
    assert settings.debug is True
    assert settings.cors_origins == ["https://portfolio.example"]


def test_dotenv_and_environment_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        'APP_NAME="From file"\nCORS_ORIGINS=["http://localhost:4200"]', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    assert Settings().app_name == "From file"
    monkeypatch.setenv("APP_NAME", "From environment")
    assert Settings().app_name == "From environment"
    assert Settings().cors_origins == ["http://localhost:4200"]


@pytest.mark.parametrize("value", ["invalid-json", "{}"])
def test_invalid_cors_configuration(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic_settings import SettingsError

    monkeypatch.setenv("CORS_ORIGINS", value)
    with pytest.raises((ValidationError, SettingsError)):
        Settings(_env_file=None)


def test_production_rejects_unrestricted_cors() -> None:
    with pytest.raises(ValidationError, match="explicit origins"):
        Settings(_env_file=None, app_env="production", cors_origins=["*"])


def test_production_rejects_debug() -> None:
    with pytest.raises(ValidationError, match="Debug must be disabled"):
        Settings(_env_file=None, app_env="production", debug=True)


def test_database_url_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL")
    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///test.db",
        "postgresql://user:password@localhost/test",
        "postgresql+psycopg2://user:password@localhost/test",
        "postgresql+asyncpg://user:password@localhost/test",
        "postgresql+psycopg://user:password@localhost",
        "postgresql+psycopg://user:password@localhost:99999/test",
        "postgresql+psycopg://user:password@localhost:invalid/test",
        "not-a-url-with-password",
    ],
)
def test_database_url_validation(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)
    assert "password" not in str(error.value)


def test_database_url_secret_and_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy.engine import make_url

    url = "postgresql+psycopg://user:p%40ss%25word@localhost:5432/portfolio?sslmode=require"
    monkeypatch.setenv("DATABASE_URL", url)
    settings = Settings(_env_file=None)
    parsed = make_url(settings.database_url.get_secret_value())
    assert parsed.password == "p@ss%word"
    assert parsed.query["sslmode"] == "require"
    assert url not in repr(settings)
    assert "p%40ss" not in settings.model_dump_json()


def test_jwt_secret_required_and_not_exposed(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = Settings().jwt_secret_key.get_secret_value()
    assert secret not in repr(Settings())
    assert secret not in Settings().model_dump_json()
    monkeypatch.delenv("JWT_SECRET_KEY")
    with pytest.raises(ValidationError, match="jwt_secret_key"):
        Settings(_env_file=None)


@pytest.mark.parametrize("secret", ["short", "CHANGE_ME" * 8])
def test_jwt_secret_rejects_short_and_placeholder_values(
    monkeypatch: pytest.MonkeyPatch, secret: str
) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", secret)
    with pytest.raises(ValidationError) as error:
        Settings()
    assert secret not in str(error.value)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("JWT_ALGORITHM", "none"),
        ("JWT_ALGORITHM", "HS512"),
        ("ACCESS_TOKEN_EXPIRE_MINUTES", "0"),
        ("ACCESS_TOKEN_EXPIRE_MINUTES", "61"),
        ("REFRESH_TOKEN_EXPIRE_DAYS", "0"),
        ("REFRESH_TOKEN_EXPIRE_DAYS", "91"),
        ("MAX_REQUEST_BODY_BYTES", "0"),
        ("MAX_REQUEST_BODY_BYTES", "10485761"),
        ("AUTH_REQUESTS_PER_MINUTE", "0"),
        ("CONTACT_REQUESTS_PER_MINUTE", "0"),
    ],
)
def test_auth_configuration_limits(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings()
