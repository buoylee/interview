from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal, cast

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    SecretStr,
    StrictInt,
)
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from order_contracts.value_objects import CurrencyCode


def _parse_timeout_seconds(value: Any) -> Any:
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    return value


class PaymentProviderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: AnyHttpUrl
    webhook_secret: SecretStr
    timeout_seconds: Annotated[
        StrictInt, BeforeValidator(_parse_timeout_seconds), Field(gt=0, le=30)
    ] = 3


class _CommaSeparatedCurrencySource:
    def prepare_field_value(
        self,
        field_name: str,
        field: FieldInfo,
        value: Any,
        value_is_complex: bool,
    ) -> Any:
        if field_name == "allowed_currencies" and isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class CommaSeparatedEnvSource(_CommaSeparatedCurrencySource, EnvSettingsSource):
    pass


class CommaSeparatedDotEnvSource(
    _CommaSeparatedCurrencySource, DotEnvSettingsSource
):
    pass


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ORDER_",
        env_nested_delimiter="__",
        env_file=None,
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    environment: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    allowed_currencies: tuple[CurrencyCode, ...] = ("USD",)
    payment: PaymentProviderSettings

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        configured_dotenv = cast(DotEnvSettingsSource, dotenv_settings)
        return (
            init_settings,
            CommaSeparatedEnvSource(settings_cls),
            CommaSeparatedDotEnvSource(
                settings_cls,
                env_file=configured_dotenv.env_file,
                env_file_encoding=configured_dotenv.env_file_encoding,
            ),
            file_secret_settings,
        )


def load_settings(
    *,
    env_file: Path | None = None,
    secrets_dir: Path | None = None,
) -> AppSettings:
    return AppSettings(_env_file=env_file, _secrets_dir=secrets_dir)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return load_settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
