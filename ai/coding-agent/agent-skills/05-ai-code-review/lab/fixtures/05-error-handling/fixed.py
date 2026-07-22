import json
from dataclasses import dataclass


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    timeout_ms: int


def load_config(raw):
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError("config must be valid JSON") from exc

    try:
        timeout_ms = data["timeout_ms"]
    except (KeyError, TypeError) as exc:
        raise ConfigError("timeout_ms is required") from exc

    if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int):
        raise ConfigError("timeout_ms must be an integer")
    if timeout_ms <= 0:
        raise ConfigError("timeout_ms must be positive")
    return Config(timeout_ms=timeout_ms)
