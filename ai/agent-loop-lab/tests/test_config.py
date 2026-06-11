import base64

from agent_loop.config import Settings, langfuse_otlp_config


def _settings(**overrides):
    base = dict(
        llm_base_url="https://api.openai.com/v1",
        llm_api_key="sk-x",
        llm_model="gpt-4o-mini",
        langfuse_host="http://localhost:3000",
        langfuse_public_key="pk-lf-1",
        langfuse_secret_key="sk-lf-2",
    )
    base.update(overrides)
    return Settings(**base)


def test_otlp_config_builds_langfuse_endpoint_and_basic_auth():
    endpoint, headers = langfuse_otlp_config(_settings())
    assert endpoint == "http://localhost:3000/api/public/otel/v1/traces"
    expected_auth = base64.b64encode(b"pk-lf-1:sk-lf-2").decode()
    assert headers["Authorization"] == f"Basic {expected_auth}"
    assert headers["x-langfuse-ingestion-version"] == "4"


def test_otlp_config_none_when_keys_missing():
    assert langfuse_otlp_config(_settings(langfuse_public_key="")) is None
