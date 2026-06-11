# tests/test_obs_otel.py
import base64

from mvp_agentic_rag.core.config import Settings
from mvp_agentic_rag.obs.otel import langfuse_otlp_config


def _settings(**overrides):
    base = dict(
        obs_backend="otel",
        langfuse_public_key="pk-lf-1",
        langfuse_secret_key="sk-lf-2",
        langfuse_host="http://localhost:3000",
    )
    base.update(overrides)
    return Settings(**base)


def test_otlp_config_builds_langfuse_endpoint_and_basic_auth():
    endpoint, headers = langfuse_otlp_config(_settings())
    assert endpoint == "http://localhost:3000/api/public/otel/v1/traces"
    expected = base64.b64encode(b"pk-lf-1:sk-lf-2").decode()
    assert headers["Authorization"] == f"Basic {expected}"
    assert headers["x-langfuse-ingestion-version"] == "4"


def test_otlp_config_none_when_keys_missing():
    assert langfuse_otlp_config(_settings(langfuse_public_key="")) is None
