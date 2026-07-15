from collections.abc import Iterator
import os
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings

from order_contracts.config import (
    AppSettings,
    clear_settings_cache,
    get_settings,
    load_settings,
)


ENV_KEYS = (
    "ORDER_ENVIRONMENT",
    "ORDER_LOG_LEVEL",
    "ORDER_ALLOWED_CURRENCIES",
    "ORDER_PAYMENT__BASE_URL",
    "ORDER_PAYMENT__WEBHOOK_SECRET",
    "ORDER_PAYMENT__TIMEOUT_SECONDS",
)


@pytest.fixture(autouse=True)
def isolate_order_environment(monkeypatch) -> Iterator[None]:
    order_keys = set(ENV_KEYS)
    order_keys.update(key for key in os.environ if key.upper().startswith("ORDER_"))
    for key in order_keys:
        monkeypatch.delenv(key, raising=False)
    clear_settings_cache()
    yield
    clear_settings_cache()


def set_required_env(monkeypatch) -> None:
    monkeypatch.setenv("ORDER_PAYMENT__BASE_URL", "https://env.example.test")
    monkeypatch.setenv("ORDER_PAYMENT__WEBHOOK_SECRET", "env-secret")


def test_env_overrides_explicit_dotenv(monkeypatch, tmp_path: Path) -> None:
    dotenv = tmp_path / "settings.env"
    dotenv.write_text(
        "ORDER_PAYMENT__BASE_URL=https://dotenv.example.test\n"
        "ORDER_PAYMENT__WEBHOOK_SECRET=dotenv-secret\n",
        encoding="utf-8",
    )
    set_required_env(monkeypatch)
    settings = load_settings(env_file=dotenv)
    assert str(settings.payment.base_url) == "https://env.example.test/"
    assert settings.payment.webhook_secret.get_secret_value() == "env-secret"


def test_init_overrides_environment(monkeypatch) -> None:
    set_required_env(monkeypatch)
    settings = AppSettings(
        payment={
            "base_url": "https://init.example.test",
            "webhook_secret": "init-secret",
        }
    )
    assert str(settings.payment.base_url) == "https://init.example.test/"
    assert settings.payment.webhook_secret.get_secret_value() == "init-secret"


def test_custom_env_source_parses_currency_csv(monkeypatch) -> None:
    set_required_env(monkeypatch)
    monkeypatch.setenv("ORDER_ALLOWED_CURRENCIES", "usd, eur")
    settings = load_settings()
    assert settings.allowed_currencies == ("USD", "EUR")


def test_timeout_rejects_non_integer_environment_value(monkeypatch) -> None:
    set_required_env(monkeypatch)
    monkeypatch.setenv("ORDER_PAYMENT__TIMEOUT_SECONDS", "3.0")
    with pytest.raises(ValidationError) as caught:
        load_settings()
    error = caught.value.errors()[0]
    assert error["type"] == "int_type"
    assert error["loc"] == ("payment", "timeout_seconds")


def test_timeout_parses_integer_environment_value(monkeypatch) -> None:
    set_required_env(monkeypatch)
    monkeypatch.setenv("ORDER_PAYMENT__TIMEOUT_SECONDS", "5")
    settings = load_settings()
    assert settings.payment.timeout_seconds == 5
    assert type(settings.payment.timeout_seconds) is int


def test_environment_names_are_case_insensitive(monkeypatch) -> None:
    monkeypatch.setenv("order_payment__base_url", "https://lower.example.test")
    monkeypatch.setenv("order_payment__webhook_secret", "lower-secret")
    settings = load_settings()
    assert str(settings.payment.base_url) == "https://lower.example.test/"


