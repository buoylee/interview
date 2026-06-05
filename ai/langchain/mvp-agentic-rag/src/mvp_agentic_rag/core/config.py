from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Embedding(OpenAI 兼容)
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embed_dim: int = 1536

    # Postgres
    database_url: str = "postgresql://rag:rag@localhost:5433/rag"

    # 检索旋钮
    top_k_dense: int = 20
    top_k_sparse: int = 20
    rrf_k: int = 60
    rerank_top_n: int = 5
    chunk_size: int = 800
    chunk_overlap: int = 120
    fts_config: str = "simple"


@lru_cache
def get_settings() -> Settings:
    return Settings()
