import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_accept_environment_values() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://user:pass@db/test",
        redis_url="redis://cache:6379/2",
    )

    assert settings.app_env == "test"
    assert settings.database_url.endswith("/test")
    assert settings.redis_url.endswith("/2")


def test_production_requires_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production", auth_jwt_secret="too-short")


def test_production_rejects_bootstrap_configuration() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production", auth_jwt_secret="x" * 32, auth_bootstrap_token="bootstrap")
