import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    timeout_ms: int


def load_config(raw):
    try:
        data = json.loads(raw)
        return Config(timeout_ms=int(data["timeout_ms"]))
    except Exception:
        return Config(timeout_ms=1000)
