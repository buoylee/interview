from langchain_openai import OpenAIEmbeddings

from mvp_agentic_rag.core.config import Settings, get_settings


def get_embeddings(settings: Settings | None = None) -> OpenAIEmbeddings:
    s = settings or get_settings()
    return OpenAIEmbeddings(
        model=s.embedding_model,
        base_url=s.embedding_base_url,
        api_key=s.embedding_api_key,
        dimensions=s.embed_dim,
    )
