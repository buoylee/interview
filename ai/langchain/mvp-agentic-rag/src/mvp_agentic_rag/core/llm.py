from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from mvp_agentic_rag.core.config import Settings, get_settings


def get_embeddings(settings: Settings | None = None) -> OpenAIEmbeddings:
    s = settings or get_settings()
    return OpenAIEmbeddings(
        model=s.embedding_model,
        base_url=s.embedding_base_url,
        api_key=s.embedding_api_key,
        dimensions=s.embed_dim,
    )


def get_chat_model(settings: Settings | None = None, *, model: str | None = None) -> ChatOpenAI:
    s = settings or get_settings()
    return ChatOpenAI(
        model=model or s.llm_model,
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        temperature=0,
        timeout=30,
        max_retries=2,
    )
