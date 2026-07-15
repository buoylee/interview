import pytest

from order_service.db.settings import DatabaseSettings


def test_settings_use_local_compose_url_and_hide_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SQLALCHEMY_DATABASE_URL", raising=False)

    settings = DatabaseSettings.from_env()

    assert settings.url.drivername == "postgresql+psycopg"
    assert settings.url.port == 55432
    assert settings.url.database == "sqlalchemy_handson"
    assert "sqlalchemy:***@" in settings.safe_url
    assert "sqlalchemy:sqlalchemy@" not in settings.safe_url