def test_unprefixed_environment_does_not_satisfy_required_settings(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PAYMENT__BASE_URL", "https://unprefixed.example.test")
    monkeypatch.setenv("PAYMENT__WEBHOOK_SECRET", "unprefixed-secret")
    with pytest.raises(ValidationError) as caught:
        load_settings()
    assert caught.value.errors()[0]["loc"] == ("payment",)


def test_default_loader_does_not_read_ambient_dotenv(
    monkeypatch, tmp_path: Path
) -> None:
    set_required_env(monkeypatch)
    (tmp_path / ".env").write_text("ORDER_LOG_LEVEL=DEBUG\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    settings = load_settings()
    assert settings.log_level == "INFO"


def test_file_secret_source_can_be_explicit(monkeypatch, tmp_path: Path) -> None:
    class SecretOnlySettings(BaseSettings):
        api_key: SecretStr

    monkeypatch.delenv("API_KEY", raising=False)
    (tmp_path / "api_key").write_text("file-secret", encoding="utf-8")
    settings = SecretOnlySettings(_secrets_dir=tmp_path)
    assert settings.api_key.get_secret_value() == "file-secret"
    assert "file-secret" not in repr(settings)


def test_app_file_secrets_override_defaults_and_supply_nested_model(
    tmp_path: Path,
) -> None:
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    (secrets_dir / "ORDER_LOG_LEVEL").write_text("ERROR", encoding="utf-8")
    (secrets_dir / "ORDER_PAYMENT").write_text(
        '{"base_url":"https://secret.example.test",'
        '"webhook_secret":"file-secret"}',
        encoding="utf-8",
    )
    settings = load_settings(secrets_dir=secrets_dir)
    assert settings.log_level == "ERROR"
    assert str(settings.payment.base_url) == "https://secret.example.test/"
    assert settings.payment.webhook_secret.get_secret_value() == "file-secret"


def test_explicit_dotenv_overrides_file_secrets(tmp_path: Path) -> None:
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    (secrets_dir / "ORDER_LOG_LEVEL").write_text("ERROR", encoding="utf-8")
    (secrets_dir / "ORDER_PAYMENT").write_text(
        '{"base_url":"https://secret.example.test",'
        '"webhook_secret":"file-secret"}',
        encoding="utf-8",
    )
    dotenv = tmp_path / "settings.env"
    dotenv.write_text("ORDER_LOG_LEVEL=DEBUG\n", encoding="utf-8")
    settings = load_settings(env_file=dotenv, secrets_dir=secrets_dir)
    assert settings.log_level == "DEBUG"
    assert settings.payment.webhook_secret.get_secret_value() == "file-secret"


def test_explicit_dotenv_ignores_unrelated_entries(tmp_path: Path) -> None:
    dotenv = tmp_path / "settings.env"
    dotenv.write_text(
        "UNRELATED=value\n"
        "ORDER_UNKNOWN=value\n"
        "ORDER_PAYMENT__BASE_URL=https://dotenv.example.test\n"
        "ORDER_PAYMENT__WEBHOOK_SECRET=dotenv-secret\n",
        encoding="utf-8",
    )
    settings = load_settings(env_file=dotenv)
    assert str(settings.payment.base_url) == "https://dotenv.example.test/"


def test_explicit_dotenv_parses_currency_csv(tmp_path: Path) -> None:
    dotenv = tmp_path / "settings.env"
    dotenv.write_text(
        "ORDER_ALLOWED_CURRENCIES=usd, eur\n"
        "ORDER_PAYMENT__BASE_URL=https://dotenv.example.test\n"
        "ORDER_PAYMENT__WEBHOOK_SECRET=dotenv-secret\n",
        encoding="utf-8",
    )
    settings = load_settings(env_file=dotenv)
    assert settings.allowed_currencies == ("USD", "EUR")


def test_nested_payment_settings_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError) as caught:
        AppSettings(
            payment={
                "base_url": "https://init.example.test",
                "webhook_secret": "init-secret",
                "unknown": "value",
            }
        )
    error = caught.value.errors()[0]
    assert error["type"] == "extra_forbidden"
    assert error["loc"] == ("payment", "unknown")


def test_settings_repr_redacts_payment_secret(monkeypatch) -> None:
    set_required_env(monkeypatch)
    settings = load_settings()
    assert "env-secret" not in repr(settings)


def test_startup_factory_fails_fast_without_required_settings() -> None:
    with pytest.raises(ValidationError) as caught:
        get_settings()
    assert caught.value.errors()[0]["loc"] == ("payment",)


def test_cache_is_explicit_and_clearable(monkeypatch) -> None:
    set_required_env(monkeypatch)
    clear_settings_cache()
    first = get_settings()
    second = get_settings()
    assert first is second
    clear_settings_cache()
    assert get_settings() is not first
    clear_settings_cache()
